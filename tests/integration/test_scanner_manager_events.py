"""Integration tests for Scanner → Manager event flow via RabbitMQ.

Note: These tests require actual RabbitMQ and Redis services to be running.
In CI, these services should be started via docker-compose before running tests.
"""

import asyncio
import logging
import subprocess
from uuid import uuid4

import aio_pika
import httpx
import pytest
import pytest_asyncio

logger = logging.getLogger(__name__)

from common.config import settings
from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleResponse, SubtitleStatus
from common.utils import DateTimeUtils
from manager.orchestrator import orchestrator


@pytest_asyncio.fixture(scope="function")
async def setup_services():
    """
    Set up Redis, RabbitMQ, and orchestrator for testing.

    This fixture:
    1. Ensures Manager and Consumer services are ready
    2. Purges the Manager's queue to ensure test isolation
    3. Connects to all required services
    4. Verifies connections are working
    5. Provides diagnostics about queue status
    """
    # Ensure services are ready (restart if needed)
    logger.info("Ensuring Manager and Consumer services are ready...")
    services_ready = await ensure_services_ready()
    if not services_ready:
        pytest.skip(
            "Manager and Consumer services are not ready. "
            "Please ensure Docker services are running: "
            "docker-compose -f docker-compose.integration.yml up -d"
        )

    # Purge Manager's queue to clear backlog from previous tests
    # This is critical for test isolation when running the full suite
    logger.info("Purging Manager queue for test isolation...")
    await purge_manager_queue()

    # Check queue status before test
    initial_count = await get_queue_message_count("manager.subtitle.requests")
    if initial_count > 0:
        logger.warning(f"Manager queue still has {initial_count} messages after purge")

    # Verify Manager consumer is still healthy after purge
    consumer_health = await check_manager_consumer_health()
    logger.info(f"Manager consumer health: {consumer_health}")

    if not (
        consumer_health.get("status") == "consuming"
        and consumer_health.get("connected")
    ):
        logger.warning(
            "Manager consumer not healthy after setup, attempting one more restart..."
        )
        await ensure_services_ready(max_retries=1)

    # Connect services with timeout
    try:
        await asyncio.wait_for(redis_client.connect(), timeout=5.0)
        await asyncio.wait_for(orchestrator.connect(), timeout=5.0)
        # Ensure event_publisher is connected and stays connected
        if event_publisher.connection is None or event_publisher.connection.is_closed:
            await asyncio.wait_for(
                event_publisher.connect(max_retries=10, retry_delay=1.0), timeout=10.0
            )
    except asyncio.TimeoutError:
        pytest.fail(
            "Timeout connecting to services. Ensure RabbitMQ and Redis are running."
        )

    # Verify actual connections (not mock mode)
    if event_publisher.connection is None or event_publisher.connection.is_closed:
        pytest.skip(
            "Integration tests require RabbitMQ and Redis services. "
            "Services are in mock mode - connections failed."
        )

    # Verify event_publisher exchange is declared
    if event_publisher.exchange is None:
        # Reconnect to ensure exchange is declared
        await event_publisher.connect(max_retries=5, retry_delay=1.0)

    # Small delay to let services stabilize after connection
    await asyncio.sleep(1.0)

    yield

    # Cleanup: Purge queues after test to prevent backlog
    logger.info("Cleaning up queues after test...")
    await purge_manager_queue()

    # Don't disconnect event_publisher - it's a global instance and other tests might need it
    # Only disconnect orchestrator and redis_client which are test-specific
    try:
        await asyncio.wait_for(orchestrator.disconnect(), timeout=3.0)
        # Keep redis_client connected for other tests
        # await asyncio.wait_for(redis_client.disconnect(), timeout=3.0)
    except asyncio.TimeoutError:
        # Log but don't fail on disconnect timeout
        pass


# Removed ensure_consumer_healthy and consumer fixtures
# Tests now rely on Docker services from docker-compose.integration.yml
# No competing test consumers - Manager service in Docker handles SUBTITLE_REQUESTED events


# Removed event_consumer_service fixture - Consumer service runs in Docker


async def purge_manager_queue() -> None:
    """
    Purge the Manager's event queue to clear backlog from previous tests.
    This helps ensure test isolation when running the full test suite.
    """
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        queue = await channel.declare_queue("manager.subtitle.requests", durable=True)
        purged_count = await queue.purge()
        logger.info(
            f"Purged {purged_count} messages from manager.subtitle.requests queue"
        )
        await channel.close()
        await connection.close()
    except Exception as e:
        logger.warning(f"Failed to purge manager queue: {e}. Continuing anyway.")


