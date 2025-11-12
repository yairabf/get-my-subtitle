"""Serialization/deserialization tests for manager-specific schema models."""

import json
from uuid import uuid4

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
# SubtitleRequestCreate Serialization Tests
# ============================================================================


class TestSubtitleRequestCreateSerialization:
    """Test SubtitleRequestCreate serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        request = SubtitleRequestCreate(
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
        request = SubtitleRequestCreate(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
        )

        json_str = request.model_dump_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["video_url"] == "https://example.com/video.mp4"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        data = {
            "video_url": "https://example.com/video.mp4",
            "video_title": "Test Video",
            "language": "en",
        }

        request = SubtitleRequestCreate.model_validate(data)

        assert request.video_url == data["video_url"]
        assert request.video_title == data["video_title"]
        assert request.language == data["language"]

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = SubtitleRequestCreate(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
        )

        dumped = original.model_dump()
        restored = SubtitleRequestCreate.model_validate(dumped)

        assert restored.video_url == original.video_url
        assert restored.video_title == original.video_title
        assert restored.language == original.language
        assert restored.target_language == original.target_language


# ============================================================================
# SubtitleRequestUpdate Serialization Tests
# ============================================================================


class TestSubtitleRequestUpdateSerialization:
    """Test SubtitleRequestUpdate serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        update = SubtitleRequestUpdate(
            status="done",
            error_message="No errors",
            download_url="https://example.com/subtitles/123.srt",
        )

        dumped = update.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["status"] == "done"
        assert dumped["error_message"] == "No errors"
        assert (
            dumped["download_url"]
            == "https://example.com/subtitles/123.srt"
        )

    def test_model_dump_json_returns_string(self):
        """Test model_dump_json() returns valid JSON string."""
        update = SubtitleRequestUpdate(status="done")

        json_str = update.model_dump_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["status"] == "done"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        data = {
            "status": "failed",
            "error_message": "Error occurred",
        }

        update = SubtitleRequestUpdate.model_validate(data)

        assert update.status == "failed"
        assert update.error_message == "Error occurred"
        assert update.download_url is None

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = SubtitleRequestUpdate(
            status="done",
            error_message="Success",
            download_url="https://example.com/subtitles/123.srt",
        )

        dumped = original.model_dump()
        restored = SubtitleRequestUpdate.model_validate(dumped)

        assert restored.status == original.status
        assert restored.error_message == original.error_message
        assert restored.download_url == original.download_url


# ============================================================================
# SubtitleStatusResponse Serialization Tests
# ============================================================================


