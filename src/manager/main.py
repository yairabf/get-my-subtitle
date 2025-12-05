"""FastAPI application for the subtitle management system."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from redis import asyncio as redis

from common.config import settings
from common.event_publisher import event_publisher
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils, StatusProgressCalculator
from manager.event_consumer import event_consumer
from manager.health import check_health
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

    # Quick connection attempts during startup (don't block for too long)
    # Background reconnection will continue via health checks and ensure_connected
    logger.info("Attempting quick connections to dependencies...")

    # Try Redis with a simple single attempt (don't wait for full retry logic)
    try:
        # Just try to create connection without retries
        redis_client.client = await asyncio.wait_for(
            redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            ),
            timeout=3.0,
        )
        # Quick ping test
        await asyncio.wait_for(redis_client.client.ping(), timeout=2.0)
        redis_client.connected = True
        logger.info("✅ Redis connected successfully")
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Redis not available during startup: {e}")
        logger.info(
            "Service will start anyway - connections will be established via background health checks"
        )
        redis_client.connected = False

    # Try Event Publisher with fewer retries (max 3 attempts, 2 second delays)
    logger.info("Connecting event publisher...")
    try:
        await asyncio.wait_for(
            event_publisher.connect(max_retries=3, retry_delay=2.0), timeout=15.0
        )
        logger.info("✅ Event publisher connected successfully")
    except asyncio.TimeoutError:
        logger.warning(
            "Event publisher connection timed out during startup (will retry in background)"
        )
    except Exception as e:
        logger.warning(
            f"Event publisher connection failed: {e} (will retry in background)"
        )

    # Try Orchestrator with fewer retries
    try:
        await asyncio.wait_for(
            orchestrator.connect(max_retries=3, retry_delay=2.0), timeout=15.0
        )
        logger.info("✅ Orchestrator connected successfully")
    except asyncio.TimeoutError:
        logger.warning(
            "Orchestrator connection timed out during startup (will retry in background)"
        )
    except Exception as e:
        logger.warning(
            f"Orchestrator connection failed: {e} (will retry in background)"
        )

    # Try Event Consumer with fewer retries
    logger.info("Starting event consumer for SUBTITLE_REQUESTED events...")
    try:
        await asyncio.wait_for(
            event_consumer.connect(max_retries=3, retry_delay=2.0), timeout=15.0
        )
        logger.info("✅ Event consumer connected successfully")
    except asyncio.TimeoutError:
        logger.warning(
            "Event consumer connection timed out during startup (will retry in background)"
        )
    except Exception as e:
        logger.warning(
            f"Event consumer connection failed: {e} (will retry in background)"
        )

    # Verify consumer is connected before starting
    if event_consumer.queue is None or event_consumer.channel is None:
        logger.warning(
            "Event consumer not properly connected yet, will retry connection via health checks"
        )
        logger.info("Consumer will start when RabbitMQ connection is established")
    else:
        logger.info("Event consumer connected successfully, starting consumption...")
        consumer_task = asyncio.create_task(event_consumer.start_consuming())

        # Add error handler to catch task exceptions
        def handle_task_exception(task):
            try:
                task.result()  # This will raise if task failed
            except Exception as e:
                logger.error(f"Event consumer task failed: {e}", exc_info=True)

        consumer_task.add_done_callback(handle_task_exception)
        logger.info(f"Event consumer task started: {consumer_task}")

    logger.info("API startup complete")

    yield

    # Shutdown
    logger.info("Shutting down subtitle management API...")

    # Stop event consumer
    if consumer_task:
        logger.info("Stopping event consumer...")
        event_consumer.stop()
        try:
            await asyncio.wait_for(consumer_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Event consumer task did not stop gracefully, cancelling...")
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass

    await event_consumer.disconnect()
    await orchestrator.disconnect()
    await event_publisher.disconnect()
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
            # Publish failure event - Consumer will update status
            failure_event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={"error_message": "Failed to enqueue download task"},
            )
            await event_publisher.publish_event(failure_event)
            # Set status in response object for API response (not saved to Redis)
            subtitle_response.status = SubtitleStatus.FAILED
            subtitle_response.error_message = "Failed to enqueue download task"
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
            # Publish failure event - Consumer will update status
            failure_event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={"error_message": "Failed to enqueue translation task"},
            )
            await event_publisher.publish_event(failure_event)
            # Set status in response object for API response (not saved to Redis)
            subtitle_response.status = SubtitleStatus.FAILED
            subtitle_response.error_message = "Failed to enqueue translation task"
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
            failure_event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={"error_message": "Failed to enqueue download task"},
            )
            await event_publisher.publish_event(failure_event)
            # Note: Status will be updated by Consumer, not directly here
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
