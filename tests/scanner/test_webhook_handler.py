"""Tests for the Jellyfin webhook handler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.schemas import EventType, SubtitleStatus
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
        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = "es"
            mock_settings.jellyfin_auto_translate = True

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock()
                mock_redis.update_phase = AsyncMock()

                with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch(
                        "scanner.webhook_handler.orchestrator"
                    ) as mock_orchestrator:
                        mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                            return_value=True
                        )

                        result = await webhook_handler.process_webhook(
                            valid_movie_payload
                        )

                        assert isinstance(result, WebhookAcknowledgement)
                        assert result.status == "received"
                        assert result.job_id is not None
                        assert "Test Movie" in result.message

                        # Verify job was created
                        mock_redis.save_job.assert_called_once()

                        # Verify event was published
                        mock_publisher.publish_event.assert_called_once()
                        event_call = mock_publisher.publish_event.call_args[0][0]
                        assert event_call.event_type == EventType.MEDIA_FILE_DETECTED
                        assert event_call.source == "scanner"
                        assert event_call.payload["source"] == "jellyfin_webhook"

                        # Verify download task was enqueued
                        mock_orchestrator.enqueue_download_with_translation.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_webhook_valid_episode_creates_job(
        self, webhook_handler, valid_episode_payload
    ):
        """Test that processing a valid episode webhook creates a job."""
        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = None
            mock_settings.jellyfin_auto_translate = False

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock()
                mock_redis.update_phase = AsyncMock()

                with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch(
                        "scanner.webhook_handler.orchestrator"
                    ) as mock_orchestrator:
                        mock_orchestrator.enqueue_download_task = AsyncMock(
                            return_value=True
                        )

                        result = await webhook_handler.process_webhook(
                            valid_episode_payload
                        )

                        assert isinstance(result, WebhookAcknowledgement)
                        assert result.status == "received"
                        assert result.job_id is not None

                        # Verify download task was enqueued (not translation)
                        mock_orchestrator.enqueue_download_task.assert_called_once()

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

        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = None
            mock_settings.jellyfin_auto_translate = False

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock()

                with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch(
                        "scanner.webhook_handler.orchestrator"
                    ) as mock_orchestrator:
                        mock_orchestrator.enqueue_download_task = AsyncMock(
                            return_value=True
                        )

                        result = await webhook_handler.process_webhook(
                            payload_with_path
                        )

                        assert result.status == "received"
                        # Verify the path was used in the subtitle request
                        call_args = mock_redis.save_job.call_args[0][0]
                        assert call_args.video_url == "/media/movies/test_movie.mp4"

    @pytest.mark.asyncio
    async def test_process_webhook_handles_enqueue_failure(
        self, webhook_handler, valid_movie_payload
    ):
        """Test that enqueue failure is handled gracefully."""
        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = None
            mock_settings.jellyfin_auto_translate = False

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock()
                mock_redis.update_phase = AsyncMock()

                with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch(
                        "scanner.webhook_handler.orchestrator"
                    ) as mock_orchestrator:
                        mock_orchestrator.enqueue_download_task = AsyncMock(
                            return_value=False
                        )

                        result = await webhook_handler.process_webhook(
                            valid_movie_payload
                        )

                        assert isinstance(result, WebhookAcknowledgement)
                        assert result.status == "error"
                        assert result.job_id is not None
                        assert "Failed to enqueue" in result.message

                        # Verify job status was updated to FAILED
                        mock_redis.update_phase.assert_called_once()
                        call_args = mock_redis.update_phase.call_args
                        # update_phase(job_id, status, source="scanner", metadata={...})
                        # call_args is a tuple: (args, kwargs)
                        assert (
                            call_args[0][1] == SubtitleStatus.FAILED
                        )  # status is second positional arg
                        assert (
                            call_args[1]["source"] == "scanner"
                        )  # source is keyword arg
                        assert "error_message" in call_args[1].get("metadata", {})

    @pytest.mark.asyncio
    async def test_process_webhook_handles_exception(self, webhook_handler):
        """Test that exceptions are handled gracefully."""
        invalid_payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_type="Movie",
            item_name="Test Movie",
            item_path="/media/movies/test_movie.mp4",
        )

        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = None
            mock_settings.jellyfin_auto_translate = False

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock(side_effect=Exception("Redis error"))

                result = await webhook_handler.process_webhook(invalid_payload)

                assert isinstance(result, WebhookAcknowledgement)
                assert result.status == "error"
                assert "Internal server error" in result.message

    @pytest.mark.asyncio
    async def test_process_webhook_library_item_updated_event(
        self, webhook_handler, valid_movie_payload
    ):
        """Test that library.item.updated events are processed."""
        updated_payload = JellyfinWebhookPayload(
            event="library.item.updated",
            item_type="Movie",
            item_name="Updated Movie",
            item_path="/media/movies/updated_movie.mp4",
            video_url="http://jellyfin.local/videos/updated123",
        )

        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = None
            mock_settings.jellyfin_auto_translate = False

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock()

                with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch(
                        "scanner.webhook_handler.orchestrator"
                    ) as mock_orchestrator:
                        mock_orchestrator.enqueue_download_task = AsyncMock(
                            return_value=True
                        )

                        result = await webhook_handler.process_webhook(updated_payload)

                        assert result.status == "received"
                        assert "Updated Movie" in result.message

    @pytest.mark.asyncio
    async def test_process_webhook_publishes_media_file_detected_event(
        self, webhook_handler, valid_movie_payload
    ):
        """Test that MEDIA_FILE_DETECTED event is published with correct payload."""
        with patch("scanner.webhook_handler.settings") as mock_settings:
            mock_settings.jellyfin_default_source_language = "en"
            mock_settings.jellyfin_default_target_language = "es"
            mock_settings.jellyfin_auto_translate = True

            with patch("scanner.webhook_handler.redis_client") as mock_redis:
                mock_redis.save_job = AsyncMock()

                with patch("scanner.webhook_handler.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch(
                        "scanner.webhook_handler.orchestrator"
                    ) as mock_orchestrator:
                        mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                            return_value=True
                        )

                        await webhook_handler.process_webhook(valid_movie_payload)

                        # Verify event was published
                        mock_publisher.publish_event.assert_called_once()
                        event = mock_publisher.publish_event.call_args[0][0]

                        assert event.event_type == EventType.MEDIA_FILE_DETECTED
                        assert event.source == "scanner"
                        assert event.payload["video_title"] == "Test Movie"
                        assert (
                            event.payload["video_url"] == valid_movie_payload.video_url
                        )
                        assert event.payload["language"] == "en"
                        assert event.payload["target_language"] == "es"
                        assert event.payload["source"] == "jellyfin_webhook"
