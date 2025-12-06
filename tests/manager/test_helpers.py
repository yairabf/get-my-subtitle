"""Tests for Manager helper functions."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from common.schemas import EventType, SubtitleResponse, SubtitleStatus
from manager.helpers import (
    calculate_job_progress_percentage,
    publish_job_failure_and_raise_http_error,
)


@pytest.mark.unit
class TestCalculateJobProgressPercentage:
    """Test calculate_job_progress_percentage helper function."""

    @pytest.mark.parametrize(
        "subtitle_status,expected_progress",
        [
            (SubtitleStatus.PENDING, 0),
            (SubtitleStatus.DOWNLOADING, 25),
            (SubtitleStatus.TRANSLATING, 75),
            (SubtitleStatus.COMPLETED, 100),
            (SubtitleStatus.FAILED, 0),
        ],
        ids=[
            "pending_0_percent",
            "downloading_25_percent",
            "translating_75_percent",
            "completed_100_percent",
            "failed_0_percent",
        ],
    )
    def test_calculate_progress_for_status(self, subtitle_status, expected_progress):
        """Test progress calculation for different subtitle statuses."""
        subtitle = SubtitleResponse(
            id=uuid4(),
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            status=subtitle_status,
        )

        progress = calculate_job_progress_percentage(subtitle)

        assert progress == expected_progress
        assert 0 <= progress <= 100

    def test_calculate_progress_returns_integer(self):
        """Test that progress calculation returns an integer."""
        subtitle = SubtitleResponse(
            id=uuid4(),
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            status=SubtitleStatus.PENDING,
        )

        progress = calculate_job_progress_percentage(subtitle)

        assert isinstance(progress, int)


@pytest.mark.unit
class TestPublishJobFailureAndRaiseHttpError:
    """Test publish_job_failure_and_raise_http_error helper function."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error_message,http_status_code",
        [
            ("Failed to enqueue download task", status.HTTP_500_INTERNAL_SERVER_ERROR),
            (
                "Failed to enqueue translation task",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ),
            ("Invalid request", status.HTTP_400_BAD_REQUEST),
            ("Service unavailable", status.HTTP_503_SERVICE_UNAVAILABLE),
        ],
        ids=[
            "download_task_failure_500",
            "translation_task_failure_500",
            "invalid_request_400",
            "service_unavailable_503",
        ],
    )
    async def test_publishes_event_and_raises_http_exception(
        self, error_message, http_status_code
    ):
        """Test that function publishes failure event and raises HTTPException."""
        job_id = uuid4()

        with patch("manager.helpers.event_publisher") as mock_publisher:
            mock_publisher.publish_event = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await publish_job_failure_and_raise_http_error(
                    job_id, error_message, http_status_code
                )

            # Verify HTTPException was raised with correct status code
            assert exc_info.value.status_code == http_status_code
            assert exc_info.value.detail == error_message

            # Verify event was published
            assert mock_publisher.publish_event.called
            call_args = mock_publisher.publish_event.call_args[0][0]

            # Verify event structure
            assert call_args.event_type == EventType.JOB_FAILED
            assert call_args.job_id == job_id
            assert call_args.source == "manager"
            assert call_args.payload["error_message"] == error_message

    @pytest.mark.asyncio
    async def test_default_status_code_is_500(self):
        """Test that default HTTP status code is 500 if not specified."""
        job_id = uuid4()

        with patch("manager.helpers.event_publisher") as mock_publisher:
            mock_publisher.publish_event = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await publish_job_failure_and_raise_http_error(job_id, "Test error")

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_event_contains_timestamp(self):
        """Test that published event contains a timestamp."""
        job_id = uuid4()

        with patch("manager.helpers.event_publisher") as mock_publisher:
            mock_publisher.publish_event = AsyncMock()

            with pytest.raises(HTTPException):
                await publish_job_failure_and_raise_http_error(job_id, "Test error")

            call_args = mock_publisher.publish_event.call_args[0][0]
            assert call_args.timestamp is not None