async def get_queue_message_count(queue_name: str) -> int:
    """
    Get the current message count for a RabbitMQ queue.

    Args:
        queue_name: Name of the queue to check

    Returns:
        Number of messages in the queue, or -1 if error
    """
    try:
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True)
        message_count = queue.declaration_result.message_count
        await channel.close()
        await connection.close()
        return message_count
    except Exception as e:
        logger.warning(f"Failed to get message count for queue {queue_name}: {e}")
        return -1


async def check_manager_consumer_health() -> dict:
    """
    Check the health status of the Manager's event consumer.

    Returns:
        Dictionary with consumer health information
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://localhost:8000/health/consumer")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.warning(f"Could not check Manager consumer health: {e}")
    return {"status": "unknown", "connected": False}


async def ensure_services_ready(max_retries: int = 3) -> bool:
    """
    Ensure Manager and Consumer services are ready and consuming events.
    Restarts them if they're not healthy.

    Args:
        max_retries: Maximum number of restart attempts

    Returns:
        True if services are ready, False otherwise
    """
    for attempt in range(max_retries):
        # Check Manager consumer health
        manager_health = await check_manager_consumer_health()
        manager_ready = (
            manager_health.get("status") == "consuming"
            and manager_health.get("connected") is True
        )

        if manager_ready:
            logger.info(f"✅ Manager consumer is ready (attempt {attempt + 1})")
            return True

        logger.warning(
            f"⚠️ Manager consumer not ready (attempt {attempt + 1}/{max_retries}): {manager_health}"
        )

        if attempt < max_retries - 1:
            # Restart services
            logger.info("Restarting Manager and Consumer services...")
            try:
                subprocess.run(
                    [
                        "docker-compose",
                        "-f",
                        "docker-compose.integration.yml",
                        "restart",
                        "manager",
                        "consumer",
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                logger.info("Services restarted, waiting for them to be ready...")
                await asyncio.sleep(8)  # Wait for services to start
            except Exception as e:
                logger.warning(f"Failed to restart services: {e}")
                await asyncio.sleep(2)

    logger.error("❌ Services failed to become ready after all retries")
    return False


async def wait_for_event_in_redis(
    job_id, event_type: str, max_wait: int = 60, poll_interval: float = 0.5
) -> bool:
    """
    Wait for a specific event type to appear in Redis event history.

    Args:
        job_id: UUID of the job
        event_type: Event type to wait for (e.g., "subtitle.download.requested")
        max_wait: Maximum time to wait in seconds
        poll_interval: Time between polls in seconds

    Returns:
        True if event was found, False if timeout
    """
    for attempt in range(int(max_wait / poll_interval)):
        await asyncio.sleep(poll_interval)
        events = await redis_client.get_job_events(job_id)
        if events:
            event_types = [e.get("event_type", "unknown") for e in events]
            if event_type in event_types:
                return True
    return False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scanner_publishes_manager_consumes_end_to_end(setup_services):
    """
    Test end-to-end event flow using Docker services from docker-compose.integration.yml:
    1. Scanner creates job in Redis and publishes SUBTITLE_REQUESTED event
    2. Manager service (Docker) consumes event from RabbitMQ
    3. Manager enqueues download task and publishes DOWNLOAD_REQUESTED event
    4. Consumer service (Docker) processes DOWNLOAD_REQUESTED and updates status to DOWNLOAD_QUEUED

    This test verifies the full event-driven workflow between services.
    """
    job_id = uuid4()
    # Use unique video title to avoid duplicate detection
    unique_video_title = f"Integration Test Movie {job_id}"

    # Create the job in Redis first (as Scanner would do via SubtitleResponse)
    job = SubtitleResponse(
        id=job_id,
        video_url=f"/media/movies/integration_test_{job_id}.mp4",
        video_title=unique_video_title,
        language="en",
        target_language="es",
        status=SubtitleStatus.PENDING,
        source="scanner",
    )
    await redis_client.save_job(job)
    logger.info(f"Created job {job_id} in Redis with status PENDING")

    # Create a SUBTITLE_REQUESTED event (as Scanner would publish)
    subtitle_requested_event = SubtitleEvent(
        event_type=EventType.SUBTITLE_REQUESTED,
        job_id=job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="scanner",
        payload={
            "video_url": f"/media/movies/integration_test_{job_id}.mp4",
            "video_title": unique_video_title,
            "language": "en",
            "target_language": "es",
            "preferred_sources": ["opensubtitles"],
            "auto_translate": True,
        },
    )

    # Ensure event_publisher is connected and exchange is declared
    if not event_publisher.connection or event_publisher.connection.is_closed:
        await event_publisher.connect(max_retries=10, retry_delay=1.0)
    if event_publisher.exchange is None:
        # Force reconnection to ensure exchange is declared
        await event_publisher.disconnect()
        await event_publisher.connect(max_retries=10, retry_delay=1.0)

    # Publish the event (Manager service in Docker will consume it)
    success = await event_publisher.publish_event(subtitle_requested_event)
    assert (
        success is True
    ), "Failed to publish event - event_publisher may not be connected"
    logger.info(f"✅ Published SUBTITLE_REQUESTED event for job {job_id}")

    # Check queue status after publishing
    queue_count = await get_queue_message_count("manager.subtitle.requests")
    logger.info(f"Manager queue message count after publishing: {queue_count}")

    # Check Manager consumer health
    consumer_health = await check_manager_consumer_health()
    logger.info(f"Manager consumer status: {consumer_health}")

    # Give services a moment to start processing
    # Reduced delay since we're now purging queues between tests
    await asyncio.sleep(3.0)

    # Wait for Docker services to process event
    # Manager (Docker) consumes SUBTITLE_REQUESTED → publishes DOWNLOAD_REQUESTED
    # Consumer (Docker) consumes DOWNLOAD_REQUESTED → updates Redis status
    max_wait = 120  # seconds (increased for full test suite with queue backlog)
    poll_interval = 0.5  # seconds

    # Wait for status to be updated to DOWNLOAD_QUEUED
    # This is the primary indicator that the full flow worked
    status_updated = False
    for attempt in range(int(max_wait / poll_interval)):
        await asyncio.sleep(poll_interval)
        job = await redis_client.get_job(job_id)

        if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
            logger.info(
                f"✅ Job processed successfully after {attempt * poll_interval}s"
            )
            status_updated = True
            break

        # Log progress every 20 attempts (every 10 seconds) with diagnostics
        if attempt % 20 == 0:
            queue_count = await get_queue_message_count("manager.subtitle.requests")
            events = await redis_client.get_job_events(job_id) if job else []
            event_types = (
                [e.get("event_type", "unknown") for e in events] if events else []
            )
            logger.info(
                f"⏳ Waiting... Status: {job.status if job else 'None'} "
                f"(attempt {attempt}, {attempt * poll_interval:.1f}s). "
                f"Queue messages: {queue_count}. Events: {event_types}"
            )

    if not status_updated:
        # Test failed - get final state and check event history
        final_job = await redis_client.get_job(job_id)
        events = await redis_client.get_job_events(job_id) if final_job else []
        event_types = [e.get("event_type", "unknown") for e in events] if events else []

        # Check if Manager at least received the event (even if not fully processed)
        # This helps diagnose if the issue is event publishing or processing
        manager_received = (
            any(
                "subtitle.download.requested" in str(e)
                or "DOWNLOAD_REQUESTED" in str(e)
                for e in event_types
            )
            if events
            else False
        )

        error_msg = (
            f"Timeout: Job not processed after {max_wait}s. "
            f"Final status: {final_job.status if final_job else 'None'}, job_id: {job_id}. "
            f"Events received: {event_types}. "
            f"Manager received DOWNLOAD_REQUESTED: {manager_received}"
        )

        # If Manager received the event but status wasn't updated, it might just be slow
        # In full test suite, this can happen due to queue backlog
        if (
            manager_received
            and final_job
            and final_job.status == SubtitleStatus.PENDING
        ):
            logger.warning(
                f"Manager received event but status not updated - likely queue backlog. "
                f"Consider running these tests individually or with longer timeouts."
            )

        pytest.fail(error_msg)

    # Verify the job was updated correctly
    job = await redis_client.get_job(job_id)
    assert job is not None, "Job should exist in Redis"
    assert job.status == SubtitleStatus.DOWNLOAD_QUEUED
    assert job.video_url == f"/media/movies/integration_test_{job_id}.mp4"
    assert job.video_title == unique_video_title
    assert job.language == "en"
    assert job.target_language == "es"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_events_processed_sequentially(setup_services):
    """
    Test that multiple SUBTITLE_REQUESTED events are processed in order by Docker services.
    Verifies Manager and Consumer can handle multiple events correctly.
    """
    job_ids = [uuid4() for _ in range(3)]
    events = []

    # Create multiple jobs and events
    for i, job_id in enumerate(job_ids):
        # Use unique video title to avoid duplicate detection
        unique_video_title = f"Test Movie {job_id}"
        # Create job in Redis
        job = SubtitleResponse(
            id=job_id,
            video_url=f"/media/movies/test_movie_{job_id}.mp4",
            video_title=unique_video_title,
            language="en",
            target_language="es",
            status=SubtitleStatus.PENDING,
            source="scanner",
        )
        await redis_client.save_job(job)

        # Create event
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": f"/media/movies/test_movie_{job_id}.mp4",
                "video_title": unique_video_title,
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
                "auto_translate": True,
            },
        )
        events.append(event)

    # Give Manager service time to be ready (it's running in Docker)
    # No need to check health - rely on Docker health checks and longer delays
    await asyncio.sleep(2.0)

    # Ensure event_publisher is connected and exchange is declared
    if not event_publisher.connection or event_publisher.connection.is_closed:
        await event_publisher.connect(max_retries=10, retry_delay=1.0)
    if event_publisher.exchange is None:
        # Force reconnection to ensure exchange is declared
        await event_publisher.disconnect()
        await event_publisher.connect(max_retries=10, retry_delay=1.0)

    # Publish all events (Manager service in Docker will consume them)
    for event in events:
        success = await event_publisher.publish_event(event)
        assert success is True, f"Failed to publish event for job {event.job_id}"
        logger.info(f"✅ Published SUBTITLE_REQUESTED event for job {event.job_id}")
        # Small delay between events to avoid overwhelming the queue
        await asyncio.sleep(0.5)

    # Check queue status after publishing
    queue_count = await get_queue_message_count("manager.subtitle.requests")
    logger.info(
        f"Manager queue message count after publishing all events: {queue_count}"
    )

    # Give services a moment to start processing
    await asyncio.sleep(3.0)  # Reduced delay since queues are purged between tests

    # Wait for Docker services to process all events
    max_wait = 120  # seconds (increased for full test suite with multiple events and queue backlog)
    poll_interval = 0.5  # seconds

    all_processed = False
    last_processed_count = 0
    no_progress_count = 0

    for attempt in range(int(max_wait / poll_interval)):
        await asyncio.sleep(poll_interval)

        # Check if all jobs were processed
        processed_count = 0
        for job_id in job_ids:
            job = await redis_client.get_job(job_id)
            if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
                processed_count += 1

        # Check if we made progress
        if processed_count > last_processed_count:
            logger.info(f"Progress: {processed_count}/{len(job_ids)} jobs processed")
            no_progress_count = 0
            last_processed_count = processed_count
        else:
            no_progress_count += 1

        if processed_count == len(job_ids):
            all_processed = True
            logger.info(
                f"✅ All jobs processed successfully after {attempt * poll_interval}s"
            )
            break

        # If no progress for 10 attempts (5 seconds), log status for debugging
        if no_progress_count == 10:
            job_statuses = {}
            for job_id in job_ids:
                job = await redis_client.get_job(job_id)
                job_statuses[job_id] = job.status if job else "None"
            logger.info(
                f"⏳ Waiting... Processed: {processed_count}/{len(job_ids)}. "
                f"Statuses: {job_statuses}"
            )
            no_progress_count = 0  # Reset counter

    if not all_processed:
        # Get status of all jobs for debugging
        job_statuses = {}
        for job_id in job_ids:
            job = await redis_client.get_job(job_id)
            job_statuses[job_id] = job.status if job else "None"
        pytest.fail(
            f"Timeout: Not all events processed after {max_wait}s. "
            f"Processed: {processed_count}/{len(job_ids)}. "
            f"Job statuses: {job_statuses}"
        )

    # Verify all jobs were created correctly
    for job_id in job_ids:
        job = await redis_client.get_job(job_id)
        assert job is not None
        assert job.status == SubtitleStatus.DOWNLOAD_QUEUED
        assert job.video_title == f"Test Movie {job_id}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_consumer_ignores_non_subtitle_requested_events(setup_services):
    """
    Test that Manager service only processes SUBTITLE_REQUESTED events and ignores others.
    """
    job_id = uuid4()

    # Create a MEDIA_FILE_DETECTED event (should be ignored by Manager)
    media_detected_event = SubtitleEvent(
        event_type=EventType.MEDIA_FILE_DETECTED,
        job_id=job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="scanner",
        payload={
            "file_path": "/media/movies/test.mp4",
            "video_title": "Test",
            "language": "en",
        },
    )

    # Publish the event
    await event_publisher.publish_event(media_detected_event)

    # Wait a bit to ensure event would be processed if it was going to be
    await asyncio.sleep(2.0)

    # Verify job was NOT created (event should be ignored)
    job = await redis_client.get_job(job_id)
    assert job is None, "Job should not exist for MEDIA_FILE_DETECTED event"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_consumer_handles_malformed_events_gracefully(setup_services):
    """
    Test that Manager service handles malformed events without crashing.
    """
    job_id = uuid4()

    # Create event with missing required fields
    incomplete_event = SubtitleEvent(
        event_type=EventType.SUBTITLE_REQUESTED,
        job_id=job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="scanner",
        payload={
            "video_url": "/media/movies/test.mp4",
            # Missing video_title and language (required fields)
        },
    )

    # Publish the malformed event
    await event_publisher.publish_event(incomplete_event)

    # Wait for processing (malformed event should be handled gracefully)
    await asyncio.sleep(2.0)

    # Verify Manager is still running by publishing and processing a valid event
    valid_job_id = uuid4()
    unique_video_title = f"Valid Test {valid_job_id}"
    valid_job = SubtitleResponse(
        id=valid_job_id,
        video_url=f"/media/movies/test_{valid_job_id}.mp4",
        video_title=unique_video_title,
        language="en",
        status=SubtitleStatus.PENDING,
        source="test",
    )
    await redis_client.save_job(valid_job)

    valid_event = SubtitleEvent(
        event_type=EventType.SUBTITLE_REQUESTED,
        job_id=valid_job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="test",
        payload={
            "video_url": f"/media/movies/test_{valid_job_id}.mp4",
            "video_title": unique_video_title,
            "language": "en",
            "target_language": "es",
            "preferred_sources": ["opensubtitles"],
        },
    )
    # Ensure event_publisher is connected and exchange is declared
    if not event_publisher.connection or event_publisher.connection.is_closed:
        await event_publisher.connect(max_retries=10, retry_delay=1.0)
    if event_publisher.exchange is None:
        # Force reconnection to ensure exchange is declared
        await event_publisher.disconnect()
        await event_publisher.connect(max_retries=10, retry_delay=1.0)

    success = await event_publisher.publish_event(valid_event)
    assert success is True, "Failed to publish valid event"

    # Check queue status
    queue_count = await get_queue_message_count("manager.subtitle.requests")
    logger.info(
        f"Manager queue message count after publishing valid event: {queue_count}"
    )

    # Give services a moment to start processing
    await asyncio.sleep(3.0)  # Reduced delay since queues are purged between tests

    # Wait for valid event to be processed (increased timeout for full test suite)
    max_wait = 90  # seconds (increased for full test suite with queue backlog)
    poll_interval = 0.5  # seconds
    processed = False

    for attempt in range(int(max_wait / poll_interval)):
        await asyncio.sleep(poll_interval)
        job = await redis_client.get_job(valid_job_id)
        if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
            logger.info(
                f"✅ Valid event processed successfully after {attempt * poll_interval}s"
            )
            processed = True
            break

    # Verify Manager processed the valid event (proving it didn't crash from malformed event)
    job = await redis_client.get_job(valid_job_id)
    assert job is not None, "Manager should still be running and processing events"
    if not processed:
        # Get event history for debugging
        events = await redis_client.get_job_events(valid_job_id) if job else []
        event_types = [e.get("event_type", "unknown") for e in events] if events else []
        pytest.fail(
            f"Valid event not processed after {max_wait}s. "
            f"Final status: {job.status if job else 'None'}. "
            f"Events received: {event_types}"
        )
    assert (
        job.status == SubtitleStatus.DOWNLOAD_QUEUED
    ), "Valid event should be processed"
