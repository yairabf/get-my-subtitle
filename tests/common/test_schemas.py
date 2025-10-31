"""Tests for common schemas and models."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from common.schemas import EventType, SubtitleEvent, SubtitleStatus


class TestSubtitleRequestSchema:
    """Test subtitle request schema validation."""

    def test_valid_subtitle_request(self):
        """Test valid subtitle request data."""
        # This will be implemented when we create the schemas
        pass

    def test_invalid_subtitle_request(self):
        """Test invalid subtitle request data."""
        # This will be implemented when we create the schemas
        pass


class TestSubtitleResponseSchema:
    """Test subtitle response schema validation."""

    def test_valid_subtitle_response(self):
        """Test valid subtitle response data."""
        # This will be implemented when we create the schemas
        pass


class TestSubtitleMissingEnums:
    """Test SUBTITLE_MISSING enum values."""

    def test_subtitle_missing_event_type_exists(self):
        """Test that SUBTITLE_MISSING event type exists in EventType enum."""
        assert hasattr(EventType, "SUBTITLE_MISSING")
        assert EventType.SUBTITLE_MISSING.value == "subtitle.missing"

    def test_subtitle_missing_status_exists(self):
        """Test that SUBTITLE_MISSING status exists in SubtitleStatus enum."""
        assert hasattr(SubtitleStatus, "SUBTITLE_MISSING")
        assert SubtitleStatus.SUBTITLE_MISSING.value == "subtitle_missing"

    def test_subtitle_event_with_missing_type(self):
        """Test creating SubtitleEvent with SUBTITLE_MISSING type."""
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

        assert event.event_type == EventType.SUBTITLE_MISSING
        assert event.job_id == job_id
        assert event.source == "downloader"
        assert event.payload["language"] == "en"
        assert event.payload["reason"] == "subtitle_not_found_no_translation"

    def test_subtitle_missing_event_validates_correctly(self):
        """Test that SubtitleEvent with SUBTITLE_MISSING passes validation."""
        event_data = {
            "event_type": "subtitle.missing",
            "job_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "downloader",
            "payload": {
                "language": "en",
                "reason": "subtitle_not_found_no_translation",
            },
        }

        # Should not raise validation error
        event = SubtitleEvent.model_validate(event_data)
        assert event.event_type == EventType.SUBTITLE_MISSING


class TestUtilityFunctions:
    """Test common utility functions."""

    def test_generate_subtitle_id(self):
        """Test subtitle ID generation."""
        # This will be implemented when we create the utilities
        pass

    def test_validate_video_url(self):
        """Test video URL validation."""
        # This will be implemented when we create the utilities
        pass
