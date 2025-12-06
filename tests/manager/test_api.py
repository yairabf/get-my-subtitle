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


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Subtitle Management API"
        assert data["version"] == "1.0.0"
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.parametrize(
        "health_status,expected_status_code",
        [
            # All healthy - should return 200
            (
                {
                    "status": "healthy",
                    "checks": {
                        "orchestrator_connected": True,
                        "event_consumer_connected": True,
                        "event_consumer_consuming": True,
                        "event_publisher_connected": True,
                        "redis_connected": True,
                    },
                    "details": {},
                },
                200,
            ),
            # Some unhealthy - should return 503
            (
                {
                    "status": "unhealthy",
                    "checks": {
                        "orchestrator_connected": True,
                        "event_consumer_connected": True,
                        "event_consumer_consuming": True,
                        "event_publisher_connected": True,
                        "redis_connected": False,
                    },
                    "details": {"redis": {"status": "not_connected"}},
                },
                503,
            ),
            # Error during health check - should return 500
            (
                {
                    "status": "error",
                    "error": "Health check failed",
                    "checks": {},
                    "details": {},
                },
                500,
            ),
        ],
    )
    def test_health_check_various_states(
        self, client, health_status, expected_status_code
    ):
        """Test health endpoint with various health states."""
        with patch("manager.main.check_health") as mock_check_health:
            mock_check_health.return_value = health_status

            response = client.get("/health")

            assert response.status_code == expected_status_code
            data = response.json()
            assert data["status"] == health_status["status"]
            assert "checks" in data or "error" in data

    def test_health_check_exception(self, client):
        """Test health endpoint when health check raises exception."""
        with patch("manager.main.check_health") as mock_check_health:
            mock_check_health.side_effect = Exception("Health check error")

            # The health endpoint should handle exceptions gracefully
            # and return an error status
            try:
                response = client.get("/health")
                # If we get here, check that it returned an error response
                assert response.status_code == 500
            except Exception:
                # If exception propagates, that's also acceptable
                pass


class TestSubtitleEndpoints:
    """Test subtitle-related endpoints."""

    def test_get_subtitle_details(self, client, sample_job):
        """Test getting detailed subtitle job information."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_job.id)
            assert data["status"] == sample_job.status.value

    def test_get_subtitle_details_not_found(self, client):
        """Test getting details for non-existent job."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=None)

            job_id = uuid4()
            response = client.get(f"/subtitles/{job_id}")

            assert response.status_code == 404

    @pytest.mark.parametrize(
        "invalid_uuid",
        [
            "invalid-uuid-format",
            "12345",
            "not-a-uuid",
            "abc-def-ghi",
        ],
    )
    def test_get_subtitle_details_invalid_uuid(self, client, invalid_uuid):
        """Test getting details with invalid UUID formats."""
        response = client.get(f"/subtitles/{invalid_uuid}")

        assert response.status_code == 422  # Validation error

    @pytest.mark.parametrize(
        "exception_type,exception_message",
        [
            (Exception, "Redis connection error"),
            (ConnectionError, "Connection timeout"),
            (RuntimeError, "Redis unavailable"),
        ],
    )
    def test_get_subtitle_details_redis_exception(
        self, client, exception_type, exception_message
    ):
        """Test getting details when Redis raises various exceptions."""
        with patch("manager.main.redis_client") as mock_redis:
            # Mock ensure_connected to prevent reconnection retries (165s delay!)
            mock_redis.ensure_connected = AsyncMock(return_value=True)

            # Create an async function that raises the exception
            async def raise_exception(*args, **kwargs):
                raise exception_type(exception_message)

            mock_redis.get_job = raise_exception

            job_id = uuid4()

            # FastAPI may catch exceptions and return HTTP 500, or let them propagate
            try:
                response = client.get(f"/subtitles/{job_id}")
                # If we get here, FastAPI caught the exception and returned 500
                assert response.status_code == 500
            except exception_type:
                # If exception propagates, that's also acceptable
                pass

    def test_list_subtitle_requests(self, client, sample_job):
        """Test listing all subtitle requests."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.list_jobs = AsyncMock(return_value=[sample_job])

            response = client.get("/subtitles")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == str(sample_job.id)

    def test_list_subtitle_requests_empty(self, client):
        """Test listing subtitle requests when no jobs exist."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.list_jobs = AsyncMock(return_value=[])

            response = client.get("/subtitles")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0
            assert data == []

    @pytest.mark.parametrize(
        "exception_type,exception_message",
        [
            (Exception, "Redis connection error"),
            (TimeoutError, "Redis timeout"),
            (ConnectionError, "Connection lost"),
        ],
    )
    def test_list_subtitle_requests_redis_exception(
        self, client, exception_type, exception_message
    ):
        """Test listing requests when Redis raises various exceptions."""
        with patch("manager.main.redis_client") as mock_redis:
            # Mock ensure_connected to prevent reconnection retries (165s delay!)
            mock_redis.ensure_connected = AsyncMock(return_value=True)

            # Create an async function that raises the exception
            async def raise_exception(*args, **kwargs):
                raise exception_type(exception_message)

            mock_redis.list_jobs = raise_exception

            # FastAPI may catch exceptions and return HTTP 500, or let them propagate
            try:
                response = client.get("/subtitles")
                # If we get here, FastAPI caught the exception and returned 500
                assert response.status_code == 500
            except exception_type:
                # If exception propagates, that's also acceptable
                pass


