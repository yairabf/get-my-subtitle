"""Helper functions for Manager service endpoints and lifecycle management."""

import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from redis import asyncio as redis

from common.config import settings
from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils, StatusProgressCalculator
from manager.event_consumer import event_consumer
from manager.orchestrator import orchestrator
from manager.schemas import SubtitleResponse

logger = logging.getLogger(__name__)


async def publish_job_failure_and_raise_http_error(
    job_id: UUID,
    error_message: str,
    http_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> None:
    """
    Publish a JOB_FAILED event and raise an HTTPException.
    
    This is a pure function that publishes an event and raises an exception.
    It has no side effects beyond event publication and exception raising.
    
    Args:
        job_id: ID of the failed job
        error_message: Human-readable error message
        http_status_code: HTTP status code to return (defaults to 500)
        
    Raises:
        HTTPException: Always raises with the provided status code and message
    """
    failure_event = SubtitleEvent(
        event_type=EventType.JOB_FAILED,
        job_id=job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="manager",
        payload={"error_message": error_message},
    )
    await event_publisher.publish_event(failure_event)
    
    raise HTTPException(
        status_code=http_status_code,
        detail=error_message,
    )


def calculate_job_progress_percentage(subtitle: SubtitleResponse) -> int:
    """
    Calculate progress percentage for a subtitle job based on its current status.
    
    Returns a value between 0-100 representing completion percentage.
    
    Args:
        subtitle: SubtitleResponse object with current status
        
    Returns:
        Progress percentage as integer (0-100)
    """
    progress_mapping = StatusProgressCalculator.get_subtitle_status_progress_mapping()
    return StatusProgressCalculator.calculate_progress_for_status(
        subtitle.status, progress_mapping
    )


async def attempt_redis_connection_on_startup() -> bool:
    """
    Attempt to connect to Redis during application startup.
    
    Uses a quick timeout (3s) to avoid blocking startup.
    Background health checks will continue attempting connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        redis_client.client = await asyncio.wait_for(
            redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            ),
            timeout=3.0,
        )
        await asyncio.wait_for(redis_client.client.ping(), timeout=2.0)
        redis_client.connected = True
        logger.info("✅ Redis connected successfully")
        return True
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Redis not available during startup: {e}")
        logger.info(
            "Service will start anyway - connections will be established via background health checks"
        )
        redis_client.connected = False
        return False


async def attempt_event_publisher_connection_on_startup() -> bool:
    """
    Attempt to connect event publisher during application startup.
    
    Uses reduced retries (3 max, 2s delays) to avoid blocking startup.
    
    Returns:
        True if connection successful, False otherwise
    """
    logger.info("Connecting event publisher...")
    try:
        await asyncio.wait_for(
            event_publisher.connect(max_retries=3, retry_delay=2.0), timeout=15.0
        )
        logger.info("✅ Event publisher connected successfully")
        return True
    except asyncio.TimeoutError:
        logger.warning(
            "Event publisher connection timed out during startup (will retry in background)"
        )
        return False
    except Exception as e:
        logger.warning(
            f"Event publisher connection failed: {e} (will retry in background)"
        )
        return False


async def attempt_orchestrator_connection_on_startup() -> bool:
    """
    Attempt to connect orchestrator during application startup.
    
    Uses reduced retries (3 max, 2s delays) to avoid blocking startup.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        await asyncio.wait_for(
            orchestrator.connect(max_retries=3, retry_delay=2.0), timeout=15.0
        )
        logger.info("✅ Orchestrator connected successfully")
        return True
    except asyncio.TimeoutError:
        logger.warning(
            "Orchestrator connection timed out during startup (will retry in background)"
        )
        return False
    except Exception as e:
        logger.warning(
            f"Orchestrator connection failed: {e} (will retry in background)"
        )
        return False


async def attempt_event_consumer_connection_on_startup() -> bool:
    """
    Attempt to connect event consumer during application startup.
    
    Uses reduced retries (3 max, 2s delays) to avoid blocking startup.
    
    Returns:
        True if connection successful, False otherwise
    """
    logger.info("Starting event consumer for SUBTITLE_REQUESTED events...")
    try:
        await asyncio.wait_for(
            event_consumer.connect(max_retries=3, retry_delay=2.0), timeout=15.0
        )
        logger.info("✅ Event consumer connected successfully")
        return True
    except asyncio.TimeoutError:
        logger.warning(
            "Event consumer connection timed out during startup (will retry in background)"
        )
        return False
    except Exception as e:
        logger.warning(
            f"Event consumer connection failed: {e} (will retry in background)"
        )
        return False


async def initialize_all_connections_on_startup() -> None:
    """
    Initialize all external connections during application startup.
    
    Uses quick connection attempts that don't block startup indefinitely.
    Background reconnection continues via health checks.
    """
    logger.info("Attempting quick connections to dependencies...")
    
    await attempt_redis_connection_on_startup()
    await attempt_event_publisher_connection_on_startup()
    await attempt_orchestrator_connection_on_startup()
    await attempt_event_consumer_connection_on_startup()


async def start_event_consumer_if_ready() -> Optional[asyncio.Task]:
    """
    Start event consumer task if connection is ready.
    
    Returns:
        asyncio.Task if consumer started, None otherwise
    """
    # Verify consumer is connected before starting
    if event_consumer.queue is None or event_consumer.channel is None:
        logger.warning(
            "Event consumer not properly connected yet, will retry connection via health checks"
        )
        logger.info("Consumer will start when RabbitMQ connection is established")
        return None
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
        return consumer_task


async def shutdown_all_connections(consumer_task: Optional[asyncio.Task]) -> None:
    """
    Gracefully shutdown all connections and stop background tasks.
    
    Args:
        consumer_task: Optional event consumer task to stop
    """
    logger.info("Shutting down subtitle management API...")

    # Stop event consumer
    if consumer_task:
        logger.info("Stopping event consumer...")
        event_consumer.stop()
        try:
            await asyncio.wait_for(consumer_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Event consumer task did not stop gracefully, cancelling..."
            )
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

