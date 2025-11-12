"""Comprehensive validation tests for common schema models and enums."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

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
# Enum Validation Tests
# ============================================================================


class TestSubtitleStatusEnum:
    """Test SubtitleStatus enum validation."""

    @pytest.mark.parametrize(
        "status_value",
        [
            SubtitleStatus.PENDING,
            SubtitleStatus.DOWNLOAD_QUEUED,
            SubtitleStatus.DOWNLOAD_IN_PROGRESS,
            SubtitleStatus.TRANSLATE_QUEUED,
            SubtitleStatus.TRANSLATE_IN_PROGRESS,
            SubtitleStatus.DONE,
            SubtitleStatus.FAILED,
            SubtitleStatus.SUBTITLE_MISSING,
            SubtitleStatus.DOWNLOADING,  # Legacy
            SubtitleStatus.TRANSLATING,  # Legacy
            SubtitleStatus.COMPLETED,  # Legacy
        ],
    )
    def test_all_subtitle_status_values_are_valid(self, status_value):
        """Test that all SubtitleStatus enum values are valid."""
        assert isinstance(status_value, SubtitleStatus)
        assert isinstance(status_value.value, str)

    @pytest.mark.parametrize(
        "status_string",
        [
            "pending",
            "download_queued",
            "download_in_progress",
            "translate_queued",
            "translate_in_progress",
            "done",
            "failed",
            "subtitle_missing",
            "downloading",  # Legacy
            "translating",  # Legacy
            "completed",  # Legacy
        ],
    )
    def test_subtitle_status_accepts_string_values(self, status_string):
        """Test that SubtitleStatus accepts string values."""
        status = SubtitleStatus(status_string)
        assert status.value == status_string

    @pytest.mark.parametrize(
        "invalid_status",
        [
            "invalid_status",
            "PENDING",  # Wrong case
            "pending_status",
            "",
            None,
            123,
        ],
    )
    def test_invalid_subtitle_status_raises_error(self, invalid_status):
        """Test that invalid SubtitleStatus values raise ValidationError."""
        with pytest.raises((ValueError, ValidationError, TypeError)):
            if invalid_status is None:
                # None will raise TypeError when used in model
                SubtitleResponse(
                    video_url="https://example.com/video.mp4",
                    video_title="Test",
                    language="en",
                    status=invalid_status,
                )
            else:
                SubtitleStatus(invalid_status)


class TestEventTypeEnum:
    """Test EventType enum validation."""

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            EventType.SUBTITLE_READY,
            EventType.SUBTITLE_MISSING,
            EventType.SUBTITLE_TRANSLATE_REQUESTED,
            EventType.SUBTITLE_TRANSLATED,
            EventType.TRANSLATION_COMPLETED,
            EventType.JOB_FAILED,
            EventType.MEDIA_FILE_DETECTED,
            EventType.SUBTITLE_REQUESTED,
        ],
    )
    def test_all_event_type_values_are_valid(self, event_type):
        """Test that all EventType enum values are valid."""
        assert isinstance(event_type, EventType)
        assert isinstance(event_type.value, str)

    @pytest.mark.parametrize(
        "event_string",
        [
            "subtitle.download.requested",
            "subtitle.ready",
            "subtitle.missing",
            "subtitle.translate.requested",
            "subtitle.translated",
            "translation.completed",
            "job.failed",
            "media.file.detected",
            "subtitle.requested",
        ],
    )
    def test_event_type_accepts_string_values(self, event_string):
        """Test that EventType accepts string values."""
        event = EventType(event_string)
        assert event.value == event_string

    @pytest.mark.parametrize(
        "invalid_event",
        [
            "invalid.event",
            "subtitle.ready.invalid",
            "",
            None,
            123,
        ],
    )
    def test_invalid_event_type_raises_error(self, invalid_event):
        """Test that invalid EventType values raise ValidationError."""
        with pytest.raises((ValueError, ValidationError, TypeError)):
            if invalid_event is None:
                SubtitleEvent(
                    event_type=invalid_event,
                    job_id=uuid4(),
                    source="test",
                )
            else:
                EventType(invalid_event)


# ============================================================================
# SubtitleRequest Validation Tests
# ============================================================================


class TestSubtitleRequestValidation:
    """Test SubtitleRequest model validation."""

    def test_valid_subtitle_request(self):
        """Test valid SubtitleRequest passes validation."""
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert request.video_url == "https://example.com/video.mp4"
        assert request.video_title == "Test Video"
        assert request.language == "en"
        assert request.target_language is None
        assert request.preferred_sources == []

    def test_subtitle_request_with_all_fields(self):
        """Test SubtitleRequest with all fields populated."""
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            preferred_sources=["opensubtitles", "subscene"],
        )

        assert request.target_language == "es"
        assert request.preferred_sources == ["opensubtitles", "subscene"]

    def test_subtitle_request_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleRequest()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "video_url" in error_fields
        assert "video_title" in error_fields
        assert "language" in error_fields

    def test_subtitle_request_empty_preferred_sources_defaults_to_empty_list(
        self,
    ):
        """Test that preferred_sources defaults to empty list."""
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert request.preferred_sources == []
        assert isinstance(request.preferred_sources, list)

    def test_subtitle_request_optional_target_language(self):
        """Test that target_language is optional."""
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert request.target_language is None


# ============================================================================
# SubtitleResponse Validation Tests
# ============================================================================


class TestSubtitleResponseValidation:
    """Test SubtitleResponse model validation."""

    def test_valid_subtitle_response(self):
        """Test valid SubtitleResponse passes validation."""
        response = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert isinstance(response.id, UUID)
        assert response.video_url == "https://example.com/video.mp4"
        assert response.video_title == "Test Video"
        assert response.language == "en"
        assert response.status == SubtitleStatus.PENDING
        assert isinstance(response.created_at, datetime)
        assert isinstance(response.updated_at, datetime)

    def test_subtitle_response_auto_generates_id(self):
        """Test that id is auto-generated."""
        response1 = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )
        response2 = SubtitleResponse(
            video_url="https://example.com/video2.mp4",
            video_title="Test Video 2",
            language="en",
        )

        assert response1.id != response2.id
        assert isinstance(response1.id, UUID)
        assert isinstance(response2.id, UUID)

    def test_subtitle_response_auto_generates_timestamps(self):
        """Test that timestamps are auto-generated."""
        before = datetime.now(timezone.utc)
        response = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )
        after = datetime.now(timezone.utc)

        assert before <= response.created_at <= after
        assert before <= response.updated_at <= after
        assert response.created_at.tzinfo == timezone.utc
        assert response.updated_at.tzinfo == timezone.utc

    def test_subtitle_response_with_all_fields(self):
        """Test SubtitleResponse with all fields populated."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        response = SubtitleResponse(
            id=job_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            status=SubtitleStatus.DONE,
            created_at=created_at,
            updated_at=updated_at,
            error_message=None,
            download_url="https://example.com/subtitles/123.srt",
        )

        assert response.id == job_id
        assert response.status == SubtitleStatus.DONE
        assert response.target_language == "es"
        assert response.download_url == "https://example.com/subtitles/123.srt"

    def test_subtitle_response_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleResponse()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "video_url" in error_fields
        assert "video_title" in error_fields
        assert "language" in error_fields

    @pytest.mark.parametrize(
        "status",
        [
            SubtitleStatus.PENDING,
            SubtitleStatus.DOWNLOAD_QUEUED,
            SubtitleStatus.DOWNLOAD_IN_PROGRESS,
            SubtitleStatus.DONE,
            SubtitleStatus.FAILED,
        ],
    )
    def test_subtitle_response_accepts_all_status_values(self, status):
        """Test that SubtitleResponse accepts all SubtitleStatus values."""
        response = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            status=status,
        )

        assert response.status == status

    def test_subtitle_response_optional_fields(self):
        """Test that optional fields can be None."""
        response = SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert response.target_language is None
        assert response.error_message is None
        assert response.download_url is None