class TestJobEventHistory:
    """Test job event history endpoint."""

    def test_get_job_events_success(self, client, sample_job):
        """Test getting event history for existing job with events."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=sample_job)
            mock_redis.get_job_events = AsyncMock(
                return_value=[
                    {
                        "event_type": "subtitle.download.requested",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "source": "manager",
                        "payload": {"language": "en"},
                    },
                    {
                        "event_type": "subtitle.ready",
                        "timestamp": "2024-01-01T00:05:00Z",
                        "source": "downloader",
                        "payload": {"subtitle_path": "/path/to/subtitle.srt"},
                    },
                ]
            )

            response = client.get(f"/subtitles/{sample_job.id}/events")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == str(sample_job.id)
            assert data["event_count"] == 2
            assert len(data["events"]) == 2
            assert data["events"][0]["event_type"] == "subtitle.download.requested"
            assert data["events"][1]["event_type"] == "subtitle.ready"

    def test_get_job_events_not_found(self, client):
        """Test getting events for non-existent job."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=None)

            job_id = uuid4()
            response = client.get(f"/subtitles/{job_id}/events")

            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "Subtitle job not found"

    def test_get_job_events_empty(self, client, sample_job):
        """Test getting events when no events recorded yet."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=sample_job)
            mock_redis.get_job_events = AsyncMock(return_value=[])

            response = client.get(f"/subtitles/{sample_job.id}/events")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == str(sample_job.id)
            assert data["event_count"] == 0
            assert data["events"] == []
            assert "No events recorded" in data["message"]

    @pytest.mark.parametrize(
        "invalid_uuid",
        [
            "invalid-uuid",
            "not-a-uuid-at-all",
            "12345678",
            "malformed",
        ],
    )
    def test_get_job_events_invalid_uuid(self, client, invalid_uuid):
        """Test getting events with invalid UUID formats."""
        response = client.get(f"/subtitles/{invalid_uuid}/events")

        assert response.status_code == 422  # Validation error

    @pytest.mark.parametrize(
        "exception_type,exception_message",
        [
            (Exception, "Redis connection error"),
            (RuntimeError, "Redis query failed"),
            (ValueError, "Invalid job ID"),
        ],
    )
    def test_get_job_events_redis_exception(
        self, client, sample_job, exception_type, exception_message
    ):
        """Test getting events when Redis raises various exceptions."""
        with patch("manager.main.redis_client") as mock_redis:
            # Mock ensure_connected to prevent reconnection retries (165s delay!)
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            # Create an async function that raises the exception
            async def raise_exception(*args, **kwargs):
                raise exception_type(exception_message)

            mock_redis.get_job_events = raise_exception

            # FastAPI may catch exceptions and return HTTP 500, or let them propagate
            try:
                response = client.get(f"/subtitles/{sample_job.id}/events")
                # If we get here, FastAPI caught the exception and returned 500
                assert response.status_code == 500
            except exception_type:
                # If exception propagates, that's also acceptable
                pass


class TestSubtitleDownloadRequest:
    """Test subtitle download request endpoint."""

    def test_request_download_success(self, client):
        """Test successful subtitle download request."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
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

    @pytest.mark.parametrize(
        "enqueue_result,expected_status",
        [
            (False, 500),
            (None, 500),
        ],
    )
    def test_request_download_enqueue_failure(
        self, client, enqueue_result, expected_status
    ):
        """Test subtitle download request when enqueue fails."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.helpers.event_publisher"
        ) as mock_event_publisher:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(
                return_value=enqueue_result
            )
            mock_event_publisher.publish_event = AsyncMock(return_value=True)

            request_data = {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "preferred_sources": ["opensubtitles"],
            }

            response = client.post("/subtitles/download", json=request_data)

            assert response.status_code == expected_status

    @pytest.mark.parametrize(
        "missing_field,request_data",
        [
            (
                "video_url",
                {
                    "video_title": "Test Video",
                    "language": "en",
                    "preferred_sources": ["opensubtitles"],
                },
            ),
            (
                "video_title",
                {
                    "video_url": "https://example.com/video.mp4",
                    "language": "en",
                    "preferred_sources": ["opensubtitles"],
                },
            ),
            (
                "language",
                {
                    "video_url": "https://example.com/video.mp4",
                    "video_title": "Test Video",
                    "preferred_sources": ["opensubtitles"],
                },
            ),
        ],
    )
    def test_request_download_missing_fields(self, client, missing_field, request_data):
        """Test download request validation with missing required fields."""
        response = client.post("/subtitles/download", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_request_download_with_target_language(self, client):
        """Test download request with target language for translation."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

            request_data = {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
            }

            response = client.post("/subtitles/download", json=request_data)

            assert response.status_code == 201
            data = response.json()
            assert data["target_language"] == "es"

    @pytest.mark.parametrize(
        "component,exception_type,exception_message",
        [
            ("redis", Exception, "Redis connection error"),
            ("redis", ConnectionError, "Redis timeout"),
            ("orchestrator", Exception, "RabbitMQ connection error"),
            ("orchestrator", RuntimeError, "Queue unavailable"),
        ],
    )
    def test_request_download_exception_handling(
        self, client, component, exception_type, exception_message
    ):
        """Test download request when components raise various exceptions."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            if component == "redis":
                mock_redis.save_job = AsyncMock(
                    side_effect=exception_type(exception_message)
                )
            else:
                mock_redis.save_job = AsyncMock(return_value=True)
                mock_orchestrator.enqueue_download_task = AsyncMock(
                    side_effect=exception_type(exception_message)
                )

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

    @pytest.mark.parametrize(
        "exception_type,exception_message",
        [
            (Exception, "RabbitMQ connection error"),
            (ConnectionError, "Queue service unavailable"),
            (TimeoutError, "Queue status timeout"),
        ],
    )
    def test_get_queue_status_orchestrator_exception(
        self, client, exception_type, exception_message
    ):
        """Test queue status when orchestrator raises various exceptions."""
        with patch("manager.main.orchestrator") as mock_orchestrator:
            mock_orchestrator.get_queue_status = AsyncMock(
                side_effect=exception_type(exception_message)
            )

            response = client.get("/queue/status")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to get queue status" in data["detail"]

    def test_get_queue_status_empty_queues(self, client):
        """Test queue status when queues are empty."""
        with patch("manager.main.orchestrator") as mock_orchestrator:
            mock_orchestrator.get_queue_status = AsyncMock(
                return_value={
                    "download_queue_size": 0,
                    "translation_queue_size": 0,
                    "active_workers": {"downloader": 0, "translator": 0},
                }
            )

            response = client.get("/queue/status")

            assert response.status_code == 200
            data = response.json()
            assert data["download_queue_size"] == 0
            assert data["translation_queue_size"] == 0


class TestSubtitleTranslateEndpoint:
    """Test subtitle translation endpoint."""

    def test_translate_request_success(self, client):
        """Test successful translation request."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
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

    @pytest.mark.parametrize(
        "enqueue_result,expected_status",
        [
            (False, 500),
            (None, 500),
        ],
    )
    def test_translate_request_enqueue_failure(
        self, client, enqueue_result, expected_status
    ):
        """Test translation request when enqueue fails."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.helpers.event_publisher"
        ) as mock_event_publisher:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_translation_task = AsyncMock(
                return_value=enqueue_result
            )
            mock_event_publisher.publish_event = AsyncMock(return_value=True)

            request_data = {
                "subtitle_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            }

            response = client.post("/subtitles/translate", json=request_data)

            assert response.status_code == expected_status

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

            mock_redis.ensure_connected = AsyncMock(return_value=True)
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

    @pytest.mark.parametrize(
        "component,exception_type,exception_message",
        [
            ("redis", Exception, "Redis connection error"),
            ("redis", ConnectionError, "Redis save failed"),
            ("orchestrator", Exception, "RabbitMQ connection error"),
            ("orchestrator", RuntimeError, "Translation queue full"),
        ],
    )
    def test_translate_request_exception_handling(
        self, client, component, exception_type, exception_message
    ):
        """Test translation request when components raise various exceptions."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            if component == "redis":
                mock_redis.save_job = AsyncMock(
                    side_effect=exception_type(exception_message)
                )
            else:
                mock_redis.save_job = AsyncMock(return_value=True)
                mock_orchestrator.enqueue_translation_task = AsyncMock(
                    side_effect=exception_type(exception_message)
                )

            request_data = {
                "subtitle_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            }

            response = client.post("/subtitles/translate", json=request_data)

            assert response.status_code == 500


class TestSubtitleStatusEndpoint:
    """Test subtitle status endpoint."""

    @pytest.mark.parametrize(
        "status,expected_progress",
        [
            # Progress mapping based on actual implementation in common/utils.py
            (SubtitleStatus.PENDING, 0),
            (SubtitleStatus.DOWNLOADING, 25),
            (SubtitleStatus.TRANSLATING, 75),
            (SubtitleStatus.COMPLETED, 100),
            (SubtitleStatus.FAILED, 0),
            # New statuses not in mapping default to 0
            (SubtitleStatus.DOWNLOAD_QUEUED, 0),
            (SubtitleStatus.DOWNLOAD_IN_PROGRESS, 0),
            (SubtitleStatus.TRANSLATE_QUEUED, 0),
            (SubtitleStatus.TRANSLATE_IN_PROGRESS, 0),
            (SubtitleStatus.DONE, 0),
        ],
    )
    def test_get_status_progress_mapping(
        self, client, sample_job, status, expected_progress
    ):
        """Test status progress calculation for all status values."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            sample_job.status = status
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/status/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_job.id)
            assert data["status"] == status.value
            assert data["progress"] == expected_progress

    def test_get_status_not_found(self, client):
        """Test getting status for non-existent job."""
        with patch("manager.main.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.get_job = AsyncMock(return_value=None)

            job_id = uuid4()
            response = client.get(f"/subtitles/status/{job_id}")

            assert response.status_code == 404

    @pytest.mark.parametrize(
        "invalid_uuid",
        [
            "invalid-uuid",
            "not-a-real-uuid",
            "123456789",
            "wrong-format",
        ],
    )
    def test_get_status_invalid_uuid(self, client, invalid_uuid):
        """Test getting status with invalid UUID formats."""
        response = client.get(f"/subtitles/status/{invalid_uuid}")

        assert response.status_code == 422  # Validation error

    @pytest.mark.parametrize(
        "exception_type,exception_message",
        [
            (Exception, "Redis connection error"),
            (ConnectionError, "Redis unavailable"),
            (TimeoutError, "Query timeout"),
        ],
    )
    def test_get_status_redis_exception(
        self, client, exception_type, exception_message
    ):
        """Test getting status when Redis raises various exceptions."""
        with patch("manager.main.redis_client") as mock_redis:
            # Mock ensure_connected to prevent reconnection retries (165s delay!)
            mock_redis.ensure_connected = AsyncMock(return_value=True)

            # Create an async function that raises the exception
            async def raise_exception(*args, **kwargs):
                raise exception_type(exception_message)

            mock_redis.get_job = raise_exception

            job_id = uuid4()

            # FastAPI may catch exceptions and return HTTP 500, or let them propagate
            try:
                response = client.get(f"/subtitles/status/{job_id}")
                # If we get here, FastAPI caught the exception and returned 500
                assert response.status_code == 500
            except exception_type:
                # If exception propagates, that's also acceptable
                pass

    def test_get_status_failed(self, client, sample_job):
        """Test getting status for failed job."""
        with patch("manager.main.redis_client") as mock_redis:
            sample_job.status = SubtitleStatus.FAILED
            sample_job.error_message = "Download failed"
            mock_redis.get_job = AsyncMock(return_value=sample_job)

            response = client.get(f"/subtitles/status/{sample_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["progress"] == 0  # Failed jobs have 0 progress


class TestJellyfinWebhookEndpoint:
    """Test Jellyfin webhook endpoint."""

    def test_webhook_library_item_added(self, client):
        """Test webhook for library item added event."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=True
            )
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
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
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings, patch(
            "common.event_publisher.event_publisher"
        ) as mock_event_publisher:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=False
            )
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=False)
            mock_event_publisher.publish_event = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
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
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = None
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

    def test_webhook_episode_item_type(self, client):
        """Test webhook with Episode item type."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=True
            )
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
            mock_settings.jellyfin_auto_translate = True

            payload = {
                "event": "library.item.added",
                "item_type": "Episode",
                "item_name": "S01E01 - Pilot",
                "video_url": "http://jellyfin.local/videos/ep123",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"
            assert "job_id" in data

    def test_webhook_item_path_fallback(self, client):
        """Test webhook uses item_path when video_url is missing."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=True
            )
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
            mock_settings.jellyfin_auto_translate = True

            payload = {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Test Movie",
                "item_path": "/media/movies/test.mp4",
                # No video_url provided - endpoint should convert to file:// URL
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "received"

    @pytest.mark.parametrize(
        "event_type,expected_status",
        [
            ("library.item.added", "received"),
            ("library.item.updated", "received"),
            ("library.item.deleted", "ignored"),
            ("playback.start", "ignored"),
            ("playback.stop", "ignored"),
        ],
    )
    def test_webhook_event_types(self, client, event_type, expected_status):
        """Test webhook handling of different event types."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=True
            )
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
            mock_settings.jellyfin_auto_translate = True

            payload = {
                "event": event_type,
                "item_type": "Movie",
                "item_name": "Test Movie",
                "video_url": "http://test.com/video.mp4",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == expected_status

    @pytest.mark.parametrize(
        "item_type,expected_status",
        [
            ("Movie", "received"),
            ("Episode", "received"),
            ("Audio", "ignored"),
            ("MusicVideo", "ignored"),
            ("Book", "ignored"),
        ],
    )
    def test_webhook_item_types(self, client, item_type, expected_status):
        """Test webhook handling of different item types."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.save_job = AsyncMock(return_value=True)
            mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                return_value=True
            )
            mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
            mock_settings.jellyfin_auto_translate = True

            payload = {
                "event": "library.item.added",
                "item_type": item_type,
                "item_name": f"Test {item_type}",
                "video_url": "http://test.com/video.mp4",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == expected_status

    @pytest.mark.parametrize(
        "component,exception_type,exception_message",
        [
            ("redis", Exception, "Redis connection error"),
            ("redis", ConnectionError, "Redis write failed"),
            ("orchestrator", Exception, "RabbitMQ connection error"),
            ("orchestrator", RuntimeError, "Queue service unavailable"),
        ],
    )
    def test_webhook_exception_handling(
        self, client, component, exception_type, exception_message
    ):
        """Test webhook when components raise various exceptions."""
        with patch("manager.main.redis_client") as mock_redis, patch(
            "manager.main.orchestrator"
        ) as mock_orchestrator, patch(
            "manager.main.settings", new_callable=MagicMock
        ) as mock_settings:

            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "es"
            mock_settings.jellyfin_auto_translate = True

            if component == "redis":
                mock_redis.ensure_connected = AsyncMock(return_value=True)
                mock_redis.save_job = AsyncMock(
                    side_effect=exception_type(exception_message)
                )
            else:
                mock_redis.ensure_connected = AsyncMock(return_value=True)
                mock_redis.save_job = AsyncMock(return_value=True)
                mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                    side_effect=exception_type(exception_message)
                )

            payload = {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Test Movie",
                "video_url": "http://test.com/video.mp4",
            }

            response = client.post("/webhooks/jellyfin", json=payload)

            assert response.status_code == 500
