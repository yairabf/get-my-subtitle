"""Serialization/deserialization tests for common schema models."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from common.schemas import (
    DownloadTask,
    EventType,
    HealthResponse,
    SubtitleEvent,
    SubtitleRequest,
    SubtitleResponse,
    SubtitleStatus,
    TranslationCheckpoint,
    TranslationTask,
)

# ============================================================================
# SubtitleRequest Serialization Tests
# ============================================================================


class TestSubtitleRequestSerialization:
    """Test SubtitleRequest serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            preferred_sources=["opensubtitles"],
        )

        dumped = request.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["video_url"] == "https://example.com/video.mp4"
        assert dumped["video_title"] == "Test Video"
        assert dumped["language"] == "en"
        assert dumped["target_language"] == "es"
        assert dumped["preferred_sources"] == ["opensubtitles"]

    def test_model_dump_json_returns_string(self):
        """Test model_dump_json() returns valid JSON string."""
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        json_str = request.model_dump_json()
        assert isinstance(json_str, str)

        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["video_url"] == "https://example.com/video.mp4"
        assert parsed["video_title"] == "Test Video"
        assert parsed["language"] == "en"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        data = {
            "video_url": "https://example.com/video.mp4",
            "video_title": "Test Video",
            "language": "en",
            "target_language": "es",
            "preferred_sources": ["opensubtitles"],
        }

        request = SubtitleRequest.model_validate(data)

        assert request.video_url == data["video_url"]
        assert request.video_title == data["video_title"]
        assert request.language == data["language"]
        assert request.target_language == data["target_language"]
        assert request.preferred_sources == data["preferred_sources"]

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        json_str = json.dumps(
            {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
            }
        )

        request = SubtitleRequest.model_validate_json(json_str)

        assert request.video_url == "https://example.com/video.mp4"
        assert request.video_title == "Test Video"
        assert request.language == "en"

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            preferred_sources=["opensubtitles", "subscene"],
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = SubtitleRequest.model_validate(dumped)

        assert restored.video_url == original.video_url
        assert restored.video_title == original.video_title
        assert restored.language == original.language
        assert restored.target_language == original.target_language
        assert restored.preferred_sources == original.preferred_sources

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        original = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = SubtitleRequest.model_validate_json(json_str)

        assert restored.video_url == original.video_url
        assert restored.video_title == original.video_title
        assert restored.language == original.language


# ============================================================================
# SubtitleResponse Serialization Tests
# ============================================================================


