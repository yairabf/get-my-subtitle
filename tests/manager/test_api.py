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

    def test_request_subtitle_processing(self, client):
        """Test requesting subtitle processing."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

            request_data = {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
            }

            response = client.post("/subtitles/request", json=request_data)

            assert response.status_code == 201
            data = response.json()
            assert data["video_url"] == request_data["video_url"]
            assert data["status"] == "pending"
            assert "id" in data

    def test_request_subtitle_processing_enqueue_failure(self, client):
        """Test requesting subtitle processing when enqueue fails."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=False)

            request_data = {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
            }

            response = client.post("/subtitles/request", json=request_data)

            assert response.status_code == 500

    def test_get_subtitle_status(self, client, sample_job):
        """Test getting subtitle status."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_job.id)
            assert data["status"] == sample_job.status.value

    def test_get_subtitle_status_not_found(self, client):
        """Test getting status for non-existent job."""
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

    def test_get_subtitle_status_simple(self, client, sample_job):
        """Test getting simplified subtitle status."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/{sample_job.id}/status")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_job.id)
            assert data["status"] == sample_job.status.value
            assert "progress" in data
            assert "message" in data

    def test_download_subtitles_completed(self, client, sample_job):
        """Test downloading completed subtitles."""
        with patch("manager.main.redis_client") as mock_redis:
            sample_job.status = SubtitleStatus.COMPLETED
            sample_job.download_url = "https://example.com/subtitle.srt"
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.post(f"/subtitles/{sample_job.id}/download")

            assert response.status_code == 200
            data = response.json()
            assert "download_url" in data
            assert data["download_url"] == sample_job.download_url

    def test_download_subtitles_not_ready(self, client, sample_job):
        """Test downloading subtitles that are not ready."""
        with patch("manager.main.redis_client") as mock_redis:
            sample_job.status = SubtitleStatus.DOWNLOADING
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.post(f"/subtitles/{sample_job.id}/download")

            assert response.status_code == 400

    def test_download_subtitles_no_url(self, client, sample_job):
        """Test downloading when download URL is missing."""
        with patch("manager.main.redis_client") as mock_redis:
            sample_job.status = SubtitleStatus.COMPLETED
            sample_job.download_url = None
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.post(f"/subtitles/{sample_job.id}/download")

            assert response.status_code == 400


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
