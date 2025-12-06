"""FastAPI application for the subtitle management system."""

from contextlib import asynccontextmanager
from typing import Any, Dict, List
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from common.config import settings
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import SubtitleStatus
from manager.event_consumer import event_consumer
from manager.health import check_health
from manager.helpers import (
    calculate_job_progress_percentage,
    initialize_all_connections_on_startup,
    publish_job_failure_and_raise_http_error,
    shutdown_all_connections,
    start_event_consumer_if_ready,
)
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

# Global variable to hold the event consumer task
consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global consumer_task

    # Startup
    logger.info("Starting subtitle management API...")
    await initialize_all_connections_on_startup()

    consumer_task = await start_event_consumer_if_ready()
    logger.info("API startup complete")

    yield

    # Shutdown
    await shutdown_all_connections(consumer_task)


# Create FastAPI application
app = FastAPI(
    title="Subtitle Management API",
    description="API for managing subtitle download and translation workflows",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS based on environment
# Parse comma-separated origins from config
allowed_origins = (
    [origin.strip() for origin in settings.cors_allowed_origins.split(",")]
    if settings.cors_allowed_origins
    else ["http://localhost:3000"]  # Safe default for development
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Explicit methods only
    allow_headers=["Content-Type", "Authorization"],  # Explicit headers only
)


@app.get("/health", response_model=Dict[str, Any])
async def health_check_endpoint(response: Response):
    """Comprehensive health check endpoint for all Manager service components."""
    health_status = await check_health()

    # Set HTTP status code based on health status
    if health_status.get("status") == "unhealthy":
        response.status_code = 503  # Service Unavailable
    elif health_status.get("status") == "error":
        response.status_code = 500  # Internal Server Error
    else:
        response.status_code = 200  # OK

    return health_status


@app.get("/health/simple", response_model=HealthResponse)
async def simple_health_check():
    """Simple health check endpoint for backward compatibility."""
    redis_health = await redis_client.health_check()

    # Include Redis status in health check
    health_status = HealthResponse()
    if not redis_health.get("connected"):
        logger.warning(
            f"Redis health check failed: {redis_health.get('error', 'Unknown error')}"
        )

    return health_status


@app.get("/health/startup", response_model=Dict[str, str])
async def startup_health_check():
    """
    Startup health check endpoint for Docker healthcheck.

    Returns 200 OK if the application is running, regardless of dependency status.
    This allows the container to start and report healthy even if Redis/RabbitMQ
    aren't ready yet. Use /health endpoint for detailed dependency status.
    """
    return {
        "status": "running",
        "message": "Manager service is running (use /health for detailed status)",
    }


@app.get("/health/consumer", response_model=Dict[str, Any])
async def consumer_health_check():
    """Check event consumer health status."""
    consumer_healthy = await event_consumer.is_healthy()
    return {
        "status": "healthy" if consumer_healthy else "unhealthy",
        "is_consuming": event_consumer.is_consuming,
        "connected": event_consumer.connection is not None
        and not event_consumer.connection.is_closed,
        "queue_name": event_consumer.queue_name,
        "routing_key": event_consumer.routing_key,
    }


@app.get("/health/orchestrator", response_model=Dict[str, Any])
async def orchestrator_health_check():
    """Check orchestrator health status."""
    orchestrator_healthy = await orchestrator.is_healthy()
    return {
        "status": "healthy" if orchestrator_healthy else "unhealthy",
        "connected": orchestrator.connection is not None
        and not orchestrator.connection.is_closed,
        "has_channel": orchestrator.channel is not None,
        "download_queue": orchestrator.download_queue_name,
        "translation_queue": orchestrator.translation_queue_name,
    }


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
            status_code=status.HTTP_404_NOT_FOUND, detail="Subtitle job not found"
        )

    # Get event history
    events = await redis_client.get_job_events(job_id)

    if not events:
        # Job exists but no events yet
        return {
            "job_id": str(job_id),
            "event_count": 0,
            "events": [],
            "message": "No events recorded for this job yet",
        }

    return {"job_id": str(job_id), "event_count": len(events), "events": events}


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


@app.post(
    "/subtitles/download",
    response_model=SubtitleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enqueue_subtitle_download_job(request: SubtitleRequestCreate):
    """
    Create and enqueue a new subtitle download job.

    Returns the created job with PENDING status.
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
            await publish_job_failure_and_raise_http_error(
                subtitle_response.id,
                "Failed to enqueue download task",
            )

        logger.info(f"Subtitle download job created: {subtitle_response.id}")
        return subtitle_response

    except HTTPException:
        raise
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
async def enqueue_subtitle_translation_job(request: SubtitleTranslateRequest):
    """
    Create and enqueue a new subtitle translation job.

    The translator worker will read the file from the provided path
    and send its content to OpenAI API for translation.

    Returns the created job with PENDING status.
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
            f"Translation job for file: {request.subtitle_path} -> {request.target_language}"
        )

        # Enqueue translation task - the worker will read the file and send to OpenAI
        success = await orchestrator.enqueue_translation_task(
            subtitle_response.id,
            request.subtitle_path,
            request.source_language,
            request.target_language,
        )

        if not success:
            await publish_job_failure_and_raise_http_error(
                subtitle_response.id,
                "Failed to enqueue translation task",
            )

        logger.info(f"Translation job created: {subtitle_response.id}")
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

    progress = calculate_job_progress_percentage(subtitle)

    return SubtitleStatusResponse(
        id=subtitle.id,
        status=subtitle.status.value,
        progress=progress,
        message=f"Status: {subtitle.status.value}",
    )


@app.post("/webhooks/jellyfin", response_model=WebhookAcknowledgement)
async def process_jellyfin_media_event(payload: JellyfinWebhookPayload):
    """
    Process Jellyfin webhook event and create subtitle download job.

    Only processes library.item.added and library.item.updated events
    for Movie and Episode items.
    """
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

        # Convert plain file paths to file:// URLs if needed
        if video_url and not video_url.startswith(("http://", "https://", "file://")):
            video_url = f"file://{video_url}"

        # Create subtitle request with default settings
        subtitle_request = SubtitleRequestCreate(
            video_url=video_url,
            video_title=payload.item_name,
            language=settings.subtitle_desired_language,
            target_language=None,
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
            # Publish failure event - Consumer will update status
            # Note: We can't use publish_job_failure_and_raise_http_error here
            # because we need to return a WebhookAcknowledgement, not raise HTTPException
            from common.event_publisher import event_publisher
            from common.schemas import EventType, SubtitleEvent
            from common.utils import DateTimeUtils

            failure_event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={"error_message": "Failed to enqueue download task"},
            )
            await event_publisher.publish_event(failure_event)
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


@app.post("/scan", status_code=status.HTTP_202_ACCEPTED)
async def trigger_manual_scan():
    """
    Trigger a manual scan of the media library.

    This sends a request to the Scanner service to initiate a full scan
    of the configured media directory.
    """
    import httpx

    try:
        scanner_url = f"http://{settings.scanner_webhook_host}:{settings.scanner_webhook_port}/scan"
        logger.info(f"Triggering manual scan via {scanner_url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(scanner_url, timeout=5.0)

        if response.status_code != 200:
            logger.error(f"Scanner returned error: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Scanner service returned error: {response.status_code}",
            )

        return {"status": "accepted", "message": "Manual scan initiated"}

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to scanner service: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scanner service is unreachable",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering manual scan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