class TestSubtitleStatusResponseSerialization:
    """Test SubtitleStatusResponse serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        job_id = uuid4()
        response = SubtitleStatusResponse(
            id=job_id,
            status="download_in_progress",
            progress=50,
            message="Processing...",
        )

        dumped = response.model_dump()

        assert isinstance(dumped, dict)
        assert str(dumped["id"]) == str(job_id)
        assert dumped["status"] == "download_in_progress"
        assert dumped["progress"] == 50
        assert dumped["message"] == "Processing..."

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        job_id = uuid4()
        response = SubtitleStatusResponse(
            id=job_id,
            status="pending",
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["id"] == str(job_id)
        assert isinstance(parsed["id"], str)

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        job_id = uuid4()
        data = {
            "id": str(job_id),
            "status": "done",
            "progress": 100,
            "message": "Completed",
        }

        response = SubtitleStatusResponse.model_validate(data)

        assert response.id == job_id
        assert response.status == "done"
        assert response.progress == 100
        assert response.message == "Completed"

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        job_id = uuid4()
        json_str = json.dumps(
            {
                "id": str(job_id),
                "status": "pending",
                "progress": 0,
                "message": "",
            }
        )

        response = SubtitleStatusResponse.model_validate_json(json_str)

        assert response.id == job_id
        assert response.status == "pending"
        assert response.progress == 0

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        job_id = uuid4()
        original = SubtitleStatusResponse(
            id=job_id,
            status="download_in_progress",
            progress=75,
            message="Processing subtitle...",
        )

        dumped = original.model_dump()
        restored = SubtitleStatusResponse.model_validate(dumped)

        assert restored.id == original.id
        assert restored.status == original.status
        assert restored.progress == original.progress
        assert restored.message == original.message


# ============================================================================
# QueueStatusResponse Serialization Tests
# ============================================================================


class TestQueueStatusResponseSerialization:
    """Test QueueStatusResponse serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        response = QueueStatusResponse(
            download_queue_size=5,
            translation_queue_size=3,
            active_workers={"downloader": 2, "translator": 1},
        )

        dumped = response.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["download_queue_size"] == 5
        assert dumped["translation_queue_size"] == 3
        assert dumped["active_workers"] == {"downloader": 2, "translator": 1}

    def test_model_dump_json_returns_string(self):
        """Test model_dump_json() returns valid JSON string."""
        response = QueueStatusResponse(
            download_queue_size=0,
            translation_queue_size=0,
            active_workers={},
        )

        json_str = response.model_dump_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["download_queue_size"] == 0
        assert parsed["translation_queue_size"] == 0
        assert parsed["active_workers"] == {}

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        data = {
            "download_queue_size": 10,
            "translation_queue_size": 5,
            "active_workers": {"downloader": 3, "translator": 2},
        }

        response = QueueStatusResponse.model_validate(data)

        assert response.download_queue_size == 10
        assert response.translation_queue_size == 5
        assert response.active_workers == {"downloader": 3, "translator": 2}

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        json_str = json.dumps(
            {
                "download_queue_size": 2,
                "translation_queue_size": 1,
                "active_workers": {"downloader": 1},
            }
        )

        response = QueueStatusResponse.model_validate_json(json_str)

        assert response.download_queue_size == 2
        assert response.translation_queue_size == 1
        assert response.active_workers == {"downloader": 1}

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = QueueStatusResponse(
            download_queue_size=5,
            translation_queue_size=3,
            active_workers={"downloader": 2, "translator": 1},
        )

        dumped = original.model_dump()
        restored = QueueStatusResponse.model_validate(dumped)

        assert restored.download_queue_size == original.download_queue_size
        assert (
            restored.translation_queue_size
            == original.translation_queue_size
        )
        assert (
            restored.active_workers == original.active_workers
        )


# ============================================================================
# SubtitleTranslateRequest Serialization Tests
# ============================================================================


