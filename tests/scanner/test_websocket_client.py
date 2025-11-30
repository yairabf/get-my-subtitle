"""Unit tests for Jellyfin WebSocket client."""

import asyncio
import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from websockets.exceptions import ConnectionClosed, WebSocketException

from common.config import settings
from common.schemas import SubtitleStatus
from scanner.websocket_client import JellyfinWebSocketClient


@pytest.fixture
def websocket_client():
    """Create a WebSocket client instance for testing."""
    return JellyfinWebSocketClient()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("scanner.websocket_client.settings") as mock_settings:
        mock_settings.jellyfin_url = "http://jellyfin.local:8096"
        mock_settings.jellyfin_api_key = "test_api_key"
        mock_settings.jellyfin_websocket_enabled = True
        mock_settings.jellyfin_websocket_reconnect_delay = 2.0
        mock_settings.jellyfin_websocket_max_reconnect_delay = 300.0
        mock_settings.subtitle_desired_language = "en"
        mock_settings.subtitle_fallback_language = "en"
        mock_settings.jellyfin_auto_translate = True
        yield mock_settings


class TestWebSocketClientConfiguration:
    """Test WebSocket client configuration and URL building."""

    def test_is_configured_when_settings_present(self, websocket_client, mock_settings):
        """Test that client is configured when all settings are present."""
        assert websocket_client._is_configured() is True

    def test_is_configured_when_url_missing(self, websocket_client, mock_settings):
        """Test that client is not configured when URL is missing."""
        mock_settings.jellyfin_url = None
        assert websocket_client._is_configured() is False

    def test_is_configured_when_api_key_missing(self, websocket_client, mock_settings):
        """Test that client is not configured when API key is missing."""
        mock_settings.jellyfin_api_key = None
        assert websocket_client._is_configured() is False

    def test_is_configured_when_disabled(self, websocket_client, mock_settings):
        """Test that client is not configured when disabled."""
        mock_settings.jellyfin_websocket_enabled = False
        assert websocket_client._is_configured() is False

    def test_build_websocket_url_with_http(self, websocket_client, mock_settings):
        """Test WebSocket URL building with HTTP."""
        url = websocket_client._build_websocket_url()
        assert url == "ws://jellyfin.local:8096/socket?api_key=test_api_key"

    def test_build_websocket_url_with_https(self, websocket_client, mock_settings):
        """Test WebSocket URL building with HTTPS."""
        mock_settings.jellyfin_url = "https://jellyfin.secure:8096"
        url = websocket_client._build_websocket_url()
        assert url == "wss://jellyfin.secure:8096/socket?api_key=test_api_key"


class TestReconnectionLogic:
    """Test reconnection logic and exponential backoff."""

    def test_calculate_reconnect_delay_first_attempt(
        self, websocket_client, mock_settings
    ):
        """Test reconnection delay calculation for first attempt."""
        websocket_client.reconnect_attempts = 0
        delay = websocket_client._calculate_reconnect_delay()
        assert delay == 2.0  # base_delay * 2^0

    def test_calculate_reconnect_delay_second_attempt(
        self, websocket_client, mock_settings
    ):
        """Test reconnection delay calculation for second attempt."""
        websocket_client.reconnect_attempts = 1
        delay = websocket_client._calculate_reconnect_delay()
        assert delay == 4.0  # base_delay * 2^1

    def test_calculate_reconnect_delay_third_attempt(
        self, websocket_client, mock_settings
    ):
        """Test reconnection delay calculation for third attempt."""
        websocket_client.reconnect_attempts = 2
        delay = websocket_client._calculate_reconnect_delay()
        assert delay == 8.0  # base_delay * 2^2

    def test_calculate_reconnect_delay_max_cap(self, websocket_client, mock_settings):
        """Test that reconnection delay is capped at maximum."""
        websocket_client.reconnect_attempts = 10
        delay = websocket_client._calculate_reconnect_delay()
        assert delay == 300.0  # max_delay


