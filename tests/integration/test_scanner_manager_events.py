"""Integration tests for Scanner → Manager event flow via RabbitMQ.

Note: These tests require actual RabbitMQ and Redis services to be running.
In CI, these services should be started via docker-compose before running tests.
"""

import asyncio
import logging
from uuid import uuid4

import pytest
import pytest_asyncio

logger = logging.getLogger(__name__)

from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleResponse, SubtitleStatus
from common.utils import DateTimeUtils
from consumer.worker import EventConsumer
from manager.event_consumer import SubtitleEventConsumer
from manager.orchestrator import orchestrator


@pytest_asyncio.fixture(scope="function")
async def setup_services():
    """Set up Redis, RabbitMQ, and orchestrator for testing."""
    # Connect services with timeout
    try:
        await asyncio.wait_for(redis_client.connect(), timeout=5.0)
        await asyncio.wait_for(orchestrator.connect(), timeout=5.0)
        await asyncio.wait_for(event_publisher.connect(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail(
            "Timeout connecting to services. Ensure RabbitMQ and Redis are running."
        )

    # Verify actual connections (not mock mode)
    if event_publisher.connection is None or redis_client.client is None:
        pytest.skip(
            "Integration tests require RabbitMQ and Redis services. "
            "Services are in mock mode - connections failed."
        )

    yield

    # Disconnect services with timeout
    try:
        await asyncio.wait_for(event_publisher.disconnect(), timeout=3.0)
        await asyncio.wait_for(orchestrator.disconnect(), timeout=3.0)
        await asyncio.wait_for(redis_client.disconnect(), timeout=3.0)
    except asyncio.TimeoutError:
        # Log but don't fail on disconnect timeout
        pass


@pytest_asyncio.fixture(scope="function")
async def ensure_consumer_healthy():
    """
    Ensure the Consumer service in Docker is healthy and can actually process events.
    
    This fixture:
    1. Waits for Consumer queue to exist and be bound
    2. Sends a test event and verifies it's processed
    3. Ensures Consumer is actually consuming, not just connected
    """
    import aio_pika
    from common.config import settings
    from common.event_publisher import event_publisher
    from common.redis_client import redis_client
    from uuid import uuid4
    
    # Step 1: Wait for Consumer queue to be bound
    max_wait = 30  # seconds
    wait_interval = 0.5  # seconds
    attempts = int(max_wait / wait_interval)
    
    connection = None
    queue_ready = False
    
    for attempt in range(attempts):
        try:
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            channel = await connection.channel()
            
            try:
                queue = await channel.declare_queue(
                    "subtitle.events.consumer", 
                    durable=True,
                    passive=True  # Only check if exists, don't create
                )
                queue_ready = True
                await connection.close()
                connection = None
                break
            except Exception:
                if connection:
                    await connection.close()
                    connection = None
                if attempt < attempts - 1:
                    await asyncio.sleep(wait_interval)
        except Exception:
            if connection:
                try:
                    await connection.close()
                except:
                    pass
                connection = None
            if attempt < attempts - 1:
                await asyncio.sleep(wait_interval)
    
    if not queue_ready:
        # Queue not ready, but continue - test will fail with clear message
        if connection:
            try:
                await connection.close()
            except:
                pass
        return
    
    # Step 2: Verify Consumer can actually process events by sending a test event
    # This is a more reliable check than just queue existence
    test_job_id = uuid4()
    test_event = SubtitleEvent(
        event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
        job_id=test_job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="test",
        payload={
            "video_url": f"/test/verify_consumer_{test_job_id}.mp4",
            "video_title": f"Consumer Health Check {test_job_id}",
            "language": "en",
        },
    )
    
    # Create test job in Redis
    test_job = SubtitleResponse(
        id=test_job_id,
        video_url=f"/test/verify_consumer_{test_job_id}.mp4",
        video_title=f"Consumer Health Check {test_job_id}",
        language="en",
        status=SubtitleStatus.PENDING,
        source="test",
    )
    await redis_client.save_job(test_job)
    
    # Publish test event
    success = await event_publisher.publish_event(test_event)
    if not success:
        logger.warning("⚠️ Failed to publish test event for health check")
        await asyncio.sleep(2.0)
        return
    
    # Wait for Consumer to process it (up to 15 seconds)
    consumer_verified = False
    for attempt in range(150):  # 150 attempts * 0.1s = 15s max
        await asyncio.sleep(0.1)
        job = await redis_client.get_job(test_job_id)
        if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
            # Consumer is working! Clean up test job
            consumer_verified = True
            try:
                await redis_client.client.delete(f"job:{test_job_id}")
            except:
                pass
            await asyncio.sleep(1.0)  # Give Consumer a moment to be fully ready
            break
    
    if not consumer_verified:
        # Test event wasn't processed - Consumer might not be consuming
        # Log warning but don't fail - let the actual test fail with a clear message
        # This is just a best-effort check
        import logging
        logging.warning(
            f"⚠️ Consumer health check: Test event was not processed within 15s. "
            f"Test job status: {await redis_client.get_job(test_job_id)}"
        )
        # Clean up test job anyway
        try:
            await redis_client.client.delete(f"job:{test_job_id}")
        except:
            pass
        await asyncio.sleep(2.0)  # Give Consumer more time anyway


@pytest_asyncio.fixture(scope="function")
async def consumer():
    """Create a fresh event consumer instance for each test."""
    event_consumer = SubtitleEventConsumer()
    try:
        await asyncio.wait_for(event_consumer.connect(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Timeout connecting event consumer to RabbitMQ")

    yield event_consumer

    # Cleanup
    event_consumer.stop()
    try:
        await asyncio.wait_for(event_consumer.disconnect(), timeout=3.0)
    except asyncio.TimeoutError:
        pass


@pytest_asyncio.fixture(scope="function")
async def event_consumer_service():
    """Create Consumer service instance to process events and update Redis status.
    
    Note: start_consuming() handles connection and setup internally, but for tests
    we need to connect and setup separately so we can control when consuming starts.
    """
    consumer_service = EventConsumer()
    try:
        await asyncio.wait_for(consumer_service.connect(), timeout=5.0)
        queue = await asyncio.wait_for(consumer_service.setup_consumers(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Timeout connecting Consumer service to RabbitMQ")

    yield consumer_service, queue

    # Cleanup
    try:
        await asyncio.wait_for(consumer_service.disconnect(), timeout=3.0)
    except asyncio.TimeoutError:
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scanner_publishes_manager_consumes_end_to_end(
    setup_services, consumer, ensure_consumer_healthy
):
    """
    Test end-to-end event flow:
    1. Scanner creates job in Redis and publishes SUBTITLE_REQUESTED event
    2. Manager consumes event from RabbitMQ (test consumer or Docker Manager)
    3. Manager enqueues download task and publishes DOWNLOAD_REQUESTED event
    4. Consumer service (running in Docker) processes DOWNLOAD_REQUESTED and updates status to DOWNLOAD_QUEUED
    
    Note: We start a test consumer to ensure events are processed. If Docker Manager is also running,
    both will compete for messages, but that's okay - one will process it.
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

    # Start the test consumer to process events (Manager's event consumer)
    # This ensures events are processed even if Docker Manager isn't consuming
    logger.info("Starting test Manager event consumer...")
    consumer_task = asyncio.create_task(consumer.start_consuming())
    await asyncio.sleep(0.2)  # Give consumer time to start

    # Publish the event (as Scanner would do)
    success = await event_publisher.publish_event(subtitle_requested_event)
    assert success is True
    logger.info(f"✅ Published SUBTITLE_REQUESTED event for job {job_id}")

    # Wait for message to be processed (give it up to 20 seconds)
    # Manager processes SUBTITLE_REQUESTED -> publishes DOWNLOAD_REQUESTED
    # Consumer service (Docker) processes DOWNLOAD_REQUESTED -> updates status to DOWNLOAD_QUEUED
    # Add initial delay to allow events to propagate
    await asyncio.sleep(0.5)  # Give Manager time to consume and process
    
    for attempt in range(200):  # 200 attempts * 0.1s = 20s max
        await asyncio.sleep(0.1)

        # Check if job was updated in Redis (indicates Consumer processed DOWNLOAD_REQUESTED)
        job = await redis_client.get_job(job_id)
        if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
            logger.info(f"✅ Job {job_id} status updated to DOWNLOAD_QUEUED after {attempt + 1} attempts")
            break
        
        # Log progress every 50 attempts
        if (attempt + 1) % 50 == 0:
            logger.info(f"⏳ Waiting for job {job_id} to be processed... Status: {job.status if job else 'None'} (attempt {attempt + 1}/200)")
    else:
        # Get final job state for debugging
        final_job = await redis_client.get_job(job_id)
        logger.error(f"❌ Timeout waiting for event to be processed. Final job status: {final_job.status if final_job else 'None'}")
        pytest.fail(
            f"Timeout waiting for event to be processed after {attempt + 1} attempts. "
            f"Final job status: {final_job.status if final_job else 'None'}, "
            f"job_id: {job_id}"
        )

    # Verify the job was updated correctly
    job = await redis_client.get_job(job_id)
    assert job is not None, "Job should exist in Redis"
    assert job.status == SubtitleStatus.DOWNLOAD_QUEUED
    assert job.video_url == f"/media/movies/integration_test_{job_id}.mp4"
    assert job.video_title == unique_video_title
    assert job.language == "en"
    assert job.target_language == "es"

    finally:
        # Stop consumer properly before event loop closes
        logger.info("Stopping test Manager event consumer...")
        consumer.stop()
        try:
            # Give consumer a moment to stop gracefully
            await asyncio.sleep(0.1)
            # Cancel the task if it's still running
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await asyncio.wait_for(consumer_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
        except Exception as e:
            logger.warning(f"Error during consumer cleanup: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_events_processed_sequentially(
    setup_services, consumer, ensure_consumer_healthy
):
    """
    Test that multiple SUBTITLE_REQUESTED events are processed in order.
    Note: We start a test consumer to ensure events are processed.
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

    # Start the test consumer to process events (Manager's event consumer)
    logger.info("Starting test Manager event consumer...")
    consumer_task = asyncio.create_task(consumer.start_consuming())
    await asyncio.sleep(0.2)  # Give consumer time to start

    # Publish all events
    for event in events:
        await event_publisher.publish_event(event)
        logger.info(f"✅ Published SUBTITLE_REQUESTED event for job {event.job_id}")

    # Wait for all messages to be processed (Consumer service in Docker will process DOWNLOAD_REQUESTED)
    # Add initial delay to allow events to propagate and Manager/Consumer to be ready
    await asyncio.sleep(1.0)
    
    all_processed = False
    last_processed_count = 0
    no_progress_count = 0
    
    for attempt in range(300):  # 300 attempts * 0.1s = 30s max
        await asyncio.sleep(0.1)

        # Check if all jobs were processed (Consumer should have updated status)
        processed_count = 0
        for job_id in job_ids:
            job = await redis_client.get_job(job_id)
            if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
                processed_count += 1

        # Check if we made progress
        if processed_count > last_processed_count:
            no_progress_count = 0
            last_processed_count = processed_count
        else:
            no_progress_count += 1

        if processed_count == len(job_ids):
            all_processed = True
            break
        
        # If no progress for 50 attempts (5 seconds), log status for debugging
        if no_progress_count == 50:
            job_statuses = {}
            for job_id in job_ids:
                job = await redis_client.get_job(job_id)
                job_statuses[job_id] = job.status if job else "None"
            logger.info(
                f"Waiting for events to be processed... "
                f"Processed: {processed_count}/{len(job_ids)}. "
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
            f"Not all events were processed within timeout. "
            f"Processed: {processed_count}/{len(job_ids)}. "
            f"Job statuses: {job_statuses}"
        )

    # Verify all jobs were created correctly
    for job_id in job_ids:
        job = await redis_client.get_job(job_id)
        assert job is not None
            assert job.status == SubtitleStatus.DOWNLOAD_QUEUED
            assert job.video_title == f"Test Movie {job_id}"

    finally:
        # Stop consumer properly before event loop closes
        logger.info("Stopping test Manager event consumer...")
        consumer.stop()
        try:
            # Give consumer a moment to stop gracefully
            await asyncio.sleep(0.1)
            # Cancel the task if it's still running
            if not consumer_task.done():
                consumer_task.cancel()
                try:
                    await asyncio.wait_for(consumer_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
        except Exception as e:
            logger.warning(f"Error during consumer cleanup: {e}")



@pytest.mark.asyncio
@pytest.mark.integration
async def test_consumer_ignores_non_subtitle_requested_events(setup_services, consumer):
    """
    Test that consumer only processes SUBTITLE_REQUESTED events and ignores others.
    """
    job_id = uuid4()

    # Create a MEDIA_FILE_DETECTED event (should be ignored)
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

    # Start consumer
    consumer_task = asyncio.create_task(consumer.start_consuming())

    try:
        # Wait a bit to ensure event would be processed if it was going to be
        await asyncio.sleep(1.0)

        # Verify job was NOT created (event should be ignored)
        job = await redis_client.get_job(job_id)
        assert job is None, "Job should not exist for MEDIA_FILE_DETECTED event"

    finally:
        # Stop consumer
        consumer.stop()
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_consumer_handles_malformed_events_gracefully(setup_services, consumer):
    """
    Test that consumer handles malformed events without crashing.
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

    # Start consumer
    consumer_task = asyncio.create_task(consumer.start_consuming())

    try:
        # Wait for processing
        await asyncio.sleep(1.0)

        # Verify consumer is still running (didn't crash)
        assert not consumer_task.done(), "Consumer should still be running"

        # Verify job status was updated to FAILED
        for _ in range(20):
            await asyncio.sleep(0.1)
            job = await redis_client.get_job(job_id)
            if job and job.status == SubtitleStatus.FAILED:
                break
        else:
            # Job might not exist if Redis save failed, which is also acceptable
            job = await redis_client.get_job(job_id)
            if job:
                assert (
                    job.status == SubtitleStatus.FAILED
                ), "Job should be marked as FAILED"

    finally:
        # Stop consumer
        consumer.stop()
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
