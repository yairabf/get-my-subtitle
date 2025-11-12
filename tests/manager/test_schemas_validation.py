"""Comprehensive validation tests for manager-specific schema models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from manager.schemas import (
    JellyfinWebhookPayload,
    QueueStatusResponse,
    SubtitleDownloadResponse,
    SubtitleRequestCreate,
    SubtitleRequestUpdate,
    SubtitleStatusResponse,
    SubtitleTranslateRequest,
    WebhookAcknowledgement,
)

# ============================================================================
# SubtitleRequestCreate Validation Tests
# ============================================================================


class TestSubtitleRequestCreateValidation:
    """Test SubtitleRequestCreate model validation."""

    def test_subtitle_request_create_inherits_from_subtitle_request(self):
        """Test that SubtitleRequestCreate inherits from SubtitleRequest."""
        request = SubtitleRequestCreate(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        assert request.video_url == "https://example.com/video.mp4"
        assert request.video_title == "Test Video"
        assert request.language == "en"

    def test_subtitle_request_create_with_all_fields(self):
        """Test SubtitleRequestCreate with all fields."""
        request = SubtitleRequestCreate(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            preferred_sources=["opensubtitles"],
        )

        assert request.target_language == "es"
        assert request.preferred_sources == ["opensubtitles"]

    def test_subtitle_request_create_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleRequestCreate()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "video_url" in error_fields
        assert "video_title" in error_fields
        assert "language" in error_fields


# ============================================================================
# SubtitleRequestUpdate Validation Tests
# ============================================================================


class TestSubtitleRequestUpdateValidation:
    """Test SubtitleRequestUpdate model validation."""

    def test_valid_subtitle_request_update(self):
        """Test valid SubtitleRequestUpdate passes validation."""
        update = SubtitleRequestUpdate(
            status="done",
            error_message="No errors",
            download_url="https://example.com/subtitles/123.srt",
        )

        assert update.status == "done"
        assert update.error_message == "No errors"
        assert update.download_url == "https://example.com/subtitles/123.srt"

    def test_subtitle_request_update_with_only_status(self):
        """Test SubtitleRequestUpdate with only status field."""
        update = SubtitleRequestUpdate(status="done")

        assert update.status == "done"
        assert update.error_message is None
        assert update.download_url is None

    def test_subtitle_request_update_missing_required_status(self):
        """Test that missing required status field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleRequestUpdate()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_subtitle_request_update_optional_fields(self):
        """Test that optional fields default to None when omitted."""
        update = SubtitleRequestUpdate(
            status="failed",
        )

        assert update.status == "failed"
        assert update.error_message is None
        assert update.download_url is None


# ============================================================================
# SubtitleStatusResponse Validation Tests
# ============================================================================


class TestSubtitleStatusResponseValidation:
    """Test SubtitleStatusResponse model validation."""

    def test_valid_subtitle_status_response(self):
        """Test valid SubtitleStatusResponse passes validation."""
        job_id = uuid4()
        response = SubtitleStatusResponse(
            id=job_id,
            status="download_in_progress",
            progress=50,
            message="Processing...",
        )

        assert response.id == job_id
        assert response.status == "download_in_progress"
        assert response.progress == 50
        assert response.message == "Processing..."

    def test_subtitle_status_response_default_values(self):
        """Test SubtitleStatusResponse default values."""
        job_id = uuid4()
        response = SubtitleStatusResponse(
            id=job_id,
            status="pending",
        )

        assert response.progress == 0
        assert response.message == ""

    def test_subtitle_status_response_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleStatusResponse()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "id" in error_fields
        assert "status" in error_fields

    def test_subtitle_status_response_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleStatusResponse(
                id="not-a-uuid",
                status="pending",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)

    @pytest.mark.parametrize(
        "progress",
        [0, 25, 50, 75, 100],
    )
    def test_subtitle_status_response_valid_progress_values(self, progress):
        """Test that valid progress values pass validation."""
        job_id = uuid4()
        response = SubtitleStatusResponse(
            id=job_id,
            status="pending",
            progress=progress,
        )

        assert response.progress == progress

    def test_subtitle_status_response_negative_progress_allowed(self):
        """Test that negative progress is allowed (no constraint in schema)."""
        job_id = uuid4()
        response = SubtitleStatusResponse(
            id=job_id,
            status="pending",
            progress=-1,
        )

        assert response.progress == -1


