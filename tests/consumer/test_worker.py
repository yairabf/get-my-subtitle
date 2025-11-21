"""Tests for the consumer worker."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from consumer.worker import EventConsumer


class TestSubtitleMissingHandler:
    """Test SUBTITLE_MISSING event handler in consumer."""

    @pytest.mark.asyncio
    async def test_handle_subtitle_missing_updates_job_status(self):
        """Test that handle_subtitle_missing updates job status to SUBTITLE_MISSING."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_MISSING,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="downloader",
            payload={
                "language": "en",
                "reason": "subtitle_not_found_no_translation",
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
            },
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock()
            mock_redis.record_event = AsyncMock()

            await consumer.handle_subtitle_missing(event)

            # Verify job status was updated to SUBTITLE_MISSING
            mock_redis.update_phase.assert_called_once_with(
                job_id,
                SubtitleStatus.SUBTITLE_MISSING,
                source="consumer",
                metadata=event.payload,
            )

    @pytest.mark.asyncio
    async def test_handle_subtitle_missing_records_event(self):
        """Test that handle_subtitle_missing records event in history."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_MISSING,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="downloader",
            payload={
                "language": "he",
                "reason": "subtitle_not_found_no_translation",
            },
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock()
            mock_redis.record_event = AsyncMock()

            await consumer.handle_subtitle_missing(event)

            # Verify event was recorded
            mock_redis.record_event.assert_called_once_with(
                job_id, event.event_type.value, event.payload, source="consumer"
            )

    @pytest.mark.asyncio
    async def test_handle_subtitle_missing_error_handling(self):
        """Test that handle_subtitle_missing handles errors gracefully."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_MISSING,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="downloader",
            payload={"language": "en"},
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            # Simulate Redis error
            mock_redis.update_phase = AsyncMock(
                side_effect=Exception("Redis connection error")
            )

            # Should not raise exception
            await consumer.handle_subtitle_missing(event)

    @pytest.mark.asyncio
    async def test_process_event_routes_subtitle_missing(self):
        """Test that process_event routes SUBTITLE_MISSING to correct handler."""
        consumer = EventConsumer()
        job_id = uuid4()

        event_data = {
            "event_type": "subtitle.missing",
            "job_id": str(job_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "downloader",
            "payload": {
                "language": "en",
                "reason": "subtitle_not_found_no_translation",
            },
        }

        import json

        mock_message = MagicMock()
        mock_message.body = json.dumps(event_data).encode()
        mock_message.routing_key = "subtitle.missing"

        with patch.object(
            consumer, "handle_subtitle_missing", new=AsyncMock()
        ) as mock_handler:
            await consumer.process_event(mock_message)

            # Verify handler was called
            mock_handler.assert_called_once()
            event_arg = mock_handler.call_args[0][0]
            assert event_arg.event_type == EventType.SUBTITLE_MISSING
            assert event_arg.job_id == job_id


class TestDownloadRequestedHandler:
    """Test DOWNLOAD_REQUESTED event handler in consumer."""

    @pytest.mark.asyncio
    async def test_handle_download_requested_updates_job_status(self):
        """Test that handle_download_requested updates job status to DOWNLOAD_QUEUED."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="manager",
            payload={
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
            },
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock()
            mock_redis.record_event = AsyncMock()

            await consumer.handle_download_requested(event)

            # Verify job status was updated to DOWNLOAD_QUEUED
            mock_redis.update_phase.assert_called_once_with(
                job_id,
                SubtitleStatus.DOWNLOAD_QUEUED,
                source="consumer",
                metadata=event.payload,
            )

    @pytest.mark.asyncio
    async def test_handle_download_requested_records_event(self):
        """Test that handle_download_requested records event in history."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="manager",
            payload={"video_url": "https://example.com/video.mp4"},
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock()
            mock_redis.record_event = AsyncMock()

            await consumer.handle_download_requested(event)

            # Verify event was recorded
            mock_redis.record_event.assert_called_once_with(
                job_id, event.event_type.value, event.payload, source="consumer"
            )


class TestTranslateRequestedHandler:
    """Test TRANSLATE_REQUESTED event handler in consumer."""

    @pytest.mark.asyncio
    async def test_handle_translate_requested_updates_job_status(self):
        """Test that handle_translate_requested updates job status to TRANSLATE_QUEUED."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="manager",
            payload={
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            },
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock()
            mock_redis.record_event = AsyncMock()

            await consumer.handle_translate_requested(event)

            # Verify job status was updated to TRANSLATE_QUEUED
            mock_redis.update_phase.assert_called_once_with(
                job_id,
                SubtitleStatus.TRANSLATE_QUEUED,
                source="consumer",
                metadata=event.payload,
            )

    @pytest.mark.asyncio
    async def test_handle_translate_requested_records_event(self):
        """Test that handle_translate_requested records event in history."""
        consumer = EventConsumer()
        job_id = uuid4()

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
            job_id=job_id,
            timestamp=datetime.now(timezone.utc),
            source="manager",
            payload={"source_language": "en", "target_language": "es"},
        )

        with patch("consumer.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock()
            mock_redis.record_event = AsyncMock()

            await consumer.handle_translate_requested(event)

            # Verify event was recorded
            mock_redis.record_event.assert_called_once_with(
                job_id, event.event_type.value, event.payload, source="consumer"
            )


class TestConsumerEventRouting:
    """Test event routing in consumer."""

    @pytest.mark.asyncio
    async def test_all_event_types_have_handlers(self):
        """Test that all EventType values have corresponding handlers."""
        consumer = EventConsumer()

        # Map of event types to handler methods
        expected_handlers = {
            EventType.SUBTITLE_DOWNLOAD_REQUESTED: "handle_download_requested",
            EventType.SUBTITLE_READY: "handle_subtitle_ready",
            EventType.SUBTITLE_MISSING: "handle_subtitle_missing",
            EventType.SUBTITLE_TRANSLATE_REQUESTED: "handle_translate_requested",
            EventType.SUBTITLE_TRANSLATED: "handle_subtitle_translated",
            EventType.JOB_FAILED: "handle_job_failed",
        }

        for event_type, handler_name in expected_handlers.items():
            assert hasattr(
                consumer, handler_name
            ), f"Consumer missing handler: {handler_name} for {event_type}"
