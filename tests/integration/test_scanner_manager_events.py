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


# Removed ensure_consumer_healthy and consumer fixtures
# Tests now rely on Docker services from docker-compose.integration.yml
# No competing test consumers - Manager service in Docker handles SUBTITLE_REQUESTED events


# Removed event_consumer_service fixture - Consumer service runs in Docker


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

    # Publish the event (Manager service in Docker will consume it)
    success = await event_publisher.publish_event(subtitle_requested_event)
    assert success is True
    logger.info(f"✅ Published SUBTITLE_REQUESTED event for job {job_id}")

    # Wait for Docker services to process event
    # Manager (Docker) consumes SUBTITLE_REQUESTED → publishes DOWNLOAD_REQUESTED
    # Consumer (Docker) consumes DOWNLOAD_REQUESTED → updates Redis status
    max_wait = 30  # seconds
    poll_interval = 0.5  # seconds

    for attempt in range(int(max_wait / poll_interval)):
        await asyncio.sleep(poll_interval)
        job = await redis_client.get_job(job_id)
        
        if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
            logger.info(f"✅ Job processed successfully after {attempt * poll_interval}s")
            break
        
        # Log progress every 10 attempts
        if attempt % 10 == 0 and job:
            logger.info(f"⏳ Waiting... Status: {job.status} (attempt {attempt})")
    else:
        # Test failed - get final state
        final_job = await redis_client.get_job(job_id)
        pytest.fail(
            f"Timeout: Job not processed after {max_wait}s. "
            f"Final status: {final_job.status if final_job else 'None'}, job_id: {job_id}"
        )

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

    # Publish all events (Manager service in Docker will consume them)
    for event in events:
        await event_publisher.publish_event(event)
        logger.info(f"✅ Published SUBTITLE_REQUESTED event for job {event.job_id}")

    # Wait for Docker services to process all events
    max_wait = 45  # seconds (3 events * 15s each)
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
            logger.info(f"✅ All jobs processed successfully after {attempt * poll_interval}s")
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

    # Wait for processing
    await asyncio.sleep(2.0)

    # Verify Manager is still running by publishing and processing a valid event
    valid_job_id = uuid4()
    valid_job = SubtitleResponse(
        id=valid_job_id,
        video_url=f"/media/movies/test_{valid_job_id}.mp4",
        video_title=f"Valid Test {valid_job_id}",
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
            "video_title": f"Valid Test {valid_job_id}",
            "language": "en",
            "target_language": "es",
            "preferred_sources": ["opensubtitles"],
        },
    )
    await event_publisher.publish_event(valid_event)
    
    # Wait for valid event to be processed
    for _ in range(20):  # 10 seconds
        await asyncio.sleep(0.5)
        job = await redis_client.get_job(valid_job_id)
        if job and job.status == SubtitleStatus.DOWNLOAD_QUEUED:
            break
    
    # Verify Manager processed the valid event (proving it didn't crash from malformed event)
    job = await redis_client.get_job(valid_job_id)
    assert job is not None, "Manager should still be running and processing events"
    assert job.status == SubtitleStatus.DOWNLOAD_QUEUED, "Valid event should be processed"
