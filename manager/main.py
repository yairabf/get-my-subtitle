"""FastAPI application for the subtitle management system."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, List
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from common.schemas import SubtitleStatus
from common.config import settings
from common.redis_client import redis_client
from common.logging_config import setup_service_logging
from common.utils import StatusProgressCalculator
from manager.schemas import (
    SubtitleRequestCreate,
    SubtitleResponse,
    SubtitleStatusResponse,
    QueueStatusResponse,
    HealthResponse,
)
from manager.orchestrator import orchestrator

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


@app.post(
    "/subtitles/request",
    response_model=SubtitleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_subtitle_processing(request: SubtitleRequestCreate):
    """Request subtitle processing for a video."""
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

        logger.info(f"Subtitle request created: {subtitle_response.id}")
        return subtitle_response

    except Exception as e:
        logger.error(f"Error processing subtitle request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@app.get("/subtitles/{request_id}", response_model=SubtitleResponse)
async def get_subtitle_status(request_id: UUID):
    """Get the status of a subtitle request."""
    job = await redis_client.get_job(request_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subtitle request not found"
        )

    return job


@app.get("/subtitles", response_model=List[SubtitleResponse])
async def list_subtitle_requests():
    """List all subtitle requests."""
    jobs = await redis_client.list_jobs()
    return jobs


@app.get("/subtitles/{request_id}/status", response_model=SubtitleStatusResponse)
async def get_subtitle_status_simple(request_id: UUID):
    """Get simplified status of a subtitle request."""
    subtitle = await redis_client.get_job(request_id)

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


@app.post("/subtitles/{request_id}/download", response_model=Dict[str, str])
async def download_subtitles(request_id: UUID):
    """Download processed subtitles."""
    subtitle = await redis_client.get_job(request_id)

    if not subtitle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subtitle request not found"
        )

    if subtitle.status != SubtitleStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subtitles not ready. Current status: {subtitle.status.value}",
        )

    if not subtitle.download_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Download URL not available"
        )

    return {
        "download_url": subtitle.download_url,
        "message": "Subtitles ready for download",
    }


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