class TestConnectionManagement:
    """Test WebSocket connection and disconnection."""

    @pytest.mark.asyncio
    async def test_connect_when_not_configured(self, websocket_client, mock_settings):
        """Test that connect does nothing when not configured."""
        mock_settings.jellyfin_url = None

        await websocket_client.connect()

        assert websocket_client.running is False
        assert websocket_client.websocket is None

    @pytest.mark.asyncio
    async def test_connect_when_already_running(self, websocket_client, mock_settings):
        """Test that connect warns when already running."""
        websocket_client.running = True

        with patch("websockets.connect") as mock_connect:
            await websocket_client.connect()
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_success(self, websocket_client, mock_settings):
        """Test successful WebSocket connection."""
        mock_ws = AsyncMock()
        mock_ws.open = True

        with patch(
            "websockets.connect", new=AsyncMock(return_value=mock_ws)
        ) as mock_connect:
            with patch.object(
                websocket_client, "_message_loop", return_value=asyncio.sleep(0)
            ):
                await websocket_client.connect()

                mock_connect.assert_called_once()
                assert websocket_client.running is True
                assert websocket_client.websocket == mock_ws
                assert websocket_client.reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_connect_failure_schedules_reconnect(
        self, websocket_client, mock_settings
    ):
        """Test that connection failure schedules reconnection."""
        with patch(
            "websockets.connect", side_effect=WebSocketException("Connection failed")
        ):
            with patch.object(websocket_client, "_schedule_reconnect") as mock_schedule:
                with pytest.raises(WebSocketException):
                    await websocket_client.connect()

                mock_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_running(self, websocket_client):
        """Test that disconnect does nothing when not running."""
        await websocket_client.disconnect()
        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_disconnect_success(self, websocket_client):
        """Test successful disconnection."""
        mock_ws = AsyncMock()
        websocket_client.websocket = mock_ws
        websocket_client.running = True
        websocket_client.message_handler_task = AsyncMock()
        websocket_client.reconnect_task = AsyncMock()

        await websocket_client.disconnect()

        assert websocket_client.running is False
        mock_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_connected_when_running(self, websocket_client):
        """Test is_connected returns True when connected."""
        mock_ws = MagicMock()
        mock_ws.open = True
        websocket_client.websocket = mock_ws
        websocket_client.running = True

        assert websocket_client.is_connected() is True

    @pytest.mark.asyncio
    async def test_is_connected_when_not_running(self, websocket_client):
        """Test is_connected returns False when not running."""
        websocket_client.running = False

        assert websocket_client.is_connected() is False


class TestMessageHandling:
    """Test WebSocket message parsing and routing."""

    @pytest.mark.asyncio
    async def test_handle_message_library_changed(
        self, websocket_client, mock_settings
    ):
        """Test handling LibraryChanged message."""
        message = json.dumps(
            {
                "MessageType": "LibraryChanged",
                "Data": {"ItemsAdded": ["item1", "item2"]},
            }
        )

        with patch.object(websocket_client, "_handle_library_changed") as mock_handler:
            await websocket_client._handle_message(message)
            mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_keep_alive(self, websocket_client, mock_settings):
        """Test handling KeepAlive message."""
        message = json.dumps({"MessageType": "KeepAlive"})

        # Should not raise any errors
        await websocket_client._handle_message(message)

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self, websocket_client):
        """Test handling invalid JSON message."""
        message = "invalid json"

        # Should not raise any errors
        await websocket_client._handle_message(message)

    @pytest.mark.asyncio
    async def test_handle_message_no_message_type(self, websocket_client):
        """Test handling message without MessageType."""
        message = json.dumps({"Data": "some data"})

        # Should not raise any errors
        await websocket_client._handle_message(message)

    @pytest.mark.asyncio
    async def test_handle_library_changed_with_items(
        self, websocket_client, mock_settings
    ):
        """Test processing library change with added items."""
        data = {
            "MessageType": "LibraryChanged",
            "Data": {"ItemsAdded": ["item1", "item2"]},
        }

        with patch.object(websocket_client, "_fetch_and_process_item") as mock_fetch:
            await websocket_client._handle_library_changed(data)

            assert mock_fetch.call_count == 2
            mock_fetch.assert_any_call("item1")
            mock_fetch.assert_any_call("item2")

    @pytest.mark.asyncio
    async def test_handle_library_changed_no_items(
        self, websocket_client, mock_settings
    ):
        """Test processing library change with no items."""
        data = {"MessageType": "LibraryChanged", "Data": {"ItemsAdded": []}}

        with patch.object(websocket_client, "_fetch_and_process_item") as mock_fetch:
            await websocket_client._handle_library_changed(data)

            mock_fetch.assert_not_called()