# ============================================================================
# DownloadTask Validation Tests
# ============================================================================


class TestDownloadTaskValidation:
    """Test DownloadTask model validation."""

    def test_valid_download_task(self):
        """Test valid DownloadTask passes validation."""
        request_id = uuid4()
        task = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert task.request_id == request_id
        assert task.video_url == "https://example.com/video.mp4"
        assert task.video_title == "Test Video"
        assert task.language == "en"
        assert task.preferred_sources == []

    def test_download_task_with_preferred_sources(self):
        """Test DownloadTask with preferred_sources."""
        request_id = uuid4()
        task = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles", "subscene"],
        )

        assert task.preferred_sources == ["opensubtitles", "subscene"]

    def test_download_task_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadTask()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "request_id" in error_fields
        assert "video_url" in error_fields
        assert "video_title" in error_fields
        assert "language" in error_fields

    def test_download_task_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadTask(
                request_id="not-a-uuid",
                video_url="https://example.com/video.mp4",
                video_title="Test Video",
                language="en",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("request_id",) for error in errors)

    def test_download_task_empty_preferred_sources_defaults_to_empty_list(
        self,
    ):
        """Test that preferred_sources defaults to empty list."""
        request_id = uuid4()
        task = DownloadTask(
            request_id=request_id,
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert task.preferred_sources == []
        assert isinstance(task.preferred_sources, list)


# ============================================================================
# TranslationTask Validation Tests
# ============================================================================


class TestTranslationTaskValidation:
    """Test TranslationTask model validation."""

    def test_valid_translation_task(self):
        """Test valid TranslationTask passes validation."""
        request_id = uuid4()
        task = TranslationTask(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        assert task.request_id == request_id
        assert task.subtitle_file_path == "/path/to/subtitle.srt"
        assert task.source_language == "en"
        assert task.target_language == "es"

    def test_translation_task_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranslationTask()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "request_id" in error_fields
        assert "subtitle_file_path" in error_fields
        assert "source_language" in error_fields
        assert "target_language" in error_fields

    def test_translation_task_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranslationTask(
                request_id="not-a-uuid",
                subtitle_file_path="/path/to/subtitle.srt",
                source_language="en",
                target_language="es",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("request_id",) for error in errors)

    def test_translation_task_allows_empty_subtitle_file_path(self):
        """Test empty subtitle_file_path allowed (no min_length)."""
        request_id = uuid4()
        task = TranslationTask(
            request_id=request_id,
            subtitle_file_path="",
            source_language="en",
            target_language="es",
        )

        assert task.subtitle_file_path == ""


# ============================================================================
# HealthResponse Validation Tests
# ============================================================================


class TestHealthResponseValidation:
    """Test HealthResponse model validation."""

    def test_valid_health_response(self):
        """Test valid HealthResponse passes validation."""
        response = HealthResponse()

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert isinstance(response.timestamp, datetime)
        assert response.timestamp.tzinfo == timezone.utc

    def test_health_response_auto_generates_timestamp(self):
        """Test that timestamp is auto-generated."""
        before = datetime.now(timezone.utc)
        response = HealthResponse()
        after = datetime.now(timezone.utc)

        assert before <= response.timestamp <= after
        assert response.timestamp.tzinfo == timezone.utc

    def test_health_response_with_custom_values(self):
        """Test HealthResponse with custom values."""
        custom_timestamp = datetime.now(timezone.utc)
        response = HealthResponse(
            status="degraded",
            version="2.0.0",
            timestamp=custom_timestamp,
        )

        assert response.status == "degraded"
        assert response.version == "2.0.0"
        assert response.timestamp == custom_timestamp

    def test_health_response_default_values(self):
        """Test HealthResponse default values."""
        response = HealthResponse()

        assert response.status == "healthy"
        assert response.version == "1.0.0"


# ============================================================================
# SubtitleEvent Validation Tests
# ============================================================================


class TestSubtitleEventValidation:
    """Test SubtitleEvent model validation."""

    def test_valid_subtitle_event(self):
        """Test valid SubtitleEvent passes validation."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
        )

        assert event.event_type == EventType.SUBTITLE_READY
        assert event.job_id == job_id
        assert event.source == "downloader"
        assert event.payload == {}
        assert event.metadata is None
        assert isinstance(event.timestamp, datetime)

    def test_subtitle_event_auto_generates_timestamp(self):
        """Test that timestamp is auto-generated."""
        before = datetime.now(timezone.utc)
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
        )
        after = datetime.now(timezone.utc)

        assert before <= event.timestamp <= after
        assert event.timestamp.tzinfo == timezone.utc

    def test_subtitle_event_with_payload(self):
        """Test SubtitleEvent with payload."""
        job_id = uuid4()
        payload = {"subtitle_path": "/path/to/subtitle.srt", "language": "en"}

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
            payload=payload,
        )

        assert event.payload == payload

    def test_subtitle_event_with_metadata(self):
        """Test SubtitleEvent with metadata."""
        job_id = uuid4()
        metadata = {"version": "1.0.0", "environment": "test"}

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
            metadata=metadata,
        )

        assert event.metadata == metadata

    def test_subtitle_event_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleEvent()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "event_type" in error_fields
        assert "job_id" in error_fields
        assert "source" in error_fields

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            EventType.SUBTITLE_READY,
            EventType.SUBTITLE_MISSING,
            EventType.SUBTITLE_TRANSLATE_REQUESTED,
            EventType.TRANSLATION_COMPLETED,
            EventType.JOB_FAILED,
        ],
    )
    def test_subtitle_event_accepts_all_event_types(self, event_type):
        """Test that SubtitleEvent accepts all EventType values."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=event_type,
            job_id=job_id,
            source="downloader",
        )

        assert event.event_type == event_type

    def test_subtitle_event_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id="not-a-uuid",
                source="downloader",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("job_id",) for error in errors)

    def test_subtitle_event_default_payload(self):
        """Test that payload defaults to empty dict."""
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            source="downloader",
        )

        assert event.payload == {}
        assert isinstance(event.payload, dict)


