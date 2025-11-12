"""Comprehensive tests for new schema models: EventEnvelope, SubtitleDownloadRequest, TranslationRequest, JobRecord, and factory functions."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import HttpUrl, ValidationError

from common.schemas import (
    EventEnvelope,
    EventType,
    JobRecord,
    SubtitleDownloadRequest,
    SubtitleStatus,
    TranslationRequest,
    create_subtitle_ready_event,
)


class TestEventEnvelope:
    """Test EventEnvelope model validation and auto-generation."""

    def test_event_envelope_auto_generates_event_id(self):
        """Verify event_id is auto-generated UUID."""
        envelope = EventEnvelope(
            event_type=EventType.SUBTITLE_READY,
            source="downloader",
            payload={"test": "data"},
        )

        assert isinstance(envelope.event_id, UUID)
        assert envelope.event_id is not None

    def test_event_envelope_auto_generates_timestamp(self):
        """Verify timestamp is auto-generated with UTC."""
        before = datetime.now(timezone.utc)
        envelope = EventEnvelope(
            event_type=EventType.SUBTITLE_READY,
            source="downloader",
            payload={"test": "data"},
        )
        after = datetime.now(timezone.utc)

        assert isinstance(envelope.timestamp, datetime)
        assert envelope.timestamp.tzinfo == timezone.utc
        assert before <= envelope.timestamp <= after

    def test_event_envelope_validates_event_type_enum(self):
        """Validate event_type from enum."""
        envelope = EventEnvelope(
            event_type=EventType.SUBTITLE_READY,
            source="downloader",
            payload={"test": "data"},
        )

        assert envelope.event_type == EventType.SUBTITLE_READY
        assert isinstance(envelope.event_type, EventType)

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.SUBTITLE_READY,
            EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            EventType.SUBTITLE_TRANSLATE_REQUESTED,
            EventType.TRANSLATION_COMPLETED,
            EventType.JOB_FAILED,
        ],
    )
    def test_event_envelope_accepts_all_event_types(self, event_type):
        """Test that EventEnvelope accepts all EventType enum values."""
        envelope = EventEnvelope(
            event_type=event_type,
            source="downloader",
            payload={"test": "data"},
        )

        assert envelope.event_type == event_type

    def test_event_envelope_with_optional_fields(self):
        """Test EventEnvelope with all optional fields."""
        correlation_id = uuid4()
        metadata = {"version": "1.0.0", "environment": "test"}

        envelope = EventEnvelope(
            event_type=EventType.SUBTITLE_READY,
            source="downloader",
            payload={"test": "data"},
            correlation_id=correlation_id,
            metadata=metadata,
        )

        assert envelope.correlation_id == correlation_id
        assert envelope.metadata == metadata

    def test_event_envelope_without_optional_fields(self):
        """Test EventEnvelope without optional fields."""
        envelope = EventEnvelope(
            event_type=EventType.SUBTITLE_READY,
            source="downloader",
            payload={"test": "data"},
        )

        assert envelope.correlation_id is None
        assert envelope.metadata is None

    def test_event_envelope_requires_payload(self):
        """Test that payload is required."""
        with pytest.raises(ValidationError) as exc_info:
            EventEnvelope(
                event_type=EventType.SUBTITLE_READY,
                source="downloader",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("payload",) for error in errors)

    def test_event_envelope_requires_source(self):
        """Test that source is required."""
        with pytest.raises(ValidationError) as exc_info:
            EventEnvelope(
                event_type=EventType.SUBTITLE_READY,
                payload={"test": "data"},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("source",) for error in errors)

    def test_event_envelope_serialization(self):
        """Test that EventEnvelope can be serialized to JSON."""
        envelope = EventEnvelope(
            event_type=EventType.SUBTITLE_READY,
            source="downloader",
            payload={"test": "data"},
        )

        json_str = envelope.model_dump_json()
        assert isinstance(json_str, str)
        assert "subtitle.ready" in json_str
        assert "downloader" in json_str


class TestSubtitleDownloadRequest:
    """Test SubtitleDownloadRequest validation."""

    @pytest.mark.parametrize(
        "video_url",
        [
            "https://example.com/video.mp4",
            "http://example.com/video.mp4",
            "https://subdomain.example.com/path/to/video.mkv",
            "https://example.com:8080/video.mp4",
        ],
    )
    def test_valid_http_urls(self, video_url):
        """Test that valid HTTP URLs pass validation."""
        request = SubtitleDownloadRequest(
            video_url=video_url,
            video_title="Test Video",
            language="en",
        )

        assert isinstance(request.video_url, HttpUrl)
        assert str(request.video_url) == video_url

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "not-a-url",
            "ftp://example.com/video.mp4",
            "file:///path/to/video.mp4",
            "invalid://example.com",
            "",
        ],
    )
    def test_invalid_urls_raise_validation_error(self, invalid_url):
        """Test that invalid URLs raise ValidationError."""
        with pytest.raises(ValidationError):
            SubtitleDownloadRequest(
                video_url=invalid_url,
                video_title="Test Video",
                language="en",
            )

    @pytest.mark.parametrize(
        "language",
        ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko"],
    )
    def test_valid_language_codes(self, language):
        """Test that valid ISO 639-1 language codes pass validation."""
        request = SubtitleDownloadRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language=language,
        )

        assert request.language == language

    @pytest.mark.parametrize(
        "invalid_language",
        [
            "ENG",
            "english",
            "e",
            "en-US",
            "123",
            "",
        ],
    )
    def test_invalid_language_codes_raise_validation_error(self, invalid_language):
        """
        Test that invalid language codes raise ValidationError.

        Note: "xx" is not included here because it matches the pattern ^[a-z]{2}$
        Pattern validation only checks format (2 lowercase letters), not actual
        ISO 639-1 language code validity.
        """
        with pytest.raises(ValidationError):
            SubtitleDownloadRequest(
                video_url="https://example.com/video.mp4",
                video_title="Test Video",
                language=invalid_language,
            )

    @pytest.mark.parametrize(
        "video_title",
        [
            "A",
            "Test Video",
            "A" * 500,  # Max length
            "Movie Title (2024)",
            "Episode 1: The Beginning",
        ],
    )
    def test_valid_video_titles(self, video_title):
        """Test that valid video titles pass validation."""
        request = SubtitleDownloadRequest(
            video_url="https://example.com/video.mp4",
            video_title=video_title,
            language="en",
        )

        assert request.video_title == video_title

    @pytest.mark.parametrize(
        "invalid_title",
        [
            "",  # Empty string
            "A" * 501,  # Too long
        ],
    )
    def test_invalid_video_titles_raise_validation_error(self, invalid_title):
        """Test that invalid video titles raise ValidationError."""
        with pytest.raises(ValidationError):
            SubtitleDownloadRequest(
                video_url="https://example.com/video.mp4",
                video_title=invalid_title,
                language="en",
            )

    def test_empty_preferred_sources_defaults_to_empty_list(self):
        """Test that empty preferred_sources defaults to []."""
        request = SubtitleDownloadRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert request.preferred_sources == []

    def test_preferred_sources_with_values(self):
        """Test that preferred_sources can contain values."""
        request = SubtitleDownloadRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles", "subscene"],
        )

        assert request.preferred_sources == ["opensubtitles", "subscene"]

    def test_target_language_optional(self):
        """Test that target_language is optional."""
        request = SubtitleDownloadRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert request.target_language is None

    def test_target_language_with_valid_code(self):
        """Test that target_language accepts valid ISO code."""
        request = SubtitleDownloadRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
        )

        assert request.target_language == "es"

    def test_target_language_with_invalid_code_raises_error(self):
        """Test that invalid target_language raises ValidationError."""
        with pytest.raises(ValidationError):
            SubtitleDownloadRequest(
                video_url="https://example.com/video.mp4",
                video_title="Test Video",
                language="en",
                target_language="SPANISH",
            )


class TestTranslationRequest:
    """Test TranslationRequest validation."""

    @pytest.mark.parametrize(
        "subtitle_path",
        [
            "/path/to/subtitle.srt",
            "/storage/subtitles/123.srt",
            "relative/path/subtitle.srt",
            "/very/long/path/to/subtitle/file.srt",
        ],
    )
    def test_valid_subtitle_file_paths(self, subtitle_path):
        """Test that non-empty subtitle_file_path passes validation."""
        request = TranslationRequest(
            subtitle_file_path=subtitle_path,
            source_language="en",
            target_language="es",
        )

        assert request.subtitle_file_path == subtitle_path

    def test_empty_subtitle_file_path_raises_validation_error(self):
        """Test that empty subtitle_file_path raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TranslationRequest(
                subtitle_file_path="",
                source_language="en",
                target_language="es",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("subtitle_file_path",) for error in errors)

    @pytest.mark.parametrize(
        "source_lang,target_lang",
        [
            ("en", "es"),
            ("fr", "de"),
            ("it", "pt"),
            ("ja", "ko"),
            ("zh", "ru"),
        ],
    )
    def test_valid_iso_language_codes(self, source_lang, target_lang):
        """Test that valid ISO language codes pass validation."""
        request = TranslationRequest(
            subtitle_file_path="/path/to/subtitle.srt",
            source_language=source_lang,
            target_language=target_lang,
        )

        assert request.source_language == source_lang
        assert request.target_language == target_lang

    @pytest.mark.parametrize(
        "invalid_language",
        [
            "ENG",
            "english",
            "e",
            "en-US",
            "123",
            "",
        ],
    )
    def test_invalid_source_language_raises_validation_error(self, invalid_language):
        """Test that invalid source_language raises ValidationError."""
        with pytest.raises(ValidationError):
            TranslationRequest(
                subtitle_file_path="/path/to/subtitle.srt",
                source_language=invalid_language,
                target_language="es",
            )

    @pytest.mark.parametrize(
        "invalid_language",
        [
            "SPANISH",
            "es-ES",
            "e",
            "123",
            "",
        ],
    )
    def test_invalid_target_language_raises_validation_error(self, invalid_language):
        """Test that invalid target_language raises ValidationError."""
        with pytest.raises(ValidationError):
            TranslationRequest(
                subtitle_file_path="/path/to/subtitle.srt",
                source_language="en",
                target_language=invalid_language,
            )

    def test_video_title_optional(self):
        """Test that video_title is optional."""
        request = TranslationRequest(
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        assert request.video_title is None

    def test_video_title_with_value(self):
        """Test that video_title can be provided."""
        request = TranslationRequest(
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            video_title="Test Video",
        )

        assert request.video_title == "Test Video"


class TestJobRecord:
    """Test JobRecord construction and validation."""

    def test_job_record_with_all_required_fields(self):
        """Test JobRecord with all required fields present."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=SubtitleStatus.PENDING,
            created_at=created_at,
            updated_at=updated_at,
            task_type="download",
        )

        assert record.job_id == job_id
        assert record.status == SubtitleStatus.PENDING
        assert record.created_at == created_at
        assert record.updated_at == updated_at
        assert record.task_type == "download"

    @pytest.mark.parametrize(
        "task_type",
        ["download", "translation", "download_with_translation"],
    )
    def test_job_record_task_type_literal_values(self, task_type):
        """Test that task_type accepts all valid literal values."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=SubtitleStatus.PENDING,
            created_at=created_at,
            updated_at=updated_at,
            task_type=task_type,
        )

        assert record.task_type == task_type

    def test_job_record_invalid_task_type_raises_error(self):
        """Test that invalid task_type raises ValidationError."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        with pytest.raises(ValidationError):
            JobRecord(
                job_id=job_id,
                status=SubtitleStatus.PENDING,
                created_at=created_at,
                updated_at=updated_at,
                task_type="invalid_type",
            )

    @pytest.mark.parametrize(
        "status",
        [
            SubtitleStatus.PENDING,
            SubtitleStatus.DOWNLOAD_QUEUED,
            SubtitleStatus.DOWNLOAD_IN_PROGRESS,
            SubtitleStatus.TRANSLATE_QUEUED,
            SubtitleStatus.TRANSLATE_IN_PROGRESS,
            SubtitleStatus.DONE,
            SubtitleStatus.FAILED,
        ],
    )
    def test_job_record_status_enum_integration(self, status):
        """Test that status enum integration works correctly."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            task_type="download",
        )

        assert record.status == status

    def test_job_record_optional_fields_handled_correctly(self):
        """Test that optional fields are handled correctly."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=SubtitleStatus.PENDING,
            created_at=created_at,
            updated_at=updated_at,
            task_type="download",
        )

        assert record.video_url is None
        assert record.video_title is None
        assert record.language is None
        assert record.target_language is None
        assert record.result_url is None
        assert record.error_message is None
        assert record.progress_percentage == 0

    def test_job_record_with_all_optional_fields(self):
        """Test JobRecord with all optional fields populated."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=SubtitleStatus.DONE,
            created_at=created_at,
            updated_at=updated_at,
            task_type="download_with_translation",
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            result_url="https://example.com/subtitles/123.srt",
            error_message=None,
            progress_percentage=100,
        )

        assert record.video_url == "https://example.com/video.mp4"
        assert record.video_title == "Test Video"
        assert record.language == "en"
        assert record.target_language == "es"
        assert record.result_url == "https://example.com/subtitles/123.srt"
        assert record.progress_percentage == 100

    @pytest.mark.parametrize(
        "progress",
        [0, 25, 50, 75, 100],
    )
    def test_job_record_progress_percentage_bounds(self, progress):
        """Test that progress_percentage is within bounds (0-100)."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=SubtitleStatus.DOWNLOAD_IN_PROGRESS,
            created_at=created_at,
            updated_at=updated_at,
            task_type="download",
            progress_percentage=progress,
        )

        assert record.progress_percentage == progress

    @pytest.mark.parametrize(
        "invalid_progress",
        [-1, 101, 150, -10],
    )
    def test_job_record_invalid_progress_raises_error(self, invalid_progress):
        """Test that progress_percentage outside bounds raises ValidationError."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        with pytest.raises(ValidationError):
            JobRecord(
                job_id=job_id,
                status=SubtitleStatus.DOWNLOAD_IN_PROGRESS,
                created_at=created_at,
                updated_at=updated_at,
                task_type="download",
                progress_percentage=invalid_progress,
            )

    def test_job_record_with_error_message(self):
        """Test JobRecord with error_message populated."""
        job_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

        record = JobRecord(
            job_id=job_id,
            status=SubtitleStatus.FAILED,
            created_at=created_at,
            updated_at=updated_at,
            task_type="download",
            error_message="Subtitle file not found",
        )

        assert record.error_message == "Subtitle file not found"
        assert record.status == SubtitleStatus.FAILED