class TestSubtitleTranslateRequestSerialization:
    """Test SubtitleTranslateRequest serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        request = SubtitleTranslateRequest(
            subtitle_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            video_title="Test Video",
        )

        dumped = request.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["subtitle_path"] == "/path/to/subtitle.srt"
        assert dumped["source_language"] == "en"
        assert dumped["target_language"] == "es"
        assert dumped["video_title"] == "Test Video"

    def test_model_dump_json_returns_string(self):
        """Test model_dump_json() returns valid JSON string."""
        request = SubtitleTranslateRequest(
            subtitle_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
        )

        json_str = request.model_dump_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["subtitle_path"] == "/path/to/subtitle.srt"
        assert parsed["source_language"] == "en"
        assert parsed["target_language"] == "es"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        data = {
            "subtitle_path": "/path/to/subtitle.srt",
            "source_language": "en",
            "target_language": "es",
            "video_title": "Test Video",
        }

        request = SubtitleTranslateRequest.model_validate(data)

        assert request.subtitle_path == data["subtitle_path"]
        assert request.source_language == data["source_language"]
        assert request.target_language == data["target_language"]
        assert request.video_title == data["video_title"]

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = SubtitleTranslateRequest(
            subtitle_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            video_title="Test Video",
        )

        dumped = original.model_dump()
        restored = SubtitleTranslateRequest.model_validate(dumped)

        assert restored.subtitle_path == original.subtitle_path
        assert restored.source_language == original.source_language
        assert restored.target_language == original.target_language
        assert restored.video_title == original.video_title


# ============================================================================
# JellyfinWebhookPayload Serialization Tests
# ============================================================================


class TestJellyfinWebhookPayloadSerialization:
    """Test JellyfinWebhookPayload serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Sample Movie",
            item_path="/media/movies/sample.mp4",
            item_id="abc123",
            library_name="Movies",
            video_url="http://jellyfin.local/videos/abc123",
        )

        dumped = payload.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["event"] == "library.item.added"
        assert dumped["item_type"] == "Movie"
        assert dumped["item_name"] == "Sample Movie"
        assert dumped["item_path"] == "/media/movies/sample.mp4"
        assert dumped["item_id"] == "abc123"
        assert dumped["library_name"] == "Movies"
        assert dumped["video_url"] == "http://jellyfin.local/videos/abc123"

    def test_model_dump_json_returns_string(self):
        """Test model_dump_json() returns valid JSON string."""
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Sample Movie",
        )

        json_str = payload.model_dump_json()
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["event"] == "library.item.added"
        assert parsed["item_type"] == "Movie"
        assert parsed["item_name"] == "Sample Movie"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        data = {
            "event": "library.item.added",
            "item_type": "Episode",
            "item_name": "Sample Episode",
            "item_path": None,
            "item_id": None,
            "library_name": None,
            "video_url": None,
        }

        payload = JellyfinWebhookPayload.model_validate(data)

        assert payload.event == data["event"]
        assert payload.item_type == data["item_type"]
        assert payload.item_name == data["item_name"]
        assert payload.item_path is None
        assert payload.item_id is None

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        json_str = json.dumps(
            {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Sample Movie",
                "item_path": "/media/movies/sample.mp4",
                "item_id": "abc123",
                "library_name": "Movies",
                "video_url": "http://jellyfin.local/videos/abc123",
            }
        )

        payload = JellyfinWebhookPayload.model_validate_json(json_str)

        assert payload.event == "library.item.added"
        assert payload.item_type == "Movie"
        assert payload.item_name == "Sample Movie"
        assert payload.item_path == "/media/movies/sample.mp4"

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        original = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Sample Movie",
            item_path="/media/movies/sample.mp4",
            item_id="abc123",
            library_name="Movies",
            video_url="http://jellyfin.local/videos/abc123",
        )

        dumped = original.model_dump()
        restored = JellyfinWebhookPayload.model_validate(dumped)

        assert restored.event == original.event
        assert restored.item_type == original.item_type
        assert restored.item_name == original.item_name
        assert restored.item_path == original.item_path
        assert restored.item_id == original.item_id
        assert restored.library_name == original.library_name
        assert restored.video_url == original.video_url


# ============================================================================
# SubtitleDownloadResponse Serialization Tests
# ============================================================================