# ============================================================================
# TranslationCheckpoint Validation Tests
# ============================================================================


class TestTranslationCheckpointValidation:
    """Test TranslationCheckpoint model validation."""

    def test_valid_translation_checkpoint(self):
        """Test valid TranslationCheckpoint passes validation."""
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
        )

        assert checkpoint.request_id == request_id
        assert checkpoint.subtitle_file_path == "/path/to/subtitle.srt"
        assert checkpoint.source_language == "en"
        assert checkpoint.target_language == "es"
        assert checkpoint.total_chunks == 10
        assert checkpoint.completed_chunks == []
        assert checkpoint.translated_segments == []
        assert isinstance(checkpoint.created_at, datetime)
        assert isinstance(checkpoint.updated_at, datetime)

    def test_translation_checkpoint_auto_generates_timestamps(self):
        """Test that timestamps are auto-generated."""
        before = datetime.now(timezone.utc)
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
        )
        after = datetime.now(timezone.utc)

        assert before <= checkpoint.created_at <= after
        assert before <= checkpoint.updated_at <= after
        assert checkpoint.created_at.tzinfo == timezone.utc
        assert checkpoint.updated_at.tzinfo == timezone.utc

    def test_translation_checkpoint_with_completed_chunks(self):
        """Test TranslationCheckpoint with completed_chunks."""
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            completed_chunks=[0, 1, 2, 3],
            checkpoint_path="/path/to/checkpoint.json",
        )

        assert checkpoint.completed_chunks == [0, 1, 2, 3]

    def test_translation_checkpoint_with_translated_segments(self):
        """Test TranslationCheckpoint with translated_segments."""
        request_id = uuid4()
        segments = [
            {
                "index": 1,
                "start_time": "00:00:01,000",
                "end_time": "00:00:04,000",
                "text": "Hola mundo",
            }
        ]

        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            translated_segments=segments,
            checkpoint_path="/path/to/checkpoint.json",
        )

        assert checkpoint.translated_segments == segments

    def test_translation_checkpoint_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranslationCheckpoint()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "request_id" in error_fields
        assert "subtitle_file_path" in error_fields
        assert "source_language" in error_fields
        assert "target_language" in error_fields
        assert "total_chunks" in error_fields
        assert "checkpoint_path" in error_fields

    def test_translation_checkpoint_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranslationCheckpoint(
                request_id="not-a-uuid",
                subtitle_file_path="/path/to/subtitle.srt",
                source_language="en",
                target_language="es",
                total_chunks=10,
                checkpoint_path="/path/to/checkpoint.json",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("request_id",) for error in errors)

    def test_translation_checkpoint_invalid_total_chunks_type(self):
        """Test that invalid total_chunks type raises ValidationError."""
        request_id = uuid4()
        with pytest.raises(ValidationError) as exc_info:
            TranslationCheckpoint(
                request_id=request_id,
                subtitle_file_path="/path/to/subtitle.srt",
                source_language="en",
                target_language="es",
                total_chunks="not-an-int",
                checkpoint_path="/path/to/checkpoint.json",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("total_chunks",) for error in errors)

    def test_translation_checkpoint_default_completed_chunks(self):
        """Test that completed_chunks defaults to empty list."""
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
        )

        assert checkpoint.completed_chunks == []
        assert isinstance(checkpoint.completed_chunks, list)

    def test_translation_checkpoint_default_translated_segments(self):
        """Test that translated_segments defaults to empty list."""
        request_id = uuid4()
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=10,
            checkpoint_path="/path/to/checkpoint.json",
        )

        assert checkpoint.translated_segments == []
        assert isinstance(checkpoint.translated_segments, list)
