"""FastAPI application for the subtitle management system."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from common.config import settings
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import SubtitleStatus
from common.utils import StatusProgressCalculator
from manager.orchestrator import orchestrator
from manager.schemas import (
    HealthResponse,
    JellyfinWebhookPayload,
    QueueStatusResponse,
    SubtitleRequestCreate,
    SubtitleResponse,
    SubtitleStatusResponse,
    SubtitleTranslateRequest,
    WebhookAcknowledgement,
)

# Configure logging
service_logger = setup_service_logging("manager", enable_file_logging=True)
logger = service_logger.logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting subtitle management API...")
    await redis_client.connect()
    await orchestrator.connect()
    logger.info("API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down subtitle management API...")
    await orchestrator.disconnect()
    await redis_client.disconnect()
    logger.info("API shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Subtitle Management API",
    description="API for managing subtitle download and translation workflows",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    redis_health = await redis_client.health_check()

    # Include Redis status in health check
    health_status = HealthResponse()
    if not redis_health.get("connected"):
        logger.warning(
            f"Redis health check failed: {redis_health.get('error', 'Unknown error')}"
        )

    return health_status


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Subtitle Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/subtitles/{job_id}", response_model=SubtitleResponse)
async def get_subtitle_details(job_id: UUID):
    """Get detailed information about a subtitle job."""
    job = await redis_client.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subtitle job not found"
        )

    return job


@app.get("/subtitles/{job_id}/events", response_model=Dict[str, Any])
async def get_job_event_history(job_id: UUID):
    """
    Get event history for a subtitle job.
    
    Returns a list of all events that occurred during the processing of this job,
    providing a complete audit trail of the workflow.
    """
    # First check if job exists
    job = await redis_client.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtitle job not found"
        )
    
    # Get event history
    events = await redis_client.get_job_events(job_id)
    
    if not events:
        # Job exists but no events yet
        return {
            "job_id": str(job_id),
            "event_count": 0,
            "events": [],
            "message": "No events recorded for this job yet"
        }
    
    return {
        "job_id": str(job_id),
        "event_count": len(events),
        "events": events
    }


@app.get("/subtitles", response_model=List[SubtitleResponse])
async def list_subtitle_requests():
    """List all subtitle requests."""
    jobs = await redis_client.list_jobs()
    return jobs


@app.get("/queue/status", response_model=QueueStatusResponse)
async def get_queue_status():
    """Get the status of processing queues."""
    try:
        status_data = await orchestrator.get_queue_status()
        return QueueStatusResponse(**status_data)
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get queue status",
        )


@app.post("/subtitles/download", response_model=SubtitleResponse, status_code=status.HTTP_201_CREATED)
async def request_subtitle_download(request: SubtitleRequestCreate):
    """
    Request subtitle download for a video.
    
    """
    try:
        # Create subtitle response
        subtitle_response = SubtitleResponse(
            video_url=request.video_url,
            video_title=request.video_title,
            language=request.language,
            target_language=request.target_language,
            status=SubtitleStatus.PENDING,
        )

        # Store the request in Redis
        await redis_client.save_job(subtitle_response)

        # Enqueue download task
        success = await orchestrator.enqueue_download_task(
            request, subtitle_response.id
        )

        if not success:
            subtitle_response.status = SubtitleStatus.FAILED
            subtitle_response.error_message = "Failed to enqueue download task"
            await redis_client.save_job(subtitle_response)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue download task",
            )

        logger.info(f"Subtitle download request created: {subtitle_response.id}")
        return subtitle_response

    except Exception as e:
        logger.error(f"Error processing subtitle download request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# Mock endpoint for testing RabbitMQ integration
@app.post("/test/queue-message")
async def test_queue_message():
    """Test endpoint to enqueue a mock message."""
    try:
        # Create a mock request
        mock_request = SubtitleRequestCreate(
            video_url="https://example.com/test-video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            preferred_sources=["opensubtitles"],
        )

        # Create a mock response
        mock_response = SubtitleResponse(
            video_url=mock_request.video_url,
            video_title=mock_request.video_title,
            language=mock_request.language,
            target_language=mock_request.target_language,
            status=SubtitleStatus.PENDING,
        )

        # Store the request in Redis
        await redis_client.save_job(mock_response)

        # Enqueue the task
        success = await orchestrator.enqueue_download_task(
            mock_request, mock_response.id
        )

        if success:
            return {
                "message": "Mock message enqueued successfully",
                "request_id": str(mock_response.id),
                "status": "success",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue mock message",
            )

    except Exception as e:
        logger.error(f"Error testing queue message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test queue message",
        )


@app.post("/subtitles/translate", response_model=SubtitleResponse)
async def translate_subtitle_file(request: SubtitleTranslateRequest):
    """
    Enqueue a subtitle file for translation.
    
    The translator worker will read the file from the provided path
    and send its content to OpenAI API for translation.
    """
    try:
        # Create a new job for the translation
        subtitle_response = SubtitleResponse(
            video_url="",  # No video URL for direct translation
            video_title=request.video_title or "Translation Job",
            language=request.source_language,
            target_language=request.target_language,
            status=SubtitleStatus.PENDING,
        )

        # Store the request in Redis
        await redis_client.save_job(subtitle_response)

        logger.info(
            f"Translation request for file: {request.subtitle_path} -> {request.target_language}"
        )

        # Enqueue translation task - the worker will read the file and send to OpenAI
        success = await orchestrator.enqueue_translation_task(
            subtitle_response.id,
            request.subtitle_path,
            request.source_language,
            request.target_language,
        )

        if not success:
            subtitle_response.status = SubtitleStatus.FAILED
            subtitle_response.error_message = "Failed to enqueue translation task"
            await redis_client.save_job(subtitle_response)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to enqueue translation task",
            )

        logger.info(f"Translation request created: {subtitle_response.id}")
        return subtitle_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing translation request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@app.get("/subtitles/status/{job_id}", response_model=SubtitleStatusResponse)
async def get_job_status(job_id: UUID):
    """Get the status of a subtitle job."""
    subtitle = await redis_client.get_job(job_id)

    if not subtitle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subtitle request not found"
        )

    # Calculate progress based on status using utility function
    progress_mapping = StatusProgressCalculator.get_subtitle_status_progress_mapping()
    progress = StatusProgressCalculator.calculate_progress_for_status(
        subtitle.status, progress_mapping
    )

    return SubtitleStatusResponse(
        id=subtitle.id,
        status=subtitle.status.value,
        progress=progress,
        message=f"Status: {subtitle.status.value}",
    )


@app.post("/webhooks/jellyfin", response_model=WebhookAcknowledgement)
async def handle_jellyfin_webhook(payload: JellyfinWebhookPayload):
    """Handle webhook notifications from Jellyfin."""
    try:
        logger.info(f"Received Jellyfin webhook: {payload.event} - {payload.item_name}")

        # Only process library item added or updated events
        if payload.event not in ["library.item.added", "library.item.updated"]:
            return WebhookAcknowledgement(
                status="ignored",
                message=f"Event type {payload.event} is not processed",
            )

        # Only process video items
        if payload.item_type not in ["Movie", "Episode"]:
            return WebhookAcknowledgement(
                status="ignored",
                message=f"Item type {payload.item_type} is not a video",
            )

        # Determine video URL - prefer provided URL, fall back to constructing from path
        video_url = payload.video_url or payload.item_path or ""

        if not video_url:
            logger.warning(
                f"No video URL or path provided for item {payload.item_name}"
            )
            return WebhookAcknowledgement(
                status="error", message="No video URL or path provided"
            )

        # Create subtitle request with default settings
        subtitle_request = SubtitleRequestCreate(
            video_url=video_url,
            video_title=payload.item_name,
            language=settings.jellyfin_default_source_language,
            target_language=settings.jellyfin_default_target_language,
            preferred_sources=["opensubtitles"],
        )

        # Create subtitle response
        subtitle_response = SubtitleResponse(
            video_url=subtitle_request.video_url,
            video_title=subtitle_request.video_title,
            language=subtitle_request.language,
            target_language=subtitle_request.target_language,
            status=SubtitleStatus.PENDING,
        )

        # Store the request in Redis
        await redis_client.save_job(subtitle_response)

        # Enqueue download task (will auto-trigger translation if target_language is set)
        if settings.jellyfin_auto_translate and subtitle_request.target_language:
            success = await orchestrator.enqueue_download_with_translation(
                subtitle_request, subtitle_response.id
            )
        else:
            success = await orchestrator.enqueue_download_task(
                subtitle_request, subtitle_response.id
            )

        if not success:
            subtitle_response.status = SubtitleStatus.FAILED
            subtitle_response.error_message = "Failed to enqueue download task"
            await redis_client.save_job(subtitle_response)
            return WebhookAcknowledgement(
                status="error",
                job_id=subtitle_response.id,
                message="Failed to enqueue subtitle processing task",
            )

        logger.info(
            f"Jellyfin webhook processed successfully. Job ID: {subtitle_response.id}"
        )
        return WebhookAcknowledgement(
            status="received",
            job_id=subtitle_response.id,
            message=f"Subtitle processing queued for {payload.item_name}",
        )

    except Exception as e:
        logger.error(f"Error processing Jellyfin webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
