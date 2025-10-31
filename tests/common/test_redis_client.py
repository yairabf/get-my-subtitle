"""Unit tests for RedisJobClient using fakeredis."""

import json
from datetime import datetime
from uuid import uuid4

import pytest
from redis.exceptions import RedisError

from common.redis_client import RedisJobClient
from common.schemas import SubtitleResponse, SubtitleStatus


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisJobClientConnection:
    """Test RedisJobClient connection lifecycle."""

    async def test_connect_successfully_sets_connected_flag(
        self, fake_redis_job_client
    ):
        """Test that connection is established and connected flag is True."""
        assert fake_redis_job_client.connected is True
        assert fake_redis_job_client.client is not None

    async def test_disconnect_closes_connection(self, fake_redis_job_client):
        """Test that disconnect closes the Redis connection."""
        await fake_redis_job_client.disconnect()
        assert fake_redis_job_client.connected is False

    async def test_health_check_returns_healthy_when_connected(
        self, fake_redis_job_client
    ):
        """Test health check returns healthy status when Redis is connected."""
        health = await fake_redis_job_client.health_check()

        assert health["connected"] is True
        assert health["status"] == "healthy"

    async def test_health_check_returns_disconnected_when_no_client(self):
        """Test health check returns disconnected when client is None."""
        client = RedisJobClient()
        # Don't connect - client remains None

        health = await client.health_check()

        assert health["connected"] is False
        assert health["status"] == "disconnected"
        assert "error" in health


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisJobClientJobOperations:
    """Test RedisJobClient CRUD operations."""

    async def test_save_job_stores_job_in_redis(
        self, fake_redis_job_client, sample_subtitle_response
    ):
        """Test that save_job stores a job in Redis with correct key."""
        result = await fake_redis_job_client.save_job(sample_subtitle_response)

        assert result is True

        # Verify job was stored
        job_key = f"job:{str(sample_subtitle_response.id)}"
        stored_data = await fake_redis_job_client.client.get(job_key)
        assert stored_data is not None

        # Verify job data
        job_data = json.loads(stored_data)
        assert job_data["id"] == str(sample_subtitle_response.id)
        assert job_data["video_url"] == sample_subtitle_response.video_url

    async def test_get_job_retrieves_stored_job(
        self, fake_redis_job_client, sample_subtitle_response
    ):
        """Test that get_job retrieves a job from Redis."""
        # Save job first
        await fake_redis_job_client.save_job(sample_subtitle_response)

        # Retrieve job
        retrieved_job = await fake_redis_job_client.get_job(sample_subtitle_response.id)

        assert retrieved_job is not None
        assert retrieved_job.id == sample_subtitle_response.id
        assert retrieved_job.video_url == sample_subtitle_response.video_url
        assert retrieved_job.status == sample_subtitle_response.status

    async def test_get_job_returns_none_when_job_not_found(self, fake_redis_job_client):
        """Test that get_job returns None when job doesn't exist."""
        non_existent_id = uuid4()

        job = await fake_redis_job_client.get_job(non_existent_id)

        assert job is None

    async def test_delete_job_removes_job_from_redis(
        self, fake_redis_job_client, sample_subtitle_response
    ):
        """Test that delete_job removes a job from Redis."""
        # Save job first
        await fake_redis_job_client.save_job(sample_subtitle_response)

        # Delete job
        result = await fake_redis_job_client.delete_job(sample_subtitle_response.id)

        assert result is True

        # Verify job was deleted
        job = await fake_redis_job_client.get_job(sample_subtitle_response.id)
        assert job is None

    async def test_delete_job_returns_false_when_job_not_found(
        self, fake_redis_job_client
    ):
        """Test that delete_job returns False when job doesn't exist."""
        non_existent_id = uuid4()

        result = await fake_redis_job_client.delete_job(non_existent_id)

        assert result is False

    async def test_list_jobs_returns_all_jobs(self, fake_redis_job_client):
        """Test that list_jobs returns all stored jobs."""
        # Create and save multiple jobs
        jobs = [
            SubtitleResponse(
                id=uuid4(),
                video_url=f"https://example.com/video{i}.mp4",
                video_title=f"Video {i}",
                language="en",
                status=SubtitleStatus.PENDING,
            )
            for i in range(3)
        ]

        for job in jobs:
            await fake_redis_job_client.save_job(job)

        # List all jobs
        retrieved_jobs = await fake_redis_job_client.list_jobs()

        assert len(retrieved_jobs) == 3
        retrieved_ids = {job.id for job in retrieved_jobs}
        expected_ids = {job.id for job in jobs}
        assert retrieved_ids == expected_ids


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisJobClientStatusTracking:
    """Test RedisJobClient status updates and phase transitions."""

    @pytest.mark.parametrize(
        "status,error_message,download_url",
        [
            (SubtitleStatus.DOWNLOAD_QUEUED, None, None),
            (SubtitleStatus.DOWNLOAD_IN_PROGRESS, None, None),
            (SubtitleStatus.DONE, None, "https://example.com/subtitle.srt"),
            (SubtitleStatus.FAILED, "Download failed", None),
        ],
    )
    async def test_update_job_status_updates_fields(
        self,
        fake_redis_job_client,
        sample_subtitle_response,
        status,
        error_message,
        download_url,
    ):
        """Test that update_job_status updates status and optional fields."""
        # Save initial job
        await fake_redis_job_client.save_job(sample_subtitle_response)

        # Update status
        result = await fake_redis_job_client.update_job_status(
            sample_subtitle_response.id,
            status,
            error_message=error_message,
            download_url=download_url,
        )

        assert result is True

        # Verify updates
        updated_job = await fake_redis_job_client.get_job(sample_subtitle_response.id)
        assert updated_job.status == status
        if error_message:
            assert updated_job.error_message == error_message
        if download_url:
            assert updated_job.download_url == download_url

    async def test_update_job_status_returns_false_for_nonexistent_job(
        self, fake_redis_job_client
    ):
        """Test that update_job_status returns False for non-existent job."""
        non_existent_id = uuid4()

        result = await fake_redis_job_client.update_job_status(
            non_existent_id, SubtitleStatus.DONE
        )

        assert result is False

    async def test_update_phase_updates_status_with_source_tracking(
        self, fake_redis_job_client, sample_subtitle_response
    ):
        """Test that update_phase updates status with source tracking."""
        # Save initial job
        await fake_redis_job_client.save_job(sample_subtitle_response)

        # Update phase
        result = await fake_redis_job_client.update_phase(
            sample_subtitle_response.id,
            SubtitleStatus.DOWNLOAD_IN_PROGRESS,
            source="downloader",
        )

        assert result is True

        # Verify update
        updated_job = await fake_redis_job_client.get_job(sample_subtitle_response.id)
        assert updated_job.status == SubtitleStatus.DOWNLOAD_IN_PROGRESS

    async def test_update_phase_with_metadata_updates_job_fields(
        self, fake_redis_job_client, sample_subtitle_response
    ):
        """Test that update_phase merges metadata into job."""
        # Save initial job
        await fake_redis_job_client.save_job(sample_subtitle_response)

        # Update phase with metadata
        metadata = {
            "error_message": "Test error",
            "download_url": "https://example.com/subtitle.srt",
        }
        result = await fake_redis_job_client.update_phase(
            sample_subtitle_response.id,
            SubtitleStatus.FAILED,
            source="downloader",
            metadata=metadata,
        )

        assert result is True

        # Verify metadata was merged
        updated_job = await fake_redis_job_client.get_job(sample_subtitle_response.id)
        assert updated_job.error_message == "Test error"
        assert updated_job.download_url == "https://example.com/subtitle.srt"


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisJobClientEventHistory:
    """Test RedisJobClient event recording and retrieval."""

    async def test_record_event_stores_event_in_redis(
        self, fake_redis_job_client, sample_job_id
    ):
        """Test that record_event stores event history in Redis."""
        event_type = "subtitle.ready"
        payload = {"subtitle_path": "/path/to/subtitle.srt"}
        source = "downloader"

        result = await fake_redis_job_client.record_event(
            sample_job_id, event_type, payload, source
        )

        assert result is True

        # Verify event was stored
        events_key = f"job:events:{str(sample_job_id)}"
        events_count = await fake_redis_job_client.client.llen(events_key)
        assert events_count == 1

    async def test_get_job_events_retrieves_event_history(
        self, fake_redis_job_client, sample_job_id
    ):
        """Test that get_job_events retrieves stored event history."""
        # Record multiple events
        events_to_record = [
            ("subtitle.download.requested", {"video_url": "test.mp4"}, "manager"),
            ("subtitle.ready", {"subtitle_path": "/path/to/sub.srt"}, "downloader"),
            (
                "subtitle.translated",
                {"translated_path": "/path/to/translated.srt"},
                "translator",
            ),
        ]

        for event_type, payload, source in events_to_record:
            await fake_redis_job_client.record_event(
                sample_job_id, event_type, payload, source
            )

        # Retrieve events
        events = await fake_redis_job_client.get_job_events(sample_job_id)

        assert len(events) == 3
        # Events are returned in reverse order (most recent first)
        assert events[0]["event_type"] == "subtitle.translated"
        assert events[1]["event_type"] == "subtitle.ready"
        assert events[2]["event_type"] == "subtitle.download.requested"

    async def test_get_job_events_returns_empty_list_when_no_events(
        self, fake_redis_job_client, sample_job_id
    ):
        """Test that get_job_events returns empty list when no events exist."""
        events = await fake_redis_job_client.get_job_events(sample_job_id)

        assert events == []

    async def test_get_job_events_respects_limit_parameter(
        self, fake_redis_job_client, sample_job_id
    ):
        """Test that get_job_events respects the limit parameter."""
        # Record 10 events
        for i in range(10):
            await fake_redis_job_client.record_event(
                sample_job_id,
                f"event.{i}",
                {"index": i},
                "test",
            )

        # Get only 5 events
        events = await fake_redis_job_client.get_job_events(sample_job_id, limit=5)

        assert len(events) == 5


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisJobClientTTLManagement:
    """Test RedisJobClient TTL handling for different job statuses."""

    async def test_save_job_sets_ttl_for_completed_status(self, fake_redis_job_client):
        """Test that completed jobs get appropriate TTL."""
        job = SubtitleResponse(
            id=uuid4(),
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=SubtitleStatus.COMPLETED,
        )

        await fake_redis_job_client.save_job(job)

        # Verify TTL was set
        job_key = f"job:{str(job.id)}"
        ttl = await fake_redis_job_client.client.ttl(job_key)
        assert ttl > 0  # TTL should be set

    async def test_save_job_sets_ttl_for_failed_status(self, fake_redis_job_client):
        """Test that failed jobs get appropriate TTL."""
        job = SubtitleResponse(
            id=uuid4(),
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=SubtitleStatus.FAILED,
        )

        await fake_redis_job_client.save_job(job)

        # Verify TTL was set
        job_key = f"job:{str(job.id)}"
        ttl = await fake_redis_job_client.client.ttl(job_key)
        assert ttl > 0  # TTL should be set

    async def test_save_job_no_ttl_for_active_status(self, fake_redis_job_client):
        """Test that active jobs don't get TTL (or get TTL=0)."""
        job = SubtitleResponse(
            id=uuid4(),
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=SubtitleStatus.PENDING,
        )

        await fake_redis_job_client.save_job(job)

        # Verify no TTL was set (or TTL=0 which means no expiration in Redis)
        job_key = f"job:{str(job.id)}"
        ttl = await fake_redis_job_client.client.ttl(job_key)
        # TTL of -1 means key exists but has no expiration
        # TTL of 0 would mean key will be set with no expiration
        assert ttl == -1  # No expiration set


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisJobClientErrorHandling:
    """Test RedisJobClient error scenarios and graceful degradation."""

    async def test_save_job_returns_false_when_not_connected(
        self, sample_subtitle_response
    ):
        """Test that save_job returns False when Redis is not connected."""
        client = RedisJobClient()
        # Don't connect - should handle gracefully

        result = await client.save_job(sample_subtitle_response)

        assert result is False

    async def test_get_job_returns_none_when_not_connected(self, sample_job_id):
        """Test that get_job returns None when Redis is not connected."""
        client = RedisJobClient()
        # Don't connect - should handle gracefully

        job = await client.get_job(sample_job_id)

        assert job is None

    async def test_update_job_status_returns_false_when_not_connected(
        self, sample_job_id
    ):
        """Test that update_job_status returns False when Redis is not connected."""
        client = RedisJobClient()
        # Don't connect - should handle gracefully

        result = await client.update_job_status(sample_job_id, SubtitleStatus.DONE)

        assert result is False

    async def test_list_jobs_returns_empty_list_when_not_connected(self):
        """Test that list_jobs returns empty list when Redis is not connected."""
        client = RedisJobClient()
        # Don't connect - should handle gracefully

        jobs = await client.list_jobs()

        assert jobs == []

    async def test_record_event_returns_false_when_not_connected(self, sample_job_id):
        """Test that record_event returns False when Redis is not connected."""
        client = RedisJobClient()
        # Don't connect - should handle gracefully

        result = await client.record_event(sample_job_id, "test.event", {}, "test")

        assert result is False

    async def test_get_job_events_returns_empty_list_when_not_connected(
        self, sample_job_id
    ):
        """Test that get_job_events returns empty list when Redis is not connected."""
        client = RedisJobClient()
        # Don't connect - should handle gracefully

        events = await client.get_job_events(sample_job_id)

        assert events == []

    async def test_list_jobs_with_status_filter(self, fake_redis_job_client):
        """Test that list_jobs filters by status correctly."""
        # Create jobs with different statuses
        jobs = [
            SubtitleResponse(
                id=uuid4(),
                video_url="https://example.com/video1.mp4",
                video_title="Video 1",
                language="en",
                status=SubtitleStatus.PENDING,
            ),
            SubtitleResponse(
                id=uuid4(),
                video_url="https://example.com/video2.mp4",
                video_title="Video 2",
                language="en",
                status=SubtitleStatus.COMPLETED,
            ),
            SubtitleResponse(
                id=uuid4(),
                video_url="https://example.com/video3.mp4",
                video_title="Video 3",
                language="en",
                status=SubtitleStatus.FAILED,
            ),
        ]

        for job in jobs:
            await fake_redis_job_client.save_job(job)

        # List only completed jobs
        completed_jobs = await fake_redis_job_client.list_jobs(
            status_filter=SubtitleStatus.COMPLETED
        )

        assert len(completed_jobs) == 1
        assert completed_jobs[0].status == SubtitleStatus.COMPLETED

    async def test_key_generation_format(self, fake_redis_job_client, sample_job_id):
        """Test that Redis keys are generated in correct format."""
        job_key = fake_redis_job_client._get_job_key(sample_job_id)
        events_key = fake_redis_job_client._get_job_events_key(sample_job_id)

        assert job_key == f"job:{str(sample_job_id)}"
        assert events_key == f"job:events:{str(sample_job_id)}"