# ============================================================================
# QueueStatusResponse Validation Tests
# ============================================================================


class TestQueueStatusResponseValidation:
    """Test QueueStatusResponse model validation."""

    def test_valid_queue_status_response(self):
        """Test valid QueueStatusResponse passes validation."""
        response = QueueStatusResponse(
            download_queue_size=5,
            translation_queue_size=3,
            active_workers={"downloader": 2, "translator": 1},
        )

        assert response.download_queue_size == 5
        assert response.translation_queue_size == 3
        assert response.active_workers == {"downloader": 2, "translator": 1}

    def test_queue_status_response_with_empty_queues(self):
        """Test QueueStatusResponse with empty queues."""
        response = QueueStatusResponse(
            download_queue_size=0,
            translation_queue_size=0,
            active_workers={},
        )

        assert response.download_queue_size == 0
        assert response.translation_queue_size == 0
        assert response.active_workers == {}

    def test_queue_status_response_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            QueueStatusResponse()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "download_queue_size" in error_fields
        assert "translation_queue_size" in error_fields
        assert "active_workers" in error_fields

    def test_queue_status_response_invalid_queue_size_type(self):
        """Test that invalid queue_size type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            QueueStatusResponse(
                download_queue_size="not-an-int",
                translation_queue_size=0,
                active_workers={},
            )

        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("download_queue_size",) for error in errors
        )

    def test_queue_status_response_invalid_active_workers_type(self):
        """Test that invalid active_workers type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            QueueStatusResponse(
                download_queue_size=0,
                translation_queue_size=0,
                active_workers="not-a-dict",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("active_workers",) for error in errors)


# ============================================================================
# SubtitleTranslateRequest Validation Tests
# ============================================================================


class TestSubtitleTranslateRequestValidation:
    """Test SubtitleTranslateRequest model validation."""

    def test_valid_subtitle_translate_request(self):
        """Test valid SubtitleTranslateRequest passes validation."""
        request = SubtitleTranslateRequest(
            subtitle_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            video_title="Test Video",
        )

        assert request.subtitle_path == "/path/to/subtitle.srt"
        assert request.source_language == "en"
        assert request.target_language == "es"
        assert request.video_title == "Test Video"

    def test_subtitle_translate_request_without_video_title(self):
        """Test SubtitleTranslateRequest without optional video_title."""
        request = SubtitleTranslateRequest(
            subtitle_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        assert request.video_title is None

    def test_subtitle_translate_request_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleTranslateRequest()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "subtitle_path" in error_fields
        assert "source_language" in error_fields
        assert "target_language" in error_fields

    def test_subtitle_translate_request_allows_empty_subtitle_path(self):
        """Test empty subtitle_path allowed (no min_length)."""
        request = SubtitleTranslateRequest(
            subtitle_path="",
            source_language="en",
            target_language="es",
        )

        assert request.subtitle_path == ""


# ============================================================================
# JellyfinWebhookPayload Validation Tests
# ============================================================================


class TestJellyfinWebhookPayloadValidation:
    """Test JellyfinWebhookPayload model validation."""

    def test_valid_jellyfin_webhook_payload(self):
        """Test valid JellyfinWebhookPayload passes validation."""
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Sample Movie",
            item_path="/media/movies/sample.mp4",
            item_id="abc123",
            library_name="Movies",
            video_url="http://jellyfin.local/videos/abc123",
        )

        assert payload.event == "library.item.added"
        assert payload.item_type == "Movie"
        assert payload.item_name == "Sample Movie"
        assert payload.item_path == "/media/movies/sample.mp4"
        assert payload.item_id == "abc123"
        assert payload.library_name == "Movies"
        assert payload.video_url == "http://jellyfin.local/videos/abc123"

    def test_jellyfin_webhook_payload_with_minimal_fields(self):
        """Test JellyfinWebhookPayload with only required fields."""
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Sample Movie",
        )

        assert payload.event == "library.item.added"
        assert payload.item_type == "Movie"
        assert payload.item_name == "Sample Movie"
        assert payload.item_path is None
        assert payload.item_id is None
        assert payload.library_name is None
        assert payload.video_url is None

    def test_jellyfin_webhook_payload_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JellyfinWebhookPayload()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "event" in error_fields
        assert "item_type" in error_fields
        assert "item_name" in error_fields

    def test_jellyfin_webhook_payload_optional_fields(self):
        """Test that optional fields can be None."""
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Sample Movie",
            item_path=None,
            item_id=None,
            library_name=None,
            video_url=None,
        )

        assert payload.item_path is None
        assert payload.item_id is None
        assert payload.library_name is None
        assert payload.video_url is None