class TestSubtitleDownloadResponseSerialization:
    """Test SubtitleDownloadResponse serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        job_id = uuid4()
        response = SubtitleDownloadResponse(
            job_id=job_id,
            filename="subtitle.srt",
            language="en",
            file_size=1024,
        )

        dumped = response.model_dump()

        assert isinstance(dumped, dict)
        assert str(dumped["job_id"]) == str(job_id)
        assert dumped["filename"] == "subtitle.srt"
        assert dumped["language"] == "en"
        assert dumped["file_size"] == 1024

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        job_id = uuid4()
        response = SubtitleDownloadResponse(
            job_id=job_id,
            filename="subtitle.srt",
            language="en",
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["job_id"] == str(job_id)
        assert isinstance(parsed["job_id"], str)

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        job_id = uuid4()
        data = {
            "job_id": str(job_id),
            "filename": "subtitle.srt",
            "language": "en",
            "file_size": 2048,
        }

        response = SubtitleDownloadResponse.model_validate(data)

        assert response.job_id == job_id
        assert response.filename == data["filename"]
        assert response.language == data["language"]
        assert response.file_size == data["file_size"]

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        job_id = uuid4()
        json_str = json.dumps(
            {
                "job_id": str(job_id),
                "filename": "subtitle.srt",
                "language": "en",
                "file_size": None,
            }
        )

        response = SubtitleDownloadResponse.model_validate_json(json_str)

        assert response.job_id == job_id
        assert response.filename == "subtitle.srt"
        assert response.language == "en"
        assert response.file_size is None

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        job_id = uuid4()
        original = SubtitleDownloadResponse(
            job_id=job_id,
            filename="subtitle.srt",
            language="en",
            file_size=1024,
        )

        dumped = original.model_dump()
        restored = SubtitleDownloadResponse.model_validate(dumped)

        assert restored.job_id == original.job_id
        assert restored.filename == original.filename
        assert restored.language == original.language
        assert restored.file_size == original.file_size


# ============================================================================
# WebhookAcknowledgement Serialization Tests
# ============================================================================


class TestWebhookAcknowledgementSerialization:
    """Test WebhookAcknowledgement serialization/deserialization."""

    def test_model_dump_returns_dict(self):
        """Test model_dump() returns correct dict structure."""
        job_id = uuid4()
        acknowledgement = WebhookAcknowledgement(
            status="received",
            job_id=job_id,
            message="Webhook processed successfully",
        )

        dumped = acknowledgement.model_dump()

        assert isinstance(dumped, dict)
        assert dumped["status"] == "received"
        assert str(dumped["job_id"]) == str(job_id)
        assert dumped["message"] == "Webhook processed successfully"

    def test_model_dump_json_serializes_uuid_to_string(self):
        """Test model_dump_json() serializes UUID to string."""
        job_id = uuid4()
        acknowledgement = WebhookAcknowledgement(
            status="received",
            job_id=job_id,
        )

        json_str = acknowledgement.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "received"
        assert parsed["job_id"] == str(job_id)
        assert isinstance(parsed["job_id"], str)

    def test_model_dump_json_with_none_job_id(self):
        """Test model_dump_json() handles None job_id."""
        acknowledgement = WebhookAcknowledgement(
            status="ignored",
            message="Event type not processed",
        )

        json_str = acknowledgement.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "ignored"
        assert parsed["job_id"] is None
        assert parsed["message"] == "Event type not processed"

    def test_model_validate_from_dict(self):
        """Test model_validate() creates instance from dict."""
        job_id = uuid4()
        data = {
            "status": "duplicate",
            "job_id": str(job_id),
            "message": "Request already being processed",
        }

        acknowledgement = WebhookAcknowledgement.model_validate(data)

        assert acknowledgement.status == "duplicate"
        assert acknowledgement.job_id == job_id
        assert acknowledgement.message == "Request already being processed"

    def test_model_validate_json_from_string(self):
        """Test model_validate_json() creates instance from JSON string."""
        job_id = uuid4()
        json_str = json.dumps(
            {
                "status": "received",
                "job_id": str(job_id),
                "message": "Webhook processed successfully",
            }
        )

        acknowledgement = WebhookAcknowledgement.model_validate_json(json_str)

        assert acknowledgement.status == "received"
        assert acknowledgement.job_id == job_id
        assert acknowledgement.message == "Webhook processed successfully"

    def test_round_trip_serialization(self):
        """Test serialize → deserialize maintains data integrity."""
        job_id = uuid4()
        original = WebhookAcknowledgement(
            status="received",
            job_id=job_id,
            message="Webhook processed successfully",
        )

        dumped = original.model_dump()
        restored = WebhookAcknowledgement.model_validate(dumped)

        assert restored.status == original.status
        assert restored.job_id == original.job_id
        assert restored.message == original.message

    def test_round_trip_serialization_with_none_job_id(self):
        """Test round-trip serialization with None job_id."""
        original = WebhookAcknowledgement(
            status="ignored",
            message="Event type not processed",
        )

        dumped = original.model_dump()
        restored = WebhookAcknowledgement.model_validate(dumped)

        assert restored.status == original.status
        assert restored.job_id is None
        assert restored.message == original.message
