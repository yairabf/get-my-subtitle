"""Tests for Redis client enhancements (update_phase, record_event, get_job_events)."""

from uuid import uuid4

import pytest

from common.redis_client import RedisJobClient
from common.schemas import SubtitleResponse, SubtitleStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_phase_updates_status_with_source():
    """Test that update_phase correctly updates job status with source tracking."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        # Create a sample job
        job = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="he",
            status=SubtitleStatus.PENDING,
        )
        await client.save_job(job)

        # Update phase to DOWNLOAD_QUEUED
        success = await client.update_phase(
            job.id, SubtitleStatus.DOWNLOAD_QUEUED, source="manager"
        )

        assert success is True

        # Verify the job was updated
        updated_job = await client.get_job(job.id)
        assert updated_job is not None
        assert updated_job.status == SubtitleStatus.DOWNLOAD_QUEUED

        # Cleanup
        await client.delete_job(job.id)
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_phase_with_metadata():
    """Test that update_phase can merge metadata into job."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        # Create a sample job
        job = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="he",
            status=SubtitleStatus.PENDING,
        )
        await client.save_job(job)

        # Update with metadata
        metadata = {"download_url": "https://example.com/subtitle.srt"}

        success = await client.update_phase(
            job.id, SubtitleStatus.DONE, source="consumer", metadata=metadata
        )

        assert success is True

        # Verify metadata was applied
        updated_job = await client.get_job(job.id)
        assert updated_job.download_url == "https://example.com/subtitle.srt"

        # Cleanup
        await client.delete_job(job.id)
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_record_event_stores_event_history():
    """Test that record_event stores events in Redis list."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        # Create a sample job
        job = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="he",
            status=SubtitleStatus.PENDING,
        )
        await client.save_job(job)

        # Record an event
        event_type = "subtitle.download.requested"
        payload = {"video_url": job.video_url, "language": job.language}

        success = await client.record_event(
            job.id, event_type, payload, source="manager"
        )

        assert success is True

        # Cleanup
        await client.delete_job(job.id)
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_job_events_retrieves_event_history():
    """Test that get_job_events retrieves recorded events."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        # Create a sample job
        job = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="he",
            status=SubtitleStatus.PENDING,
        )
        await client.save_job(job)

        # Record multiple events
        events_to_record = [
            ("subtitle.download.requested", {"step": 1}, "manager"),
            ("subtitle.ready", {"step": 2}, "downloader"),
            ("subtitle.translated", {"step": 3}, "translator"),
        ]

        for event_type, payload, source in events_to_record:
            await client.record_event(job.id, event_type, payload, source)

        # Retrieve events
        events = await client.get_job_events(job.id)

        assert len(events) == 3
        # Events should be in reverse order (most recent first)
        assert events[0]["event_type"] == "subtitle.translated"
        assert events[1]["event_type"] == "subtitle.ready"
        assert events[2]["event_type"] == "subtitle.download.requested"

        # Cleanup
        await client.delete_job(job.id)
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_job_events_with_limit():
    """Test that get_job_events respects limit parameter."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        # Create a sample job
        job = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="he",
            status=SubtitleStatus.PENDING,
        )
        await client.save_job(job)

        # Record 5 events
        for i in range(5):
            await client.record_event(job.id, f"test.event.{i}", {"index": i}, "test")

        # Retrieve only 3 events
        events = await client.get_job_events(job.id, limit=3)

        assert len(events) == 3

        # Cleanup
        await client.delete_job(job.id)
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_job_events_returns_empty_for_new_job():
    """Test that get_job_events returns empty list for job with no events."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        # Create a sample job
        job = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="he",
            status=SubtitleStatus.PENDING,
        )
        await client.save_job(job)

        events = await client.get_job_events(job.id)

        assert events == []

        # Cleanup
        await client.delete_job(job.id)
    finally:
        await client.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_phase_on_nonexistent_job_returns_false():
    """Test that update_phase returns False for non-existent job."""
    client = RedisJobClient()
    await client.connect()

    if not client.connected:
        pytest.skip("Redis not available")

    try:
        fake_job_id = uuid4()
        success = await client.update_phase(
            fake_job_id, SubtitleStatus.DONE, source="test"
        )

        assert success is False
    finally:
        await client.disconnect()