# ============================================================================
# SubtitleDownloadResponse Validation Tests
# ============================================================================


class TestSubtitleDownloadResponseValidation:
    """Test SubtitleDownloadResponse model validation."""

    def test_valid_subtitle_download_response(self):
        """Test valid SubtitleDownloadResponse passes validation."""
        job_id = uuid4()
        response = SubtitleDownloadResponse(
            job_id=job_id,
            filename="subtitle.srt",
            language="en",
            file_size=1024,
        )

        assert response.job_id == job_id
        assert response.filename == "subtitle.srt"
        assert response.language == "en"
        assert response.file_size == 1024

    def test_subtitle_download_response_without_file_size(self):
        """Test SubtitleDownloadResponse without optional file_size."""
        job_id = uuid4()
        response = SubtitleDownloadResponse(
            job_id=job_id,
            filename="subtitle.srt",
            language="en",
        )

        assert response.file_size is None

    def test_subtitle_download_response_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleDownloadResponse()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}
        assert "job_id" in error_fields
        assert "filename" in error_fields
        assert "language" in error_fields

    def test_subtitle_download_response_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SubtitleDownloadResponse(
                job_id="not-a-uuid",
                filename="subtitle.srt",
                language="en",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("job_id",) for error in errors)

    def test_subtitle_download_response_allows_empty_filename(self):
        """Test that empty filename is allowed (no min_length constraint)."""
        job_id = uuid4()
        response = SubtitleDownloadResponse(
            job_id=job_id,
            filename="",
            language="en",
        )

        assert response.filename == ""


# ============================================================================
# WebhookAcknowledgement Validation Tests
# ============================================================================


class TestWebhookAcknowledgementValidation:
    """Test WebhookAcknowledgement model validation."""

    def test_valid_webhook_acknowledgement(self):
        """Test valid WebhookAcknowledgement passes validation."""
        job_id = uuid4()
        acknowledgement = WebhookAcknowledgement(
            status="received",
            job_id=job_id,
            message="Webhook processed successfully",
        )

        assert acknowledgement.status == "received"
        assert acknowledgement.job_id == job_id
        assert acknowledgement.message == "Webhook processed successfully"

    def test_webhook_acknowledgement_default_values(self):
        """Test WebhookAcknowledgement default values."""
        acknowledgement = WebhookAcknowledgement()

        assert acknowledgement.status == "received"
        assert acknowledgement.job_id is None
        assert acknowledgement.message == ""

    def test_webhook_acknowledgement_with_different_statuses(self):
        """Test WebhookAcknowledgement with different status values."""
        job_id = uuid4()

        statuses = ["received", "duplicate", "ignored", "error"]
        for status in statuses:
            acknowledgement = WebhookAcknowledgement(
                status=status,
                job_id=job_id,
            )

            assert acknowledgement.status == status

    def test_webhook_acknowledgement_without_job_id(self):
        """Test WebhookAcknowledgement without job_id."""
        acknowledgement = WebhookAcknowledgement(
            status="ignored",
            message="Event type not processed",
        )

        assert acknowledgement.job_id is None
        assert acknowledgement.message == "Event type not processed"

    def test_webhook_acknowledgement_invalid_uuid(self):
        """Test that invalid UUID raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebhookAcknowledgement(
                status="received",
                job_id="not-a-uuid",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("job_id",) for error in errors)
