"""Tests for the manager API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from common.schemas import SubtitleResponse, SubtitleStatus
from manager.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    return SubtitleResponse(
        id=uuid4(),
        video_url="https://example.com/video.mp4",
        video_title="Test Video",
        language="en",
        target_language="es",
        status=SubtitleStatus.PENDING,
    )


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_success(self, client):
        """Test that health endpoint returns 200 when Redis is healthy."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.health_check = AsyncMock(
                return_value={"connected": True, "status": "healthy"}
            )

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    def test_health_check_redis_unavailable(self, client):
        """Test health endpoint when Redis is unavailable."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.health_check = AsyncMock(
                return_value={
                    "connected": False,
                    "status": "unhealthy",
                    "error": "Connection failed",
                }
            )

            response = client.get("/health")

            # Should still return 200 but log warning
            assert response.status_code == 200


class TestSubtitleEndpoints:
    """Test subtitle-related endpoints."""

    def test_get_subtitle_details(self, client, sample_job):
        """Test getting detailed subtitle job information."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_job.id)
            assert data["status"] == sample_job.status.value

    def test_get_subtitle_details_not_found(self, client):
        """Test getting details for non-existent job."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.get_job = AsyncMock(return_value=None)

            job_id = uuid4()
            response = client.get(f"/subtitles/{job_id}")

            assert response.status_code == 404

    def test_list_subtitle_requests(self, client, sample_job):
        """Test listing all subtitle requests."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.list_jobs = AsyncMock(return_value=[sample_job])

            response = client.get("/subtitles")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == str(sample_job.id)




class TestSubtitleDownloadRequest:
    """Test subtitle download request endpoint."""

    def test_request_download_success(self, client):
        """Test successful subtitle download request."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

            request_data = {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            }

            response = client.post("/subtitles/download", json=request_data)

            assert response.status_code == 201
            data = response.json()
            assert data["video_url"] == request_data["video_url"]
            assert data["status"] == "pending"
            assert "id" in data

    def test_request_download_enqueue_failure(self, client):
        """Test subtitle download request when enqueue fails."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=False)

            request_data = {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "preferred_sources": ["opensubtitles"],
            }

            response = client.post("/subtitles/download", json=request_data)

            assert response.status_code == 500


class TestQueueStatus:
    """Test queue status endpoint."""

    def test_get_queue_status(self, client):
        """Test getting queue status."""
        with patch("manager.main.orchestrator") as mock_orchestrator:
            mock_orchestrator.get_queue_status = AsyncMock(
                return_value={
                    "download_queue_size": 5,
                    "translation_queue_size": 2,
                    "active_workers": {"downloader": 2, "translator": 1},
                }
            )

            response = client.get("/queue/status")

            assert response.status_code == 200
            data = response.json()
            assert data["download_queue_size"] == 5
            assert data["translation_queue_size"] == 2


class TestSubtitleTranslateEndpoint:
    """Test subtitle translation endpoint."""

    def test_translate_request_success(self, client):
        """Test successful translation request."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_translation_task = AsyncMock(return_value=True)

            request_data = {
                "subtitle_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
                "video_title": "Test Video",
            }

            response = client.post("/subtitles/translate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "en"
            assert data["target_language"] == "es"
            assert data["status"] == "pending"
            assert "id" in data

            # Verify the orchestrator was called with the correct path
            mock_orchestrator.enqueue_translation_task.assert_called_once()
            call_args = mock_orchestrator.enqueue_translation_task.call_args
            assert call_args[0][1] == "/path/to/subtitle.srt"  # subtitle_file_path

    def test_translate_request_enqueue_failure(self, client):
        """Test translation request when enqueue fails."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_translation_task = AsyncMock(return_value=False)

            request_data = {
                "subtitle_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            }

            response = client.post("/subtitles/translate", json=request_data)

            assert response.status_code == 500

    def test_translate_request_validation(self, client):
        """Test translation request validation."""
        # Missing required fields
        request_data = {
            "subtitle_path": "/path/to/file.srt",
            # Missing source_language and target_language
        }

        response = client.post("/subtitles/translate", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_translate_request_without_video_title(self, client):
        """Test translation request without video title."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_translation_task = AsyncMock(return_value=True)

            request_data = {
                "subtitle_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
                # No video_title provided
            }

            response = client.post("/subtitles/translate", json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert data["video_title"] == "Translation Job"  # Default title


class TestSubtitleStatusEndpoint:
    """Test subtitle status endpoint."""

    def test_get_status_success(self, client, sample_job):
        """Test getting job status."""
        with patch("manager.main.redis_client") as mock_redis:
            sample_job.status = SubtitleStatus.DOWNLOADING
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/status/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_job.id)
            assert data["status"] == "downloading"
            assert "progress" in data
            assert data["progress"] == 25  # DOWNLOADING status progress

    def test_get_status_not_found(self, client):
        """Test getting status for non-existent job."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.get_job = AsyncMock(return_value=None)

            job_id = uuid4()
            response = client.get(f"/subtitles/status/{job_id}")

            assert response.status_code == 404

    def test_get_status_completed(self, client, sample_job):
        """Test getting status for completed job."""
        with patch("manager.main.redis_client") as mock_redis:
            sample_job.status = SubtitleStatus.COMPLETED
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/status/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["progress"] == 100


class TestJellyfinWebhookEndpoint:
    """Test Jellyfin webhook endpoint."""

    def test_webhook_library_item_added(self, client):
        """Test webhook for library item added event."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch("manager.main.settings") as mock_settings:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=True
            )
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = "es"
            mock_settings.jellyfin_auto_translate = True

            payload = {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Test Movie",
                "item_path": "/media/movies/test.mp4",
                "item_id": "abc123",
                "library_name": "Movies",
                "video_url": "http://jellyfin.local/videos/abc123",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"
            assert "job_id" in data

    def test_webhook_ignored_event_type(self, client):
        """Test webhook ignores unsupported event types."""
        payload = {
            "event": "library.item.deleted",
            "item_type": "Movie",
            "item_name": "Test Movie",
            "item_path": "/media/movies/test.mp4",
        }

        response = client.post("/webhooks/jellyfin", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_ignored_non_video(self, client):
        """Test webhook ignores non-video items."""
        payload = {
            "event": "library.item.added",
            "item_type": "Audio",
            "item_name": "Test Audio",
            "item_path": "/media/audio/test.mp3",
        }

        response = client.post("/webhooks/jellyfin", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_webhook_missing_video_url(self, client):
        """Test webhook with missing video URL."""
        payload = {
            "event": "library.item.added",
            "item_type": "Movie",
            "item_name": "Test Movie",
            # Missing both item_path and video_url
        }

        response = client.post("/webhooks/jellyfin", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"

    def test_webhook_enqueue_failure(self, client):
        """Test webhook when enqueue fails."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch("manager.main.settings") as mock_settings:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=False
            )
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = "es"
            mock_settings.jellyfin_auto_translate = True

            payload = {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Test Movie",
                "video_url": "http://test.com/video.mp4",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"

    def test_webhook_auto_translate_disabled(self, client):
        """Test webhook with auto-translate disabled."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch("manager.main.settings") as mock_settings:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = None
            mock_settings.jellyfin_auto_translate = False

            payload = {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Test Movie",
                "video_url": "http://test.com/video.mp4",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"
            # Should use enqueue_download_task, not enqueue_download_with_translation
            mock_orchestrator.enqueue_download_task.assert_called_once()