class TestSubtitleResponseSerialization:
    """Test SubtitleResponse serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        response = SubtitleResponse(
            id=job_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=SubtitleStatus.DONE,
            created_at=created_at,
            updated_at=updated_at,
        )

        dumped = response.model_dump()

        assert isinstance(dumped, dict)
        assert str(dumped["id"]) == str(job_id)
        assert dumped["video_url"] == "https://example.com/video.mp4"
        assert dumped["status"] == "done"
        assert isinstance(dumped["created_at"], datetime)
        assert isinstance(dumped["updated_at"], datetime)

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        job_id = uuid4()
        response = SubtitleResponse(
            id=job_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["id"] == str(job_id)
        assert isinstance(parsed["id"], str)

    def test_model_dump_json_serializes_datetime_to_iso_format(self):
        """Test model_dump_json() serializes datetime to ISO format."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

        response = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            created_at=created_at,
            updated_at=updated_at,
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["created_at"] == "2024-01-01T12:00:00Z"
        assert parsed["updated_at"] == "2024-01-01T12:05:00Z"

    def test_model_dump_json_serializes_enum_to_string(self):
        """Test model_dump_json() serializes enum to string value."""
        response = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=SubtitleStatus.DOWNLOAD_IN_PROGRESS,
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "download_in_progress"
        assert isinstance(parsed["status"], str)

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        data = {
            "id": str(job_id),
            "video_url": "https://example.com/video.mp4",
            "video_title": "Test Video",
            "language": "en",
            "status": "done",
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
        }

        response = SubtitleResponse.model_validate(data)

        assert response.id == job_id
        assert response.video_url == data["video_url"]
        assert response.status == SubtitleStatus.DONE

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        job_id = uuid4()
        json_str = json.dumps(
            {
                "id": str(job_id),
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "status": "pending",
            }
        )

        response = SubtitleResponse.model_validate_json(json_str)

        assert response.id == job_id
        assert response.video_url == "https://example.com/video.mp4"
        assert response.status == SubtitleStatus.PENDING

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        original = SubtitleResponse(
            id=job_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            status=SubtitleStatus.DONE,
            created_at=created_at,
            updated_at=updated_at,
            download_url="https://example.com/subtitles/123.srt",
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = SubtitleResponse.model_validate(dumped)

        assert restored.id == original.id
        assert restored.video_url == original.video_url
        assert restored.status == original.status
        assert restored.target_language == original.target_language
        assert restored.download_url == original.download_url

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        original = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=SubtitleStatus.DONE,
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = SubtitleResponse.model_validate_json(json_str)

        assert restored.video_url == original.video_url
        assert restored.video_title == original.video_title
        assert restored.language == original.language
        assert restored.status == original.status


# ============================================================================
# DownloadTask Serialization Tests
# ============================================================================


class TestDownloadTaskSerialization:
    """Test DownloadTask serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        request_id = uuid4()
        task = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles"],
        )

        dumped = task.model_dump()

        assert isinstance(dumped, dict)
        assert str(dumped["request_id"]) == str(request_id)
        assert dumped["video_url"] == "https://example.com/video.mp4"
        assert dumped["preferred_sources"] == ["opensubtitles"]

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        request_id = uuid4()
        task = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        json_str = task.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["request_id"] == str(request_id)
        assert isinstance(parsed["request_id"], str)

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        request_id = uuid4()
        data = {
            "request_id": str(request_id),
            "video_url": "https://example.com/video.mp4",
            "video_title": "Test Video",
            "language": "en",
            "preferred_sources": ["opensubtitles"],
        }

        task = DownloadTask.model_validate(data)

        assert task.request_id == request_id
        assert task.video_url == data["video_url"]
        assert task.preferred_sources == data["preferred_sources"]

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        request_id = uuid4()
        json_str = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
            }
        )

        task = DownloadTask.model_validate_json(json_str)

        assert task.request_id == request_id
        assert task.video_url == "https://example.com/video.mp4"

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        request_id = uuid4()
        original = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles", "subscene"],
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = DownloadTask.model_validate(dumped)

        assert restored.request_id == original.request_id
        assert restored.video_url == original.video_url
        assert restored.preferred_sources == original.preferred_sources

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        request_id = uuid4()
        original = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = DownloadTask.model_validate_json(json_str)

        assert restored.request_id == original.request_id
        assert restored.video_url == original.video_url
        assert restored.video_title == original.video_title


# ============================================================================
# TranslationTask Serialization Tests
# ============================================================================


class TestTranslationTaskSerialization:
    """Test TranslationTask serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        request_id = uuid4()
        task = TranslationTask(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        dumped = task.model_dump()

        assert isinstance(dumped, dict)
        assert str(dumped["request_id"]) == str(request_id)
        assert dumped["subtitle_file_path"] == "/path/to/subtitle.srt"
        assert dumped["source_language"] == "en"
        assert dumped["target_language"] == "es"

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        request_id = uuid4()
        task = TranslationTask(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        json_str = task.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["request_id"] == str(request_id)
        assert isinstance(parsed["request_id"], str)

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        request_id = uuid4()
        data = {
            "request_id": str(request_id),
            "subtitle_file_path": "/path/to/subtitle.srt",
            "source_language": "en",
            "target_language": "es",
        }

        task = TranslationTask.model_validate(data)

        assert task.request_id == request_id
        assert task.subtitle_file_path == data["subtitle_file_path"]
        assert task.source_language == data["source_language"]
        assert task.target_language == data["target_language"]

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        request_id = uuid4()
        json_str = json.dumps(
            {
                "request_id": str(request_id),
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            }
        )

        task = TranslationTask.model_validate_json(json_str)

        assert task.request_id == request_id
        assert task.subtitle_file_path == "/path/to/subtitle.srt"

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        request_id = uuid4()
        original = TranslationTask(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = TranslationTask.model_validate(dumped)

        assert restored.request_id == original.request_id
        assert restored.subtitle_file_path == original.subtitle_file_path
        assert restored.source_language == original.source_language
        assert restored.target_language == original.target_language

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        request_id = uuid4()
        original = TranslationTask(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = TranslationTask.model_validate_json(json_str)

        assert restored.request_id == original.request_id
        assert restored.subtitle_file_path == original.subtitle_file_path


# ============================================================================
# HealthResponse Serialization Tests
# ============================================================================


class TestHealthResponseSerialization:
    """Test HealthResponse serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        response = HealthResponse()

        dumped = response.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["status"] == "healthy"
        assert dumped["version"] == "1.0.0"
        assert isinstance(dumped["timestamp"], datetime)

    def test_model_dump_json_serializes_datetime_to_iso_format(self):
        """Test model_dump_json() serializes datetime to ISO format."""
        custom_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        response = HealthResponse(timestamp=custom_timestamp)

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "healthy"
        assert parsed["version"] == "1.0.0"
        assert parsed["timestamp"] == "2024-01-01T12:00:00Z"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        timestamp = datetime.now(timezone.utc)
        data = {
            "status": "degraded",
            "version": "2.0.0",
            "timestamp": timestamp.isoformat(),
        }

        response = HealthResponse.model_validate(data)

        assert response.status == "degraded"
        assert response.version == "2.0.0"
        assert response.timestamp.tzinfo == timezone.utc

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        json_str = json.dumps(
            {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        )

        response = HealthResponse.model_validate_json(json_str)

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.timestamp.tzinfo == timezone.utc

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = HealthResponse(
            status="degraded",
            version="2.0.0",
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = HealthResponse.model_validate(dumped)

        assert restored.status == original.status
        assert restored.version == original.version

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        original = HealthResponse(
            status="healthy",
            version="1.0.0",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = HealthResponse.model_validate_json(json_str)

        assert restored.status == original.status
        assert restored.version == original.version


# ============================================================================
# SubtitleEvent Serialization Tests
# ============================================================================


class TestSubtitleEventSerialization:
    """Test SubtitleEvent serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
            payload={
                "subtitle_path": "/path/to/subtitle.srt",
                "language": "en",
            },
        )

        dumped = event.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["event_type"] == EventType.SUBTITLE_READY
        assert str(dumped["job_id"]) == str(job_id)
        assert dumped["source"] == "downloader"
        assert dumped["payload"] == {
            "subtitle_path": "/path/to/subtitle.srt",
            "language": "en",
        }

    def test_model_dump_json_serializes_enum_to_string(self):
        """Test model_dump_json() serializes enum to string value."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
        )

        json_str = event.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "subtitle.ready"
        assert isinstance(parsed["event_type"], str)

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
        )

        json_str = event.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["job_id"] == str(job_id)
        assert isinstance(parsed["job_id"], str)

    def test_model_dump_json_serializes_datetime_to_iso_format(self):
        """Test model_dump_json() serializes datetime to ISO format."""
        job_id = uuid4()
        custom_timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
            timestamp=custom_timestamp,
        )

        json_str = event.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["timestamp"] == "2024-01-01T12:00:00Z"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        job_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        data = {
            "event_type": "subtitle.ready",
            "job_id": str(job_id),
            "timestamp": timestamp.isoformat(),
            "source": "downloader",
            "payload": {"subtitle_path": "/path/to/subtitle.srt"},
        }

        event = SubtitleEvent.model_validate(data)

        assert event.event_type == EventType.SUBTITLE_READY
        assert event.job_id == job_id
        assert event.source == "downloader"
        assert event.payload == {"subtitle_path": "/path/to/subtitle.srt"}

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        job_id = uuid4()
        json_str = json.dumps(
            {
                "event_type": "subtitle.ready",
                "job_id": str(job_id),
                "timestamp": "2024-01-01T12:00:00Z",
                "source": "downloader",
                "payload": {"subtitle_path": "/path/to/subtitle.srt"},
            }
        )

        event = SubtitleEvent.model_validate_json(json_str)

        assert event.event_type == EventType.SUBTITLE_READY
        assert event.job_id == job_id
        assert event.source == "downloader"

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        job_id = uuid4()
        original = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
            payload={
                "subtitle_path": "/path/to/subtitle.srt",
                "language": "en",
            },
            metadata={"version": "1.0.0"},
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = SubtitleEvent.model_validate(dumped)

        assert restored.event_type == original.event_type
        assert restored.job_id == original.job_id
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.metadata == original.metadata

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        job_id = uuid4()
        original = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
            payload={"subtitle_path": "/path/to/subtitle.srt"},
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = SubtitleEvent.model_validate_json(json_str)

        assert restored.event_type == original.event_type
        assert restored.job_id == original.job_id
        assert restored.source == original.source
        assert restored.payload == original.payload


# ============================================================================
# TranslationCheckpoint Serialization Tests
# ============================================================================


class TestTranslationCheckpointSerialization:
    """Test TranslationCheckpoint serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            completed_chunks=[0, 1, 2],
            translated_segments=[{"index": 1, "text": "Hello"}],
            checkpoint_path="/path/to/checkpoint.json",
        )

        dumped = checkpoint.model_dump()

        assert isinstance(dumped, dict)
        assert str(dumped["request_id"]) == str(request_id)
        assert dumped["total_chunks"] == 10
        assert dumped["completed_chunks"] == [0, 1, 2]
        assert dumped["translated_segments"] == [{"index": 1, "text": "Hello"}]

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
        )

        json_str = checkpoint.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["request_id"] == str(request_id)
        assert isinstance(parsed["request_id"], str)

    def test_model_dump_json_serializes_datetime_to_iso_format(self):
        """Test model_dump_json() serializes datetime to ISO format."""
        request_id = uuid4()
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        updated_at = datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc)

        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
            created_at=created_at,
            updated_at=updated_at,
        )

        json_str = checkpoint.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["created_at"] == "2024-01-01T12:00:00Z"
        assert parsed["updated_at"] == "2024-01-01T12:05:00Z"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        request_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        data = {
            "request_id": str(request_id),
            "subtitle_file_path": "/path/to/subtitle.srt",
            "source_language": "en",
            "target_language": "es",
            "total_chunks": 10,
            "completed_chunks": [0, 1, 2],
            "translated_segments": [{"index": 1, "text": "Hello"}],
            "checkpoint_path": "/path/to/checkpoint.json",
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
        }

        checkpoint = TranslationCheckpoint.model_validate(data)

        assert checkpoint.request_id == request_id
        assert checkpoint.total_chunks == 10
        assert checkpoint.completed_chunks == [0, 1, 2]
        expected_segments = [{"index": 1, "text": "Hello"}]
        assert checkpoint.translated_segments == expected_segments

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        request_id = uuid4()
        json_str = json.dumps(
            {
                "request_id": str(request_id),
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
                "total_chunks": 10,
                "completed_chunks": [0, 1, 2],
                "translated_segments": [],
                "checkpoint_path": "/path/to/checkpoint.json",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:05:00Z",
            }
        )

        checkpoint = TranslationCheckpoint.model_validate_json(json_str)

        assert checkpoint.request_id == request_id
        assert checkpoint.total_chunks == 10
        assert checkpoint.completed_chunks == [0, 1, 2]

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        request_id = uuid4()
        original = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            completed_chunks=[0, 1, 2, 3],
            translated_segments=[{"index": 1, "text": "Hello"}],
            checkpoint_path="/path/to/checkpoint.json",
        )

        # Serialize to dict
        dumped = original.model_dump()
        # Deserialize from dict
        restored = TranslationCheckpoint.model_validate(dumped)

        assert restored.request_id == original.request_id
        assert restored.total_chunks == original.total_chunks
        assert restored.completed_chunks == original.completed_chunks
        assert restored.translated_segments == original.translated_segments

    def test_round_trip_json_serialization(self):
        """Test serialize to JSON → deserialize maintains data integrity."""
        request_id = uuid4()
        original = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()
        # Deserialize from JSON
        restored = TranslationCheckpoint.model_validate_json(json_str)

        assert restored.request_id == original.request_id
        assert restored.subtitle_file_path == original.subtitle_file_path
        assert restored.total_chunks == original.total_chunks
