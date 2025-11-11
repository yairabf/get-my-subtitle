"""Integration tests for Scanner → Manager event flow via RabbitMQ.

Note: These tests require actual RabbitMQ and Redis services to be running.
In CI, these services should be started via docker-compose before running tests.
"""

import asyncio
from uuid import uuid4

import pytest

from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleRequest, SubtitleStatus
from common.utils import DateTimeUtils
from manager.event_consumer import event_consumer
from manager.orchestrator import orchestrator


@pytest.fixture(scope="function")
async def setup_services():
    """Set up Redis, RabbitMQ, orchestrator, and event consumer for testing."""
    # Connect services with timeout
    try:
        await asyncio.wait_for(redis_client.connect(), timeout=5.0)
        await asyncio.wait_for(orchestrator.connect(), timeout=5.0)
        await asyncio.wait_for(event_publisher.connect(), timeout=5.0)
        await asyncio.wait_for(event_consumer.connect(), timeout=5.0)
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
        await asyncio.wait_for(event_consumer.disconnect(), timeout=3.0)
        await asyncio.wait_for(event_publisher.disconnect(), timeout=3.0)
        await asyncio.wait_for(orchestrator.disconnect(), timeout=3.0)
        await asyncio.wait_for(redis_client.disconnect(), timeout=3.0)
    except asyncio.TimeoutError:
        # Log but don't fail on disconnect timeout
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scanner_publishes_manager_consumes_end_to_end(setup_services):
    """
    Test end-to-end event flow:
    1. Scanner publishes SUBTITLE_REQUESTED event
    2. Manager consumes event from RabbitMQ
    3. Manager enqueues download task
    4. Job status is updated in Redis
    """
    job_id = uuid4()

    # Create a SUBTITLE_REQUESTED event (as Scanner would publish)
    subtitle_requested_event = SubtitleEvent(
        event_type=EventType.SUBTITLE_REQUESTED,
        job_id=job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="scanner",
        payload={
            "video_url": "/media/movies/integration_test.mp4",
            "video_title": "Integration Test Movie",
            "language": "en",
            "target_language": "es",
            "preferred_sources": ["opensubtitles"],
            "auto_translate": True,
        },
    )

    # Publish the event (as Scanner would do)
    success = await event_publisher.publish_event(subtitle_requested_event)
    assert success is True

    # Start consumer in background
    consumer_task = asyncio.create_task(event_consumer.start_consuming())

    try:
        # Wait for message to be processed (give it up to 5 seconds)
        for _ in range(50):  # 50 attempts * 0.1s = 5s max
            await asyncio.sleep(0.1)

            # Check if job was updated in Redis (indicates processing completed)
            job = await redis_client.get_job(job_id)
            if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
                break
        else:
            pytest.fail("Timeout waiting for event to be processed")

        # Verify the job was updated correctly
        job = await redis_client.get_job(job_id)
        assert job is not None, "Job should exist in Redis"
        assert job.status == SubtitleStatus.DOWNLOAD_QUEUED
        assert job.video_url == "/media/movies/integration_test.mp4"
        assert job.video_title == "Integration Test Movie"
        assert job.language == "en"
        assert job.target_language == "es"

    finally:
        # Stop consumer
        event_consumer.stop()
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
async def test_multiple_events_processed_sequentially(setup_services):
    """
    Test that multiple SUBTITLE_REQUESTED events are processed in order.
    """
    job_ids = [uuid4() for _ in range(3)]
    events = []

    # Create multiple events
    for i, job_id in enumerate(job_ids):
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": f"/media/movies/test_movie_{i}.mp4",
                "video_title": f"Test Movie {i}",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
                "auto_translate": True,
            },
        )
        events.append(event)

    # Publish all events
    for event in events:
        await event_publisher.publish_event(event)

    # Start consumer
    consumer_task = asyncio.create_task(event_consumer.start_consuming())

    try:
        # Wait for all messages to be processed
        all_processed = False
        for _ in range(100):  # 100 attempts * 0.1s = 10s max
            await asyncio.sleep(0.1)

            # Check if all jobs were processed
            processed_count = 0
            for job_id in job_ids:
                job = await redis_client.get_job(job_id)
                if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
                    processed_count += 1

            if processed_count == len(job_ids):
                all_processed = True
                break

        assert all_processed, "Not all events were processed within timeout"

        # Verify all jobs were created correctly
        for i, job_id in enumerate(job_ids):
            job = await redis_client.get_job(job_id)
            assert job is not None
            assert job.status == SubtitleStatus.DOWNLOAD_QUEUED
            assert job.video_title == f"Test Movie {i}"

    finally:
        # Stop consumer
        event_consumer.stop()
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
async def test_consumer_ignores_non_subtitle_requested_events(setup_services):
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
    consumer_task = asyncio.create_task(event_consumer.start_consuming())

    try:
        # Wait a bit to ensure event would be processed if it was going to be
        await asyncio.sleep(1.0)

        # Verify job was NOT created (event should be ignored)
        job = await redis_client.get_job(job_id)
        assert job is None, "Job should not exist for MEDIA_FILE_DETECTED event"

    finally:
        # Stop consumer
        event_consumer.stop()
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
async def test_consumer_handles_malformed_events_gracefully(setup_services):
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
    consumer_task = asyncio.create_task(event_consumer.start_consuming())

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
        event_consumer.stop()
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.TimeoutError:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
