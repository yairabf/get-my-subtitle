"""Tests for OpenSubtitles language code expansion in downloader searches."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from downloader.worker import process_message


@pytest.mark.asyncio
async def test_downloader_search_expands_hebrew_language_codes():
    """
    When requesting Hebrew ('he'), the downloader should search OpenSubtitles using both
    the OpenSubtitles 3-letter code ('heb') and ISO code ('he').
    """
    request_id = uuid4()

    mock_message = MagicMock()
    mock_message.body = json.dumps(
        {
            "request_id": str(request_id),
            "video_url": "https://example.com/video.mp4",  # remote URL => no hash path
            "video_title": "Test Video",
            "language": "he",
        }
    ).encode()
    mock_message.routing_key = "subtitle.download"
    mock_message.exchange = ""
    mock_message.message_id = "test-message-id"
    mock_message.timestamp = None

    mock_channel = MagicMock()
    mock_channel.default_exchange = MagicMock()
    mock_channel.default_exchange.publish = AsyncMock()

    with patch("downloader.worker.redis_client") as mock_redis:
        mock_redis.update_phase = AsyncMock(return_value=True)

        with patch("downloader.worker.opensubtitles_client") as mock_client:
            mock_client.search_subtitles_by_hash = AsyncMock(return_value=[])
            mock_client.search_subtitles = AsyncMock(return_value=[])

            with patch("downloader.worker.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch("downloader.worker.settings") as mock_settings:
                    mock_settings.jellyfin_auto_translate = False
                    mock_settings.subtitle_fallback_language = "en"

                    await process_message(mock_message, mock_channel)

                    # Remote URL => should only do metadata search with expanded language list
                    mock_client.search_subtitles_by_hash.assert_not_called()
                    mock_client.search_subtitles.assert_called_once()
                    kwargs = mock_client.search_subtitles.call_args.kwargs
                    assert kwargs["languages"] == ["heb", "he"]


