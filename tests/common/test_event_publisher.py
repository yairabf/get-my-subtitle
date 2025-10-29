"""Tests for event publisher."""

import pytest
from uuid import uuid4

from common.event_publisher import EventPublisher
from common.schemas import EventType, SubtitleEvent
from common.utils import DateTimeUtils


@pytest.mark.asyncio
class TestEventPublisher:
    """Test suite for EventPublisher."""

    async def test_publish_event_creates_correct_message(self):
        """Test that publish_event creates a properly formatted message."""
        publisher = EventPublisher()
        
        # Create a test event
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={
                "subtitle_path": "/test/subtitle.srt",
                "language": "en",
                "download_url": "https://example.com/subtitle.srt"
            }
        )
        
        # In mock mode (no connection), should return True
        result = await publisher.publish_event(event)
        assert result is True

    async def test_event_publisher_connection_lifecycle(self):
        """Test connecting and disconnecting event publisher."""
        publisher = EventPublisher()
        
        # Should handle connection gracefully (may fail if RabbitMQ not available)
        await publisher.connect()
        
        # Should handle disconnection gracefully
        await publisher.disconnect()

    async def test_event_types_have_correct_routing_keys(self):
        """Test that event types map to correct routing keys."""
        assert EventType.SUBTITLE_READY.value == "subtitle.ready"
        assert EventType.SUBTITLE_TRANSLATED.value == "subtitle.translated"
        assert EventType.SUBTITLE_DOWNLOAD_REQUESTED.value == "subtitle.download.requested"
        assert EventType.SUBTITLE_TRANSLATE_REQUESTED.value == "subtitle.translate.requested"
        assert EventType.JOB_FAILED.value == "job.failed"

    async def test_subtitle_event_serialization(self):
        """Test that SubtitleEvent can be serialized to JSON."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={"test": "data"}
        )
        
        # Should serialize without error
        json_str = event.model_dump_json()
        assert json_str is not None
        assert str(job_id) in json_str
        assert "subtitle.ready" in json_str