class TestCreateSubtitleReadyEvent:
    """Test create_subtitle_ready_event factory function."""

    def test_factory_returns_correct_subtitle_event(self):
        """Test that factory returns correct SubtitleEvent."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"

        event = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
        )

        assert event.event_type == EventType.SUBTITLE_READY
        assert event.job_id == job_id
        assert event.source == "downloader"  # Default source
        assert event.payload["subtitle_path"] == subtitle_path
        assert event.payload["language"] == language

    def test_factory_payload_structure_validation(self):
        """Test that payload structure is correct."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"

        event = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
        )

        assert "subtitle_path" in event.payload
        assert "language" in event.payload
        assert event.payload["subtitle_path"] == subtitle_path
        assert event.payload["language"] == language

    def test_factory_with_download_url(self):
        """Test factory with optional download_url parameter."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"
        download_url = "https://example.com/subtitles/123.srt"

        event = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
            download_url=download_url,
        )

        assert event.payload["download_url"] == download_url
        assert "subtitle_path" in event.payload
        assert "language" in event.payload

    def test_factory_without_download_url(self):
        """Test factory without download_url parameter."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"

        event = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
        )

        assert "download_url" not in event.payload

    def test_factory_with_custom_source(self):
        """Test factory with custom source parameter."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"
        custom_source = "scanner"

        event = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
            source=custom_source,
        )

        assert event.source == custom_source

    def test_factory_optional_parameters_handled_correctly(self):
        """Test that optional parameters are handled correctly."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"

        # Without optional parameters
        event1 = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
        )

        # With optional parameters
        event2 = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
            source="translator",
            download_url="https://example.com/subtitles/123.srt",
        )

        assert event1.source == "downloader"
        assert "download_url" not in event1.payload

        assert event2.source == "translator"
        assert "download_url" in event2.payload

    def test_factory_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated."""
        job_id = uuid4()
        subtitle_path = "/storage/subtitles/123.srt"
        language = "en"

        before = datetime.now(timezone.utc)
        event = create_subtitle_ready_event(
            job_id=job_id,
            subtitle_path=subtitle_path,
            language=language,
        )
        after = datetime.now(timezone.utc)

        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo == timezone.utc
        assert before <= event.timestamp <= after
