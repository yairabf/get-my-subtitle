"""Tests for the downloader worker."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.schemas import EventType, SubtitleStatus
from downloader.worker import process_message


class TestDownloaderWorker:
    """Test downloader worker functionality."""

    @pytest.mark.asyncio
    async def test_process_message_subtitle_found(self):
        """Test processing a message when subtitle is found."""
        request_id = uuid4()

        # Create mock message
        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "imdb_id": "tt1234567",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        # Mock subtitle search results
        mock_search_results = [
            {
                "id": "123",
                "attributes": {
                    "files": [{"file_id": 456}],
                },
            }
        ]

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                mock_client.search_subtitles = AsyncMock(
                    return_value=mock_search_results
                )
                mock_client.download_subtitle = AsyncMock(
                    return_value=Path("/tmp/subtitle.srt")
                )
                mock_client.auth_method = "rest"

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    await process_message(mock_message)

                    # Verify subtitle was searched
                    mock_client.search_subtitles.assert_called_once()

                    # Verify subtitle was downloaded
                    mock_client.download_subtitle.assert_called_once()

                    # Verify SUBTITLE_READY event was published
                    mock_publisher.publish_event.assert_called_once()
                    event_call = mock_publisher.publish_event.call_args[0][0]
                    assert event_call.event_type == EventType.SUBTITLE_READY
                    assert event_call.job_id == request_id

    @pytest.mark.asyncio
    async def test_process_message_subtitle_not_found(self):
        """Test processing when subtitle is not found - should request translation."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_title": "Obscure Movie",
                "language": "he",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                # No subtitles found
                mock_client.search_subtitles = AsyncMock(return_value=[])

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    await process_message(mock_message)

                    # Verify SUBTITLE_TRANSLATE_REQUESTED event was published
                    mock_publisher.publish_event.assert_called_once()
                    event_call = mock_publisher.publish_event.call_args[0][0]
                    assert (
                        event_call.event_type == EventType.SUBTITLE_TRANSLATE_REQUESTED
                    )
                    assert event_call.job_id == request_id
                    assert event_call.payload["reason"] == "subtitle_not_found"

    @pytest.mark.asyncio
    async def test_process_message_json_decode_error(self):
        """Test processing a message with invalid JSON."""
        # Create mock message with invalid JSON
        mock_message = MagicMock()
        mock_message.body = b"invalid json"
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            # Should not raise exception
            await process_message(mock_message)

            # Redis update should not be called (no request_id)
            mock_redis.update_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_redis_unavailable(self):
        """Test processing when Redis is unavailable."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "https://example.com/video.mp4",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=False)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                # Mock successful subtitle search and download
                mock_client.search_subtitles = AsyncMock(
                    return_value=[{"IDSubtitleFile": "123"}]
                )
                mock_client.download_subtitle = AsyncMock(
                    return_value=Path("/tmp/subtitle.srt")
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    # Should not raise exception even if Redis update fails
                    await process_message(mock_message)

                    # Verify update_phase was attempted
                    assert mock_redis.update_phase.call_count > 0

    @pytest.mark.asyncio
    async def test_process_message_api_error_fallback(self):
        """Test fallback to translation when OpenSubtitles API fails."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_title": "Test Video",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                # Simulate API error
                from downloader.opensubtitles_client import OpenSubtitlesAPIError

                mock_client.search_subtitles = AsyncMock(
                    side_effect=OpenSubtitlesAPIError("API error")
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    await process_message(mock_message)

                    # Verify fallback to translation
                    mock_publisher.publish_event.assert_called_once()
                    event_call = mock_publisher.publish_event.call_args[0][0]
                    assert (
                        event_call.event_type == EventType.SUBTITLE_TRANSLATE_REQUESTED
                    )
                    assert event_call.payload["reason"] == "api_error"

    @pytest.mark.asyncio
    async def test_process_message_rate_limit_error(self):
        """Test handling of rate limit errors."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_title": "Test Video",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                # Simulate rate limit error
                from downloader.opensubtitles_client import OpenSubtitlesRateLimitError

                mock_client.search_subtitles = AsyncMock(
                    side_effect=OpenSubtitlesRateLimitError("Rate limit exceeded")
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    await process_message(mock_message)

                    # Verify JOB_FAILED event with rate_limit error
                    mock_publisher.publish_event.assert_called_once()
                    event_call = mock_publisher.publish_event.call_args[0][0]
                    assert event_call.event_type == EventType.JOB_FAILED
                    assert event_call.payload["error_type"] == "rate_limit"

    @pytest.mark.asyncio
    async def test_process_message_processing_error(self):
        """Test handling of processing errors."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps({"request_id": str(request_id)}).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            # Simulate an error during processing
            mock_redis.update_phase = AsyncMock(
                side_effect=Exception("Processing error")
            )

            with patch("downloader.worker.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                # Should handle exception gracefully
                await process_message(mock_message)

                # Verify JOB_FAILED event was published
                mock_publisher.publish_event.assert_called_once()
                event_call = mock_publisher.publish_event.call_args[0][0]
                assert event_call.event_type == EventType.JOB_FAILED


class TestWorkerIntegration:
    """Test worker integration with OpenSubtitles API."""

    @pytest.mark.asyncio
    async def test_worker_opensubtitles_integration_flow(self):
        """Test complete flow: search, download, and event publishing."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "https://example.com/video.mp4",
                "video_title": "Test Video",
                "imdb_id": "tt1234567",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        # Mock subtitle found and downloaded
        mock_search_results = [
            {"id": "123", "attributes": {"files": [{"file_id": 456}]}}
        ]

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                mock_client.search_subtitles = AsyncMock(
                    return_value=mock_search_results
                )
                mock_client.download_subtitle = AsyncMock(
                    return_value=Path("/tmp/subtitle.srt")
                )
                mock_client.auth_method = "rest"

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    await process_message(mock_message)

                    # Verify complete flow
                    mock_redis.update_phase.assert_called_with(
                        request_id,
                        SubtitleStatus.DOWNLOAD_IN_PROGRESS,
                        source="downloader",
                    )
                    mock_client.search_subtitles.assert_called_once_with(
                        imdb_id="tt1234567", query="Test Video", languages=["en"]
                    )
                    mock_client.download_subtitle.assert_called_once()
                    mock_publisher.publish_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_handles_missing_video_metadata(self):
        """Test worker handles missing video title/IMDB ID gracefully."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                # No video_title or imdb_id
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                mock_client.search_subtitles = AsyncMock(return_value=[])

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    await process_message(mock_message)

                    # Should still attempt search with None values
                    mock_client.search_subtitles.assert_called_once_with(
                        imdb_id=None, query=None, languages=["en"]
                    )
