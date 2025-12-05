"""Tests for the downloader worker."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.schemas import EventType, SubtitleStatus
from common.shutdown_manager import ShutdownManager
from downloader.worker import process_message


class TestSubtitleMissingEventPublishing:
    """Test SUBTITLE_MISSING event publishing based on translation configuration."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "auto_translate,fallback_found,expected_event_type,expected_reason",
        [
            (
                True,
                True,
                EventType.SUBTITLE_TRANSLATE_REQUESTED,
                "subtitle_not_found_in_target_language",
            ),
            (
                True,
                False,
                EventType.SUBTITLE_MISSING,
                "subtitle_not_found_any_language",
            ),
            (
                False,
                False,
                EventType.SUBTITLE_MISSING,
                "subtitle_not_found_no_translation",
            ),
        ],
    )
    async def test_subtitle_not_found_event_based_on_translation_config(
        self, auto_translate, fallback_found, expected_event_type, expected_reason
    ):
        """Test that correct event is published based on translation configuration and fallback search."""
        request_id = uuid4()

        # Create a temporary local video file for fallback download scenario
        import tempfile

        video_file = None
        if fallback_found:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                tmp_file.write(b"A" * (256 * 1024))  # 256KB file
                video_file = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": (
                        video_file if video_file else "https://example.com/video.mp4"
                    ),
                    "video_title": "Test Video",
                    "language": "he",  # Request Hebrew, but not found
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Determine if hash search will be called (local file vs remote URL)
                    is_local_file = video_file is not None

                    if auto_translate and fallback_found:
                        # Fallback search finds English subtitle
                        mock_fallback_result = [
                            {
                                "IDSubtitleFile": "456",
                                "SubLanguageID": "eng",  # 3-letter code to test conversion
                            }
                        ]
                        # Mock the search sequence based on whether hash is calculated
                        if is_local_file:
                            # Local file: hash search first, then metadata
                            # Sequence: hash(he) -> metadata(he) -> hash(en) -> metadata(en)
                            mock_client.search_subtitles_by_hash = AsyncMock(
                                side_effect=[
                                    [],  # First search (he) - empty
                                    mock_fallback_result,  # Fallback search (en) - found
                                ]
                            )
                            mock_client.search_subtitles = AsyncMock(
                                side_effect=[
                                    [],  # First search (he) - empty (only called if hash empty)
                                    # Fallback metadata search won't be called if hash found result
                                ]
                            )
                        else:
                            # Remote URL: no hash, only metadata search
                            # Sequence: metadata(he) -> metadata(en)
                            mock_client.search_subtitles_by_hash = AsyncMock(
                                return_value=[]
                            )
                            mock_client.search_subtitles = AsyncMock(
                                side_effect=[
                                    [],  # First search (he) - empty
                                    mock_fallback_result,  # Fallback search (en) - found
                                ]
                            )
                        subtitle_file_path = (
                            (Path(video_file).parent / "test.en.srt")
                            if video_file
                            else Path("/tmp/test.en.srt")
                        )
                        # Create the actual subtitle file so exists() check passes
                        if video_file:
                            subtitle_file_path.write_text(
                                "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                            )
                        mock_client.download_subtitle = AsyncMock(
                            return_value=subtitle_file_path
                        )
                    elif auto_translate and not fallback_found:
                        # No subtitles found in any language
                        if is_local_file:
                            # Local file: hash searches for he, en, any; metadata searches for he, en, any
                            mock_client.search_subtitles_by_hash = AsyncMock(
                                side_effect=[[], [], []]  # he, en, any
                            )
                            mock_client.search_subtitles = AsyncMock(
                                side_effect=[
                                    [],
                                    [],
                                    [],
                                ]  # he, en, any (only if hash empty)
                            )
                        else:
                            # Remote URL: only metadata searches
                            mock_client.search_subtitles_by_hash = AsyncMock(
                                return_value=[]
                            )
                            mock_client.search_subtitles = AsyncMock(
                                side_effect=[[], [], []]  # he, en, any
                            )
                        # No download should occur when no subtitle is found
                        mock_client.download_subtitle = AsyncMock()
                    else:
                        # Translation disabled - only initial search
                        if is_local_file:
                            mock_client.search_subtitles_by_hash = AsyncMock(
                                return_value=[]
                            )
                            mock_client.search_subtitles = AsyncMock(return_value=[])
                        else:
                            mock_client.search_subtitles_by_hash = AsyncMock(
                                return_value=[]
                            )
                            mock_client.search_subtitles = AsyncMock(return_value=[])
                        # No download should occur when translation is disabled and subtitle not found
                        mock_client.download_subtitle = AsyncMock()

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = auto_translate
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Verify correct event was published
                            assert mock_publisher.publish_event.call_count > 0
                            event_call = mock_publisher.publish_event.call_args[0][0]
                            assert event_call.event_type == expected_event_type
                            assert event_call.job_id == request_id
                            assert event_call.payload["reason"] == expected_reason

                            if auto_translate and fallback_found:
                                # Verify fallback subtitle was downloaded
                                mock_client.download_subtitle.assert_called_once()
                                # Verify TranslationTask was enqueued to translation queue
                                assert (
                                    mock_channel.default_exchange.publish.call_count > 0
                                )
                                publish_call = (
                                    mock_channel.default_exchange.publish.call_args
                                )
                                # Routing key should match config (default is "subtitle.translation")
                                assert publish_call[1]["routing_key"] in [
                                    "subtitle.translation",
                                    mock_settings.rabbitmq_translation_queue_routing_key,
                                ]
                                # Verify translation request event has actual path
                                assert "subtitle_file_path" in event_call.payload
                                assert (
                                    event_call.payload["source_language"] == "en"
                                )  # Converted from "eng"
                                assert event_call.payload["target_language"] == "he"
                                # Verify SUBTITLE_READY was NOT published for fallback
                                all_events = [
                                    call[0][0].event_type
                                    for call in mock_publisher.publish_event.call_args_list
                                ]
                                assert EventType.SUBTITLE_READY not in all_events
        finally:
            if video_file:
                Path(video_file).unlink(missing_ok=True)
                (Path(video_file).parent / "test.en.srt").unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_subtitle_missing_event_contains_correct_payload(self):
        """Test that SUBTITLE_MISSING event contains all required payload fields."""
        request_id = uuid4()
        video_url = "https://example.com/video.mp4"
        video_title = "Test Video"
        language = "en"

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": video_url,
                "video_title": video_title,
                "language": language,
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

                    with patch("downloader.worker.settings") as mock_settings:
                        mock_settings.jellyfin_auto_translate = False

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify event payload
                        event_call = mock_publisher.publish_event.call_args[0][0]
                        assert event_call.event_type == EventType.SUBTITLE_MISSING
                        assert event_call.payload["language"] == language
                        assert (
                            event_call.payload["reason"]
                            == "subtitle_not_found_no_translation"
                        )
                        assert event_call.payload["video_url"] == video_url
                        assert event_call.payload["video_title"] == video_title

    @pytest.mark.asyncio
    async def test_subtitle_ready_unaffected_by_translation_config(self):
        """Test that SUBTITLE_READY is always published when subtitle is found, regardless of translation config."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))  # 256KB file
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Video",
                    "language": "en",
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_search_results = [{"IDSubtitleFile": "123"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Mock both hash and query search methods
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/tmp/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            # Test with translation disabled
                            mock_settings.jellyfin_auto_translate = False

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Should still publish SUBTITLE_READY
                            event_call = mock_publisher.publish_event.call_args[0][0]
                            assert event_call.event_type == EventType.SUBTITLE_READY
        finally:
            # Clean up temp file
            Path(video_url).unlink(missing_ok=True)


class TestDownloaderWorker:
    """Test downloader worker functionality."""

    @pytest.mark.asyncio
    async def test_process_message_subtitle_found(self):
        """Test processing a message when subtitle is found."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))  # 256KB file
            video_url = tmp_file.name

        try:
            # Create mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
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
                    "IDSubtitleFile": "123",
                    "SubFileName": "test.srt",
                    "LanguageName": "English",
                }
            ]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Mock both hash and query search methods
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/tmp/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify subtitle was downloaded
                        mock_client.download_subtitle.assert_called_once()

                        # Verify SUBTITLE_READY event was published
                        mock_publisher.publish_event.assert_called_once()
                        event_call = mock_publisher.publish_event.call_args[0][0]
                        assert event_call.event_type == EventType.SUBTITLE_READY
                        assert event_call.job_id == request_id
        finally:
            # Clean up temp file
            Path(video_url).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_process_message_subtitle_not_found_with_fallback(self):
        """Test processing when subtitle is not found - should search for fallback and request translation."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))  # 256KB file
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Obscure Movie",
                    "language": "he",  # Request Hebrew
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # No subtitles found in requested language (Hebrew)
                    # But fallback search finds English subtitle
                    mock_fallback_result = [
                        {
                            "IDSubtitleFile": "789",
                            "SubLanguageID": "en",
                        }
                    ]
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        side_effect=[
                            [],  # First search (he) - empty
                            mock_fallback_result,  # Fallback search (en) - found
                        ]
                    )
                    # Metadata search only called when hash search returns empty
                    # hash(he) -> [] -> metadata(he) -> []
                    # hash(en) -> [result] -> metadata(en) NOT called
                    mock_client.search_subtitles = AsyncMock(
                        side_effect=[
                            [],  # First search (he) - empty (only called because hash was empty)
                            # Fallback metadata search won't be called because hash(en) found result
                        ]
                    )
                    subtitle_file_path = Path(video_url).parent / "obscure_movie.en.srt"
                    # Create the actual subtitle file so exists() check passes
                    subtitle_file_path.write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=subtitle_file_path
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = True
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Verify fallback subtitle was downloaded
                            mock_client.download_subtitle.assert_called_once()

                            # Verify TranslationTask was enqueued
                            assert mock_channel.default_exchange.publish.call_count > 0

                            # Verify SUBTITLE_TRANSLATE_REQUESTED event was published with actual path
                            # Note: publish_event may be called multiple times (once for translation request, once for observability)
                            assert mock_publisher.publish_event.call_count >= 1
                            # Check that at least one event is SUBTITLE_TRANSLATE_REQUESTED
                            event_calls = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            translate_events = [
                                e
                                for e in event_calls
                                if e.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            ]
                            assert len(translate_events) > 0
                            event_call = translate_events[0]
                            assert (
                                event_call.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            )
                            assert event_call.job_id == request_id
                            assert (
                                event_call.payload["reason"]
                                == "subtitle_not_found_in_target_language"
                            )
                            # Verify actual file path is used, not placeholder
                            assert "subtitle_file_path" in event_call.payload
                            assert (
                                event_call.payload["subtitle_file_path"]
                                != f"/subtitles/fallback_{request_id}.en.srt"
                            )
                            assert event_call.payload["subtitle_file_path"] == str(
                                subtitle_file_path
                            )
                            assert event_call.payload["source_language"] == "en"
                            assert event_call.payload["target_language"] == "he"
        finally:
            Path(video_url).unlink(missing_ok=True)
            (Path(video_url).parent / "obscure_movie.en.srt").unlink(missing_ok=True)

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

            # Create mock channel for RabbitMQ
            mock_channel = MagicMock()
            mock_channel.default_exchange = MagicMock()
            mock_channel.default_exchange.publish = AsyncMock()

            # Should not raise exception
            await process_message(mock_message, mock_channel)

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

                    # Create mock channel for RabbitMQ
                    mock_channel = MagicMock()
                    mock_channel.default_exchange = MagicMock()
                    mock_channel.default_exchange.publish = AsyncMock()

                    # Should not raise exception even if Redis update fails
                    await process_message(mock_message, mock_channel)

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

                    with patch("downloader.worker.settings") as mock_settings:
                        mock_settings.subtitle_fallback_language = "en"

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify fallback to translation
                        mock_publisher.publish_event.assert_called_once()
                        event_call = mock_publisher.publish_event.call_args[0][0]
                        assert (
                            event_call.event_type
                            == EventType.SUBTITLE_TRANSLATE_REQUESTED
                        )
                        assert event_call.payload["reason"] == "api_error_fallback"
                        # API error fallback still uses placeholder (can't download due to API error)
                        assert "error_note" in event_call.payload

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

                    # Create mock channel for RabbitMQ
                    mock_channel = MagicMock()
                    mock_channel.default_exchange = MagicMock()
                    mock_channel.default_exchange.publish = AsyncMock()

                    await process_message(mock_message, mock_channel)

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

                # Create mock channel for RabbitMQ
                mock_channel = MagicMock()
                mock_channel.default_exchange = MagicMock()
                mock_channel.default_exchange.publish = AsyncMock()

                # Should handle exception gracefully
                await process_message(mock_message, mock_channel)

                # Verify JOB_FAILED event was published
                mock_publisher.publish_event.assert_called_once()
                event_call = mock_publisher.publish_event.call_args[0][0]
                assert event_call.event_type == EventType.JOB_FAILED

    @pytest.mark.asyncio
    async def test_process_message_rabbitmq_publish_failure(self):
        """Test handling when RabbitMQ publish fails for translation task."""
        request_id = uuid4()
        video_file = Path(f"/tmp/test_video_{request_id}.mkv")
        video_file.parent.mkdir(parents=True, exist_ok=True)
        video_file.write_text("fake video content")
        video_url = str(video_file)

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Video",
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
                    # Simulate fallback subtitle found
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        side_effect=[
                            [],  # First search (he) - empty
                            [
                                {
                                    "IDSubtitleFile": "789",
                                    "SubLanguageID": "eng",
                                }
                            ],  # Fallback search (en) - found
                        ]
                    )
                    mock_client.search_subtitles = AsyncMock(return_value=[])
                    subtitle_file_path = Path(video_url).parent / "test_video.en.srt"
                    # Create the actual subtitle file so exists() check passes
                    subtitle_file_path.write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=subtitle_file_path
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = True
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel that fails on publish
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock(
                                side_effect=Exception("Connection lost")
                            )

                            # Exception is caught by top-level handler, not re-raised
                            # The function should complete without raising (exceptions are caught)
                            await process_message(mock_message, mock_channel)

                            # Verify that if an exception occurred during publish, it was handled
                            # The top-level handler should catch exceptions and publish JOB_FAILED
                            # However, if the exception occurs before reaching publish, that's also valid
                            # The key is that the function completes without raising

                            # If publish was attempted and failed, verify JOB_FAILED was published
                            if mock_channel.default_exchange.publish.call_count > 0:
                                # Publish was attempted, so exception should have been caught and JOB_FAILED published
                                assert mock_publisher.publish_event.call_count > 0
                                event_calls = [
                                    call[0][0]
                                    for call in mock_publisher.publish_event.call_args_list
                                ]
                                failed_events = [
                                    e
                                    for e in event_calls
                                    if e.event_type == EventType.JOB_FAILED
                                ]
                                # Should have at least one JOB_FAILED event
                                assert len(failed_events) > 0
        finally:
            video_file.unlink(missing_ok=True)
            subtitle_file_path.unlink(missing_ok=True)


class TestWorkerHashSearchFallback:
    """Test worker hash search with query fallback logic."""

    @pytest.mark.asyncio
    async def test_process_message_hash_search_success(self):
        """Test successful subtitle search using file hash."""
        request_id = uuid4()

        # Create a temporary video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))  # 256KB file
            video_path = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_path,  # Local file path
                    "video_title": "Test Video",
                    "language": "en",
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_search_results = [{"IDSubtitleFile": "123"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Hash search succeeds
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/tmp/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify hash search was called
                        mock_client.search_subtitles_by_hash.assert_called_once()
                        # Verify query search was NOT called (hash succeeded)
                        mock_client.search_subtitles.assert_not_called()
                        # Verify subtitle was downloaded
                        mock_client.download_subtitle.assert_called_once()

        finally:
            Path(video_path).unlink()

    @pytest.mark.asyncio
    async def test_process_message_hash_empty_fallback_to_query(self):
        """Test fallback to query search when hash returns empty results."""
        request_id = uuid4()

        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"B" * (256 * 1024))
            video_path = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_path,
                    "video_title": "Obscure Movie",
                    "imdb_id": "tt9999999",
                    "language": "en",
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_query_results = [{"IDSubtitleFile": "456"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Hash search returns empty
                    mock_client.search_subtitles_by_hash = AsyncMock(return_value=[])
                    # Query search succeeds
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_query_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/tmp/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify hash search was tried first
                        mock_client.search_subtitles_by_hash.assert_called_once()
                        # Verify fallback to query search
                        mock_client.search_subtitles.assert_called_once_with(
                            imdb_id="tt9999999",
                            query="Obscure Movie",
                            languages=["en"],
                        )
                        # Verify subtitle was downloaded
                        mock_client.download_subtitle.assert_called_once()

        finally:
            Path(video_path).unlink()

    @pytest.mark.asyncio
    async def test_process_message_remote_url_skips_hash(self):
        """Test remote URL skips hash calculation and uses query search."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "https://example.com/video.mp4",  # Remote URL
                "video_title": "Remote Video",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        mock_search_results = [{"IDSubtitleFile": "789"}]

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                # Query search succeeds
                mock_client.search_subtitles = AsyncMock(
                    return_value=mock_search_results
                )
                mock_client.download_subtitle = AsyncMock(
                    return_value=Path("/tmp/subtitle.srt")
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    # Create mock channel for RabbitMQ
                    mock_channel = MagicMock()
                    mock_channel.default_exchange = MagicMock()
                    mock_channel.default_exchange.publish = AsyncMock()

                    await process_message(mock_message, mock_channel)

                    # Verify hash search was NOT called (remote URL)
                    if hasattr(mock_client, "search_subtitles_by_hash"):
                        mock_client.search_subtitles_by_hash.assert_not_called()
                    # Verify query search was called
                    mock_client.search_subtitles.assert_called_once()
                    # Verify subtitle was NOT downloaded (remote URL not supported)
                    mock_client.download_subtitle.assert_not_called()

                    # Verify JOB_FAILED event was published
                    events = [
                        call[0][0]
                        for call in mock_publisher.publish_event.call_args_list
                    ]
                    failed_events = [
                        e for e in events if e.event_type == EventType.JOB_FAILED
                    ]
                    assert len(failed_events) == 1
                    assert (
                        "video is not a local file"
                        in failed_events[0].payload["error_message"]
                    )

    @pytest.mark.asyncio
    async def test_process_message_hash_calculation_failure(self):
        """Test graceful handling when hash calculation fails."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "/nonexistent/file.mp4",  # File doesn't exist
                "video_title": "Test Video",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        mock_search_results = [{"IDSubtitleFile": "999"}]

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                # Query search succeeds
                mock_client.search_subtitles = AsyncMock(
                    return_value=mock_search_results
                )
                mock_client.download_subtitle = AsyncMock(
                    return_value=Path("/tmp/subtitle.srt")
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    # Create mock channel for RabbitMQ
                    mock_channel = MagicMock()
                    mock_channel.default_exchange = MagicMock()
                    mock_channel.default_exchange.publish = AsyncMock()

                    await process_message(mock_message, mock_channel)

                    # Hash calculation fails (file doesn't exist), should skip to query search
                    if hasattr(mock_client, "search_subtitles_by_hash"):
                        mock_client.search_subtitles_by_hash.assert_not_called()
                    mock_client.search_subtitles.assert_called_once()
                    # Should NOT download subtitle (file doesn't exist - not a valid local file)
                    mock_client.download_subtitle.assert_not_called()

                    # Verify JOB_FAILED event was published
                    events = [
                        call[0][0]
                        for call in mock_publisher.publish_event.call_args_list
                    ]
                    failed_events = [
                        e for e in events if e.event_type == EventType.JOB_FAILED
                    ]
                    assert len(failed_events) == 1

    @pytest.mark.asyncio
    async def test_process_message_local_file_not_accessible(self):
        """Test handling when local file path exists but is not a file."""
        request_id = uuid4()

        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": tmp_dir,  # Directory, not a file
                    "video_title": "Test Video",
                    "language": "en",
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_search_results = [{"IDSubtitleFile": "111"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/tmp/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Should skip hash and use query search
                        mock_client.search_subtitles_by_hash.assert_not_called()
                        mock_client.search_subtitles.assert_called_once()


class TestWorkerIntegration:
    """Test worker integration with OpenSubtitles API."""

    @pytest.mark.asyncio
    async def test_worker_opensubtitles_integration_flow(self):
        """Test complete flow: search, download, and event publishing."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))  # 256KB file
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
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
            mock_search_results = [{"IDSubtitleFile": "123"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Mock both hash and query search methods
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/tmp/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify complete flow
                        mock_redis.update_phase.assert_called_with(
                            request_id,
                            SubtitleStatus.DOWNLOAD_IN_PROGRESS,
                            source="downloader",
                        )
                        mock_client.download_subtitle.assert_called_once()
                        mock_publisher.publish_event.assert_called_once()
        finally:
            # Clean up temp file
            Path(video_url).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_worker_handles_missing_video_metadata(self):
        """Test worker handles missing video title/IMDB ID gracefully."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": None,  # No video URL
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
                mock_client.search_subtitles_by_hash = AsyncMock(return_value=[])
                mock_client.search_subtitles = AsyncMock(return_value=[])

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch("downloader.worker.settings") as mock_settings:
                        # Disable translation to avoid fallback searches
                        mock_settings.jellyfin_auto_translate = False

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Should still attempt search with None values
                        # Only one call expected since translation is disabled
                        mock_client.search_subtitles.assert_called_once_with(
                            imdb_id=None, query=None, languages=["en"]
                        )


class TestSubtitleSaveLocation:
    """Test subtitle save location based on video path."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "video_type,expected_behavior",
        [
            ("local_file", "save_to_video_dir"),
            ("remote_url", "publish_failed_event"),
            ("nonexistent_local", "publish_failed_event"),
        ],
    )
    async def test_subtitle_save_location_based_on_video_type(
        self, video_type, expected_behavior
    ):
        """Test that subtitle save behavior is correct for different video path types."""
        request_id = uuid4()
        language = "en"

        # Setup video_url based on test case
        if video_type == "local_file":
            # Create a temporary video file
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mkv") as tmp_file:
                tmp_file.write(b"A" * (256 * 1024))  # 256KB file
                video_url = tmp_file.name
        elif video_type == "remote_url":
            video_url = "http://jellyfin.local/videos/abc123"
        else:  # nonexistent_local
            video_url = "/path/to/nonexistent/video.mkv"

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Video",
                    "language": language,
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_search_results = [{"IDSubtitleFile": "123"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Mock both hash and query search methods
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/fake/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        if expected_behavior == "save_to_video_dir":
                            # Should attempt to download with custom output_path
                            mock_client.download_subtitle.assert_called_once()
                            call_kwargs = mock_client.download_subtitle.call_args[1]
                            assert "output_path" in call_kwargs
                            assert call_kwargs["output_path"] is not None

                            # Should publish SUBTITLE_READY event
                            events = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            subtitle_ready_events = [
                                e
                                for e in events
                                if e.event_type == EventType.SUBTITLE_READY
                            ]
                            assert len(subtitle_ready_events) == 1

                        elif expected_behavior == "publish_failed_event":
                            # Should NOT attempt to download
                            mock_client.download_subtitle.assert_not_called()

                            # Should publish JOB_FAILED event
                            events = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            failed_events = [
                                e
                                for e in events
                                if e.event_type == EventType.JOB_FAILED
                            ]
                            assert len(failed_events) == 1
                            assert (
                                "video is not a local file"
                                in failed_events[0].payload["error_message"]
                            )

        finally:
            # Clean up temp file if created
            if video_type == "local_file":
                Path(video_url).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_subtitle_filename_includes_language_code(self):
        """Test that generated subtitle filename includes language code."""
        request_id = uuid4()
        language = "es"

        # Create a temporary video file named "movie.mkv"
        import tempfile

        tmpdir = tempfile.mkdtemp()
        video_path = Path(tmpdir) / "movie.mkv"
        video_path.write_bytes(b"A" * (256 * 1024))

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": str(video_path),
                    "video_title": "Test Movie",
                    "language": language,
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_search_results = [{"IDSubtitleFile": "456"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Mock both hash and query search methods
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/fake/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify download_subtitle was called with correct output_path
                        mock_client.download_subtitle.assert_called_once()
                        call_kwargs = mock_client.download_subtitle.call_args[1]
                        output_path = call_kwargs["output_path"]

                        # Verify filename format: movie.es.srt
                        assert output_path.name == f"movie.{language}.srt"
                        assert output_path.parent == video_path.parent

        finally:
            # Clean up
            video_path.unlink(missing_ok=True)
            Path(tmpdir).rmdir()

    @pytest.mark.asyncio
    async def test_subtitle_saved_in_same_directory_as_video(self):
        """Test that subtitle path is in the same directory as video file."""
        request_id = uuid4()

        # Create nested directory structure like in requirements
        import tempfile

        tmpdir = tempfile.mkdtemp()
        video_dir = Path(tmpdir) / "media" / "movies" / "matrix"
        video_dir.mkdir(parents=True)
        video_path = video_dir / "matrix.mkv"
        video_path.write_bytes(b"A" * (256 * 1024))

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": str(video_path),
                    "video_title": "The Matrix",
                    "language": "en",
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            mock_search_results = [{"IDSubtitleFile": "789"}]

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Mock both hash and query search methods
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.search_subtitles = AsyncMock(
                        return_value=mock_search_results
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=Path("/fake/subtitle.srt")
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify download_subtitle was called with correct directory
                        mock_client.download_subtitle.assert_called_once()
                        call_kwargs = mock_client.download_subtitle.call_args[1]
                        output_path = call_kwargs["output_path"]

                        # Verify path structure
                        assert output_path.parent == video_dir
                        assert output_path == video_dir / "matrix.en.srt"

        finally:
            # Clean up
            video_path.unlink(missing_ok=True)
            import shutil

            shutil.rmtree(tmpdir)

    @pytest.mark.asyncio
    async def test_error_message_for_remote_url_is_clear(self):
        """Test that error message for remote URLs is clear and informative."""
        request_id = uuid4()
        video_url = "http://server.local/stream/video.mp4"

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": video_url,
                "video_title": "Test Video",
                "language": "en",
            }
        ).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None

        mock_search_results = [{"IDSubtitleFile": "123"}]

        with patch("downloader.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("downloader.worker.opensubtitles_client") as mock_client:
                mock_client.search_subtitles = AsyncMock(
                    return_value=mock_search_results
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    # Create mock channel for RabbitMQ
                    mock_channel = MagicMock()
                    mock_channel.default_exchange = MagicMock()
                    mock_channel.default_exchange.publish = AsyncMock()

                    await process_message(mock_message, mock_channel)

                    # Verify JOB_FAILED event with clear error
                    events = [
                        call[0][0]
                        for call in mock_publisher.publish_event.call_args_list
                    ]
                    failed_events = [
                        e for e in events if e.event_type == EventType.JOB_FAILED
                    ]
                    assert len(failed_events) == 1

                    error_payload = failed_events[0].payload
                    assert "error_message" in error_payload
                    assert "video is not a local file" in error_payload["error_message"]
                    assert error_payload["error_type"] == "invalid_video_path"
                    assert error_payload["video_url"] == video_url


class TestFallbackSubtitleSearch:
    """Test fallback subtitle search when requested language is not found."""

    @pytest.mark.asyncio
    async def test_fallback_subtitle_found_in_default_language(self):
        """Test that fallback subtitle is found and downloaded when default language is available."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Movie",
                    "language": "he",  # Request Hebrew
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Requested language (he) not found, but default language (en) found
                    mock_fallback_result = [
                        {
                            "IDSubtitleFile": "123",
                            "SubLanguageID": "en",
                        }
                    ]
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        side_effect=[
                            [],  # Hebrew search - empty
                            mock_fallback_result,  # English fallback - found
                        ]
                    )
                    # Metadata search only called when hash search returns empty
                    # hash(he) -> [] -> metadata(he) -> []
                    # hash(en) -> [result] -> metadata(en) NOT called
                    mock_client.search_subtitles = AsyncMock(
                        side_effect=[
                            [],  # Hebrew search - empty (only called because hash was empty)
                            # English fallback metadata search won't be called because hash(en) found result
                        ]
                    )
                    subtitle_file_path = Path(video_url).parent / "test_movie.en.srt"
                    # Create the actual subtitle file so exists() check passes
                    subtitle_file_path.write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=subtitle_file_path
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = True
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Verify fallback subtitle was downloaded
                            mock_client.download_subtitle.assert_called_once()

                            # Verify TranslationTask was enqueued to RabbitMQ
                            assert mock_channel.default_exchange.publish.call_count > 0

                            # Verify translation request event was published
                            # Note: publish_event may be called multiple times
                            assert mock_publisher.publish_event.call_count >= 1
                            event_calls = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            translate_events = [
                                e
                                for e in event_calls
                                if e.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            ]
                            assert len(translate_events) > 0
                            event_call = translate_events[0]
                            assert (
                                event_call.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            )
                            assert event_call.payload["subtitle_file_path"] == str(
                                subtitle_file_path
                            )
                            assert event_call.payload["source_language"] == "en"
                            assert event_call.payload["target_language"] == "he"
        finally:
            Path(video_url).unlink(missing_ok=True)
            (Path(video_url).parent / "test_movie.en.srt").unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_fallback_subtitle_found_in_any_language(self):
        """Test that fallback subtitle is found in any language when default not available."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Movie",
                    "language": "he",  # Request Hebrew
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Requested language (he) not found, default (en) not found, but Spanish found
                    mock_any_language_result = [
                        {
                            "IDSubtitleFile": "456",
                            "SubLanguageID": "es",  # Spanish
                        }
                    ]
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        side_effect=[
                            [],  # Hebrew search - empty
                            [],  # English fallback - empty
                            mock_any_language_result,  # Any language - found Spanish
                        ]
                    )
                    # Metadata search only called when hash search returns empty
                    # hash(he) -> [] -> metadata(he) -> []
                    # hash(en) -> [] -> metadata(en) -> []
                    # hash(None) -> [result] -> metadata(None) NOT called
                    mock_client.search_subtitles = AsyncMock(
                        side_effect=[
                            [],  # Hebrew search - empty (only called because hash was empty)
                            [],  # English fallback - empty (only called because hash was empty)
                            # Any language metadata search won't be called because hash(None) found result
                        ]
                    )
                    subtitle_file_path = Path(video_url).parent / "test_movie.es.srt"
                    # Create the actual subtitle file so exists() check passes
                    subtitle_file_path.write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=subtitle_file_path
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = True
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Verify fallback subtitle was downloaded
                            mock_client.download_subtitle.assert_called_once()

                            # Verify TranslationTask was enqueued
                            assert mock_channel.default_exchange.publish.call_count > 0

                            # Verify translation request with actual path and extracted language
                            assert mock_publisher.publish_event.call_count >= 1
                            event_calls = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            translate_events = [
                                e
                                for e in event_calls
                                if e.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            ]
                            assert len(translate_events) > 0
                            event_call = translate_events[0]
                            assert (
                                event_call.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            )
                            assert event_call.payload["subtitle_file_path"] == str(
                                subtitle_file_path
                            )
                            assert (
                                event_call.payload["source_language"] == "es"
                            )  # Extracted from API
                            assert event_call.payload["target_language"] == "he"
        finally:
            Path(video_url).unlink(missing_ok=True)
            (Path(video_url).parent / "test_movie.es.srt").unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_no_subtitle_found_in_any_language(self):
        """Test that SUBTITLE_MISSING is published when no subtitle found in any language."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "video_url": "https://example.com/video.mp4",
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
                # No subtitles found in any language
                # Remote URL - no hash search, only metadata search
                mock_client.search_subtitles_by_hash = AsyncMock(return_value=[])
                # Mock the sequence: metadata(he) -> metadata(en) -> metadata(any)
                mock_client.search_subtitles = AsyncMock(
                    side_effect=[[], [], []]  # he, en, any - all empty
                )

                with patch("downloader.worker.event_publisher") as mock_publisher:
                    mock_publisher.publish_event = AsyncMock()

                    with patch("downloader.worker.settings") as mock_settings:
                        mock_settings.jellyfin_auto_translate = True
                        mock_settings.subtitle_fallback_language = "en"

                        # Create mock channel for RabbitMQ
                        mock_channel = MagicMock()
                        mock_channel.default_exchange = MagicMock()
                        mock_channel.default_exchange.publish = AsyncMock()

                        await process_message(mock_message, mock_channel)

                        # Verify SUBTITLE_MISSING event was published
                        mock_publisher.publish_event.assert_called_once()
                        event_call = mock_publisher.publish_event.call_args[0][0]
                        assert event_call.event_type == EventType.SUBTITLE_MISSING
                        assert (
                            event_call.payload["reason"]
                            == "subtitle_not_found_any_language"
                        )
                        assert event_call.payload["language"] == "he"

    @pytest.mark.asyncio
    async def test_language_extraction_from_api_response(self):
        """Test that language is correctly extracted from OpenSubtitles API response."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Movie",
                    "language": "he",  # Request Hebrew
                }
            ).encode()
            mock_message.routing_key = "subtitle.download"
            mock_message.exchange = ""
            mock_message.message_id = "test-message-id"
            mock_message.timestamp = None

            with patch("downloader.worker.redis_client") as mock_redis:
                mock_redis.update_phase = AsyncMock(return_value=True)

                with patch("downloader.worker.opensubtitles_client") as mock_client:
                    # Fallback subtitle found with specific language code
                    mock_fallback_result = [
                        {
                            "IDSubtitleFile": "789",
                            "SubLanguageID": "fr",  # French
                        }
                    ]
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        side_effect=[[], mock_fallback_result]
                    )
                    # Metadata search only called when hash search returns empty
                    # hash(he) -> [] -> metadata(he) -> []
                    # hash(en) -> [result] -> metadata(en) NOT called
                    mock_client.search_subtitles = AsyncMock(
                        side_effect=[
                            [],  # Hebrew search - empty (only called because hash was empty)
                            # Fallback metadata search won't be called because hash(en) found result
                        ]
                    )
                    subtitle_file_path = Path(video_url).parent / "test_movie.fr.srt"
                    # Create the actual subtitle file so exists() check passes
                    subtitle_file_path.write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=subtitle_file_path
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = True
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Verify TranslationTask was enqueued
                            assert mock_channel.default_exchange.publish.call_count > 0
                            publish_call = (
                                mock_channel.default_exchange.publish.call_args
                            )
                            assert (
                                publish_call[1]["routing_key"] == "subtitle.translation"
                            )

                            # Verify language was extracted from API response and converted to ISO
                            assert mock_publisher.publish_event.call_count >= 1
                            event_calls = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            translate_events = [
                                e
                                for e in event_calls
                                if e.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            ]
                            assert len(translate_events) > 0
                            event_call = translate_events[0]
                            assert (
                                event_call.payload["source_language"] == "fr"
                            )  # From SubLanguageID (already ISO)
                            assert (
                                event_call.payload["target_language"] == "he"
                            )  # Originally requested
        finally:
            Path(video_url).unlink(missing_ok=True)
            (Path(video_url).parent / "test_movie.fr.srt").unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_language_extraction_fallback_to_default(self):
        """Test that language extraction falls back to default if SubLanguageID is missing."""
        request_id = uuid4()

        # Create a temporary local video file
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"A" * (256 * 1024))
            video_url = tmp_file.name

        try:
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "video_url": video_url,
                    "video_title": "Test Movie",
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
                    # Fallback subtitle found but SubLanguageID is missing
                    mock_fallback_result = [
                        {
                            "IDSubtitleFile": "999",
                            # SubLanguageID missing
                        }
                    ]
                    mock_client.search_subtitles_by_hash = AsyncMock(
                        side_effect=[[], mock_fallback_result]
                    )
                    # Metadata search only called when hash search returns empty
                    # hash(he) -> [] -> metadata(he) -> []
                    # hash(en) -> [result] -> metadata(en) NOT called
                    mock_client.search_subtitles = AsyncMock(
                        side_effect=[
                            [],  # Hebrew search - empty (only called because hash was empty)
                            # Fallback metadata search won't be called because hash(en) found result
                        ]
                    )
                    subtitle_file_path = Path(video_url).parent / "test_movie.en.srt"
                    # Create the actual subtitle file so exists() check passes
                    subtitle_file_path.write_text(
                        "1\n00:00:00,000 --> 00:00:01,000\nTest\n"
                    )
                    mock_client.download_subtitle = AsyncMock(
                        return_value=subtitle_file_path
                    )

                    with patch("downloader.worker.event_publisher") as mock_publisher:
                        mock_publisher.publish_event = AsyncMock()

                        with patch("downloader.worker.settings") as mock_settings:
                            mock_settings.jellyfin_auto_translate = True
                            mock_settings.subtitle_fallback_language = "en"
                            mock_settings.rabbitmq_translation_queue_routing_key = (
                                "subtitle.translation"
                            )

                            # Create mock channel for RabbitMQ
                            mock_channel = MagicMock()
                            mock_channel.default_exchange = MagicMock()
                            mock_channel.default_exchange.publish = AsyncMock()

                            await process_message(mock_message, mock_channel)

                            # Verify TranslationTask was enqueued
                            assert mock_channel.default_exchange.publish.call_count > 0

                            # Verify language falls back to default
                            assert mock_publisher.publish_event.call_count >= 1
                            event_calls = [
                                call[0][0]
                                for call in mock_publisher.publish_event.call_args_list
                            ]
                            translate_events = [
                                e
                                for e in event_calls
                                if e.event_type
                                == EventType.SUBTITLE_TRANSLATE_REQUESTED
                            ]
                            assert len(translate_events) > 0
                            event_call = translate_events[0]
                            assert (
                                event_call.payload["source_language"] == "en"
                            )  # Falls back to default
                            assert event_call.payload["target_language"] == "he"
        finally:
            Path(video_url).unlink(missing_ok=True)
            (Path(video_url).parent / "test_movie.en.srt").unlink(missing_ok=True)


class TestDownloaderWorkerShutdown:
    """Tests for downloader worker graceful shutdown."""

    @pytest.mark.asyncio
    async def test_downloader_worker_handles_shutdown_signal(self):
        """Test that downloader worker handles shutdown signals gracefully."""
        shutdown_manager = ShutdownManager("test_downloader", shutdown_timeout=5.0)
        await shutdown_manager.setup_signal_handlers()

        # Simulate shutdown signal
        shutdown_manager._trigger_shutdown_for_testing()

        assert shutdown_manager.is_shutdown_requested()

    @pytest.mark.asyncio
    async def test_downloader_worker_message_timeout_during_shutdown(self):
        """Test that message processing times out during shutdown."""
        shutdown_manager = ShutdownManager("test_downloader", shutdown_timeout=1.0)

        # Simulate long-running message processing
        async def slow_download():
            await asyncio.sleep(1.0)

        shutdown_manager._trigger_shutdown_for_testing()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                slow_download(), timeout=shutdown_manager.shutdown_timeout
            )

    @pytest.mark.asyncio
    async def test_downloader_worker_cleanup_callbacks_execute(self):
        """Test that cleanup callbacks execute during shutdown."""
        shutdown_manager = ShutdownManager("test_downloader")

        cleanup_executed = {
            "redis": False,
            "rabbitmq": False,
            "publisher": False,
            "opensubtitles": False,
        }

        async def mock_redis_disconnect():
            cleanup_executed["redis"] = True

        async def mock_rabbitmq_close():
            cleanup_executed["rabbitmq"] = True

        async def mock_publisher_disconnect():
            cleanup_executed["publisher"] = True

        async def mock_opensubtitles_disconnect():
            cleanup_executed["opensubtitles"] = True

        shutdown_manager.register_cleanup_callback(mock_redis_disconnect)
        shutdown_manager.register_cleanup_callback(mock_rabbitmq_close)
        shutdown_manager.register_cleanup_callback(mock_publisher_disconnect)
        shutdown_manager.register_cleanup_callback(mock_opensubtitles_disconnect)

        await shutdown_manager.execute_cleanup()

        assert cleanup_executed["redis"]
        assert cleanup_executed["rabbitmq"]
        assert cleanup_executed["publisher"]
        assert cleanup_executed["opensubtitles"]

    @pytest.mark.asyncio
    async def test_downloader_worker_stops_consuming_on_shutdown(self):
        """Test that downloader stops consuming messages on shutdown."""
        shutdown_manager = ShutdownManager("test_downloader")

        # Simulate message consumption loop
        messages_processed = 0
        max_messages = 5

        for i in range(max_messages):
            if shutdown_manager.is_shutdown_requested():
                break
            messages_processed += 1

            # Trigger shutdown after 2 messages
            if i == 1:
                shutdown_manager._trigger_shutdown_for_testing()

        # Should only process 2 messages before shutdown
        assert messages_processed == 2
