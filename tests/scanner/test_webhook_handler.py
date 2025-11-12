"""Tests for the Jellyfin webhook handler.

Note: Comprehensive duplicate prevention tests are in test_webhook_handler_dedup.py.
These tests focus on basic webhook processing functionality.
"""

from unittest.mock import AsyncMock, patch

import pytest

from common.duplicate_prevention import DuplicateCheckResult
from manager.schemas import JellyfinWebhookPayload, WebhookAcknowledgement
from scanner.webhook_handler import JellyfinWebhookHandler


class TestJellyfinWebhookHandler:
    """Test JellyfinWebhookHandler class."""

    @pytest.fixture
    def webhook_handler(self):
        """Create a webhook handler instance."""
        return JellyfinWebhookHandler()

    @pytest.fixture
    def valid_movie_payload(self):
        """Create a valid movie webhook payload."""
        return JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Test Movie",
            item_path="/media/movies/test_movie.mp4",
            item_id="test123",
            library_name="Movies",
            video_url="http://jellyfin.local/videos/test123",
        )

    @pytest.fixture
    def valid_episode_payload(self):
        """Create a valid episode webhook payload."""
        return JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Episode",
            item_name="Test Episode",
            item_path="/media/tv/test_episode.mp4",
            item_id="ep123",
            library_name="TV Shows",
            video_url="http://jellyfin.local/videos/ep123",
        )

    @pytest.mark.asyncio
    async def test_process_webhook_valid_movie_creates_job(
        self, webhook_handler, valid_movie_payload
    ):
        """Test that processing a valid movie webhook creates a job."""
        with patch("scanner.webhook_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()

            with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch(
                    "scanner.webhook_handler.duplicate_prevention"
                ) as mock_dedup:
                    mock_dedup.check_and_register = AsyncMock(
                        return_value=DuplicateCheckResult(
                            is_duplicate=False,
                            existing_job_id=None,
                            message="Request registered",
                        )
                    )

                    result = await webhook_handler.process_webhook(valid_movie_payload)

                    assert isinstance(result, WebhookAcknowledgement)
                    assert result.status == "received"
                    assert result.job_id is not None
                    assert "Test Movie" in result.message

                    # Verify job was created
                    mock_redis.save_job.assert_called_once()

                    # Verify events were published (MEDIA_DETECTED + SUBTITLE_REQUESTED)
                    assert mock_publisher.publish_event.call_count == 2

    @pytest.mark.asyncio
    async def test_process_webhook_valid_episode_creates_job(
        self, webhook_handler, valid_episode_payload
    ):
        """Test that processing a valid episode webhook creates a job."""
        with patch("scanner.webhook_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()

            with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch(
                    "scanner.webhook_handler.duplicate_prevention"
                ) as mock_dedup:
                    mock_dedup.check_and_register = AsyncMock(
                        return_value=DuplicateCheckResult(
                            is_duplicate=False,
                            existing_job_id=None,
                            message="Request registered",
                        )
                    )

                    result = await webhook_handler.process_webhook(
                        valid_episode_payload
                    )

                    assert isinstance(result, WebhookAcknowledgement)
                    assert result.status == "received"
                    assert result.job_id is not None

                    # Verify job was created
                    mock_redis.save_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_webhook_ignores_non_video_item(self, webhook_handler):
        """Test that non-video items are ignored."""
        audio_payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Audio",
            item_name="Test Song",
            item_path="/media/music/test_song.mp3",
        )

        result = await webhook_handler.process_webhook(audio_payload)

        assert isinstance(result, WebhookAcknowledgement)
        assert result.status == "ignored"
        assert "not a video" in result.message

    @pytest.mark.asyncio
    async def test_process_webhook_ignores_unprocessed_event(self, webhook_handler):
        """Test that unprocessed event types are ignored."""
        unprocessed_payload = JellyfinWebhookPayload(
            event="library.item.removed",
            item_type="Movie",
            item_name="Test Movie",
            item_path="/media/movies/test_movie.mp4",
        )

        result = await webhook_handler.process_webhook(unprocessed_payload)

        assert isinstance(result, WebhookAcknowledgement)
        assert result.status == "ignored"
        assert "not processed" in result.message

    @pytest.mark.asyncio
    async def test_process_webhook_handles_missing_video_url(self, webhook_handler):
        """Test that missing video URL/path returns error."""
        payload_without_url = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Test Movie",
            item_path=None,
            video_url=None,
        )

        result = await webhook_handler.process_webhook(payload_without_url)

        assert isinstance(result, WebhookAcknowledgement)
        assert result.status == "error"
        assert "No video URL or path provided" in result.message

    @pytest.mark.asyncio
    async def test_process_webhook_uses_item_path_when_url_missing(
        self, webhook_handler
    ):
        """Test that item_path is used when video_url is missing."""
        payload_with_path = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Test Movie",
            item_path="/media/movies/test_movie.mp4",
            video_url=None,
        )

        with patch("scanner.webhook_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()

            with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch(
                    "scanner.webhook_handler.duplicate_prevention"
                ) as mock_dedup:
                    mock_dedup.check_and_register = AsyncMock(
                        return_value=DuplicateCheckResult(
                            is_duplicate=False,
                            existing_job_id=None,
                            message="Request registered",
                        )
                    )

                    result = await webhook_handler.process_webhook(payload_with_path)

                    assert isinstance(result, WebhookAcknowledgement)
                    assert result.status == "received"

    @pytest.mark.asyncio
    async def test_process_webhook_handles_enqueue_failure(
        self, webhook_handler, valid_movie_payload
    ):
        """Test graceful handling of job creation failure."""
        with patch("scanner.webhook_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock(side_effect=Exception("Redis error"))

            with patch("scanner.webhook_handler.duplicate_prevention") as mock_dedup:
                mock_dedup.check_and_register = AsyncMock(
                    return_value=DuplicateCheckResult(
                        is_duplicate=False,
                        existing_job_id=None,
                        message="Request registered",
                    )
                )

                result = await webhook_handler.process_webhook(valid_movie_payload)

                assert isinstance(result, WebhookAcknowledgement)
                assert result.status == "error"
                assert "Redis error" in result.message

    @pytest.mark.asyncio
    async def test_process_webhook_library_item_updated_event(
        self, webhook_handler, valid_movie_payload
    ):
        """Test that library.item.updated events are processed."""
        valid_movie_payload.event = "library.item.updated"

        with patch("scanner.webhook_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()

            with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch(
                    "scanner.webhook_handler.duplicate_prevention"
                ) as mock_dedup:
                    mock_dedup.check_and_register = AsyncMock(
                        return_value=DuplicateCheckResult(
                            is_duplicate=False,
                            existing_job_id=None,
                            message="Request registered",
                        )
                    )

                    result = await webhook_handler.process_webhook(valid_movie_payload)

                    assert isinstance(result, WebhookAcknowledgement)
                    assert result.status == "received"

    @pytest.mark.asyncio
    async def test_process_webhook_publishes_media_file_detected_event(
        self, webhook_handler, valid_movie_payload
    ):
        """Test that MEDIA_FILE_DETECTED event is published."""
        with patch("scanner.webhook_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()

            with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch(
                    "scanner.webhook_handler.duplicate_prevention"
                ) as mock_dedup:
                    mock_dedup.check_and_register = AsyncMock(
                        return_value=DuplicateCheckResult(
                            is_duplicate=False,
                            existing_job_id=None,
                            message="Request registered",
                        )
                    )

                    result = await webhook_handler.process_webhook(valid_movie_payload)

                    assert result.status == "received"
                    # Should publish 2 events: MEDIA_DETECTED and SUBTITLE_REQUESTED
                    assert mock_publisher.publish_event.call_count == 2