class TestItemProcessing:
    """Test fetching and processing media items."""

    @pytest.mark.asyncio
    async def test_fetch_and_process_item_movie(self, websocket_client, mock_settings):
        """Test fetching and processing a movie item."""
        item_data = {
            "Type": "Movie",
            "Name": "Test Movie",
            "Path": "/media/test.mp4",
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=item_data)

        # Create proper async context manager mock
        mock_get = MagicMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get = MagicMock(return_value=mock_get)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session_instance):
            with patch.object(websocket_client, "_process_media_item") as mock_process:
                await websocket_client._fetch_and_process_item("item123")

                mock_process.assert_called_once_with(
                    "Test Movie", "/media/test.mp4", "item123"
                )

    @pytest.mark.asyncio
    async def test_fetch_and_process_item_episode(
        self, websocket_client, mock_settings
    ):
        """Test fetching and processing an episode item."""
        item_data = {
            "Type": "Episode",
            "Name": "Test Episode",
            "Path": "/media/episode.mp4",
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=item_data)

        # Create proper async context manager mock
        mock_get = MagicMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get = MagicMock(return_value=mock_get)
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session_instance):
            with patch.object(websocket_client, "_process_media_item") as mock_process:
                await websocket_client._fetch_and_process_item("item123")

                mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_and_process_item_non_video(
        self, websocket_client, mock_settings
    ):
        """Test that non-video items are skipped."""
        item_data = {
            "Type": "Audio",
            "Name": "Test Audio",
            "Path": "/media/audio.mp3",
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=item_data)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_response
            )

            with patch.object(websocket_client, "_process_media_item") as mock_process:
                await websocket_client._fetch_and_process_item("item123")

                mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_and_process_item_no_path(
        self, websocket_client, mock_settings
    ):
        """Test that items without path are skipped."""
        item_data = {"Type": "Movie", "Name": "Test Movie", "Path": None}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=item_data)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_response
            )

            with patch.object(websocket_client, "_process_media_item") as mock_process:
                await websocket_client._fetch_and_process_item("item123")

                mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_and_process_item_http_error(
        self, websocket_client, mock_settings
    ):
        """Test handling HTTP error when fetching item."""
        mock_response = AsyncMock()
        mock_response.status = 404

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_response
            )

            with patch.object(websocket_client, "_process_media_item") as mock_process:
                await websocket_client._fetch_and_process_item("item123")

                mock_process.assert_not_called()


class TestMediaProcessing:
    """Test subtitle job creation for media items."""

    @pytest.mark.asyncio
    async def test_process_media_item_with_translation(
        self, websocket_client, mock_settings
    ):
        """Test processing media item with translation enabled."""
        with patch("scanner.websocket_client.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()
            mock_redis.update_phase = AsyncMock()
            with patch("scanner.websocket_client.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()
                with patch(
                    "scanner.websocket_client.orchestrator"
                ) as mock_orchestrator:
                    mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                        return_value=True
                    )

                    await websocket_client._process_media_item(
                        "Test Movie", "/media/test.mp4", "item123"
                    )

                    mock_redis.save_job.assert_called_once()
                    mock_publisher.publish_event.assert_called_once()
                    mock_orchestrator.enqueue_download_with_translation.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_media_item_without_translation(
        self, websocket_client, mock_settings
    ):
        """Test processing media item without translation."""
        mock_settings.jellyfin_auto_translate = False

        with patch("scanner.websocket_client.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()
            mock_redis.update_phase = AsyncMock()
            with patch("scanner.websocket_client.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()
                with patch(
                    "scanner.websocket_client.orchestrator"
                ) as mock_orchestrator:
                    mock_orchestrator.enqueue_download_task = AsyncMock(
                        return_value=True
                    )

                    await websocket_client._process_media_item(
                        "Test Movie", "/media/test.mp4", "item123"
                    )

                    mock_orchestrator.enqueue_download_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_media_item_enqueue_failure(
        self, websocket_client, mock_settings
    ):
        """Test handling enqueue failure."""
        with patch("scanner.websocket_client.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()
            mock_redis.update_phase = AsyncMock()
            with patch("scanner.websocket_client.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()
                with patch(
                    "scanner.websocket_client.orchestrator"
                ) as mock_orchestrator:
                    mock_orchestrator.enqueue_download_with_translation = AsyncMock(
                        return_value=False
                    )

                    await websocket_client._process_media_item(
                        "Test Movie", "/media/test.mp4", "item123"
                    )

                    # Should update job status to FAILED
                    mock_redis.update_phase.assert_called_once()
