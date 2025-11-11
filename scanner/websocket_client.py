"""WebSocket client for real-time Jellyfin library updates."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException

from common.config import settings
from common.event_publisher import event_publisher
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import (
    EventType,
    SubtitleEvent,
    SubtitleRequest,
    SubtitleResponse,
    SubtitleStatus,
)
from common.utils import DateTimeUtils

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger


class JellyfinWebSocketClient:
    """WebSocket client for receiving real-time Jellyfin library updates."""

    def __init__(self):
        """Initialize the WebSocket client."""
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.running = False
        self.reconnect_attempts = 0
        self.message_handler_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None

    def _is_configured(self) -> bool:
        """
        Check if Jellyfin WebSocket is properly configured.

        Returns:
            True if configured, False otherwise
        """
        return bool(
            settings.jellyfin_url
            and settings.jellyfin_api_key
            and settings.jellyfin_websocket_enabled
        )

    def _build_websocket_url(self) -> str:
        """
        Build the Jellyfin WebSocket URL with authentication.

        Returns:
            WebSocket URL with API key parameter
        """
        # Parse the base URL
        parsed = urlparse(settings.jellyfin_url)

        # Convert http/https to ws/wss
        scheme = "wss" if parsed.scheme == "https" else "ws"

        # Build WebSocket URL
        base_url = f"{scheme}://{parsed.netloc}"
        ws_url = urljoin(base_url, "/socket")

        # Add API key as query parameter
        ws_url = f"{ws_url}?api_key={settings.jellyfin_api_key}"

        return ws_url

    def _calculate_reconnect_delay(self) -> float:
        """
        Calculate exponential backoff delay for reconnection.

        Returns:
            Delay in seconds before next reconnection attempt
        """
        base_delay = settings.jellyfin_websocket_reconnect_delay
        max_delay = settings.jellyfin_websocket_max_reconnect_delay

        # Exponential backoff: delay = base_delay * (2 ^ attempts)
        delay = base_delay * (2**self.reconnect_attempts)

        # Cap at maximum delay
        return min(delay, max_delay)

    async def connect(self) -> None:
        """
        Establish WebSocket connection to Jellyfin server.

        Raises:
            ValueError: If Jellyfin is not properly configured
            WebSocketException: If connection fails
        """
        if not self._is_configured():
            logger.warning(
                "Jellyfin WebSocket is not configured or disabled. "
                "Set JELLYFIN_URL, JELLYFIN_API_KEY, and JELLYFIN_WEBSOCKET_ENABLED=true"
            )
            return

        if self.running:
            logger.warning("WebSocket client is already running")
            return

        try:
            ws_url = self._build_websocket_url()
            logger.info(f"🔌 Connecting to Jellyfin WebSocket...")

            # Connect to WebSocket
            self.websocket = await websockets.connect(
                ws_url,
                ping_interval=20,  # Send ping every 20 seconds
                ping_timeout=10,  # Wait 10 seconds for pong
            )

            self.running = True
            self.reconnect_attempts = 0

            logger.info("✅ Connected to Jellyfin WebSocket")

            # Start message handler
            self.message_handler_task = asyncio.create_task(self._message_loop())

        except WebSocketException as e:
            logger.error(f"Failed to connect to Jellyfin WebSocket: {e}")
            # Schedule reconnection
            await self._schedule_reconnect()
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error connecting to Jellyfin WebSocket: {e}",
                exc_info=True,
            )
            raise

    async def disconnect(self) -> None:
        """Gracefully disconnect from Jellyfin WebSocket."""
        if not self.running:
            return

        logger.info("🔌 Disconnecting from Jellyfin WebSocket...")

        self.running = False

        # Cancel message handler task
        if self.message_handler_task and not self.message_handler_task.done():
            self.message_handler_task.cancel()
            try:
                await self.message_handler_task
            except asyncio.CancelledError:
                pass

        # Cancel reconnect task
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")

        logger.info("✅ Disconnected from Jellyfin WebSocket")

    async def _message_loop(self) -> None:
        """
        Main message processing loop.

        Continuously receives and processes messages from Jellyfin.
        """
        try:
            while self.running and self.websocket:
                try:
                    # Receive message from WebSocket
                    message = await self.websocket.recv()

                    # Parse and handle message
                    await self._handle_message(message)

                except ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.debug("Message loop cancelled")
        finally:
            # Connection lost, schedule reconnection
            if self.running:
                logger.info("Connection lost, scheduling reconnection...")
                await self._schedule_reconnect()

    async def _handle_message(self, message: str) -> None:
        """
        Parse and route incoming WebSocket messages.

        Args:
            message: Raw message string from WebSocket
        """
        try:
            # Parse JSON message
            data = json.loads(message)

            message_type = data.get("MessageType")

            if not message_type:
                logger.debug(f"Received message without MessageType: {data}")
                return

            logger.debug(f"Received Jellyfin message: {message_type}")

            # Route message based on type
            if message_type == "LibraryChanged":
                await self._handle_library_changed(data)
            elif message_type == "KeepAlive":
                # Keep-alive messages are handled automatically by ping/pong
                pass
            else:
                logger.debug(f"Unhandled message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message as JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    async def _handle_library_changed(self, data: Dict[str, Any]) -> None:
        """
        Process library change events from Jellyfin.

        Args:
            data: Message data containing library change information
        """
        try:
            # Extract data from message
            message_data = data.get("Data", {})

            # Get list of added items
            items_added = message_data.get("ItemsAdded", [])

            if not items_added:
                logger.debug("LibraryChanged event with no items added")
                return

            logger.info(f"📚 Library changed: {len(items_added)} items added")

            # Process each added item
            for item_id in items_added:
                await self._fetch_and_process_item(item_id)

        except Exception as e:
            logger.error(f"Error handling library change: {e}", exc_info=True)

    async def _fetch_and_process_item(self, item_id: str) -> None:
        """
        Fetch item details from Jellyfin API and process if it's a video.

        Args:
            item_id: Jellyfin item ID
        """
        try:
            # Import aiohttp for API calls
            import aiohttp

            # Build API URL
            api_url = urljoin(settings.jellyfin_url, f"/Items/{item_id}")

            headers = {"X-Emby-Token": settings.jellyfin_api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Failed to fetch item {item_id}: HTTP {response.status}"
                        )
                        return

                    item_data = await response.json()

            # Check if item is a video (Movie or Episode)
            item_type = item_data.get("Type")

            if item_type not in ["Movie", "Episode"]:
                logger.debug(f"Skipping non-video item: {item_type}")
                return

            # Extract item information
            item_name = item_data.get("Name", "Unknown")
            item_path = item_data.get("Path")

            if not item_path:
                logger.warning(f"No path found for item {item_id}: {item_name}")
                return

            logger.info(f"🎬 Processing video item: {item_name} ({item_type})")

            # Process the media item
            await self._process_media_item(item_name, item_path, item_id)

        except Exception as e:
            logger.error(f"Error fetching item {item_id}: {e}", exc_info=True)

    async def _process_media_item(
        self, item_name: str, item_path: str, item_id: str
    ) -> None:
        """
        Create subtitle job for a media item.

        Args:
            item_name: Name/title of the media item
            item_path: File path to the media item
            item_id: Jellyfin item ID
        """
        try:
            # Create subtitle request
            subtitle_request = SubtitleRequest(
                video_url=item_path,
                video_title=item_name,
                language=settings.jellyfin_default_source_language,
                target_language=settings.jellyfin_default_target_language,
                preferred_sources=["opensubtitles"],
            )

            # Create subtitle response/job
            subtitle_response = SubtitleResponse(
                video_url=subtitle_request.video_url,
                video_title=subtitle_request.video_title,
                language=subtitle_request.language,
                target_language=subtitle_request.target_language,
                status=SubtitleStatus.PENDING,
            )

            # Store job in Redis
            await redis_client.save_job(subtitle_response)

            logger.info(f"✅ Created job {subtitle_response.id} for {item_name}")

            # Publish MEDIA_FILE_DETECTED event (for observability)
            media_detected_event = SubtitleEvent(
                event_type=EventType.MEDIA_FILE_DETECTED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="scanner",
                payload={
                    "file_path": item_path,
                    "video_title": item_name,
                    "video_url": item_path,
                    "language": subtitle_request.language,
                    "target_language": subtitle_request.target_language,
                    "source": "jellyfin_websocket",
                    "jellyfin_item_id": item_id,
                },
            )
            await event_publisher.publish_event(media_detected_event)

            # Publish SUBTITLE_REQUESTED event (for workflow triggering)
            subtitle_requested_event = SubtitleEvent(
                event_type=EventType.SUBTITLE_REQUESTED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="scanner",
                payload={
                    "video_url": subtitle_request.video_url,
                    "video_title": subtitle_request.video_title,
                    "language": subtitle_request.language,
                    "target_language": subtitle_request.target_language,
                    "preferred_sources": subtitle_request.preferred_sources,
                    "auto_translate": settings.jellyfin_auto_translate
                    and subtitle_request.target_language is not None,
                },
                )
            await event_publisher.publish_event(subtitle_requested_event)

                logger.info(
                f"✅ Published SUBTITLE_REQUESTED event for job {subtitle_response.id}"
                )

        except Exception as e:
            logger.error(f"Error processing media item {item_name}: {e}", exc_info=True)

    async def _schedule_reconnect(self) -> None:
        """Schedule automatic reconnection with exponential backoff."""
        if not self.running or not self._is_configured():
            return

        delay = self._calculate_reconnect_delay()
        self.reconnect_attempts += 1

        logger.info(
            f"🔄 Scheduling reconnection attempt {self.reconnect_attempts} "
            f"in {delay:.1f} seconds..."
        )

        # Schedule reconnection
        self.reconnect_task = asyncio.create_task(self._reconnect(delay))

    async def _reconnect(self, delay: float) -> None:
        """
        Wait and reconnect to WebSocket.

        Args:
            delay: Delay in seconds before reconnection
        """
        try:
            await asyncio.sleep(delay)

            if not self.running:
                return

            logger.info(
                f"🔄 Attempting to reconnect (attempt {self.reconnect_attempts})..."
            )

            # Close existing connection if any
            if self.websocket:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
                self.websocket = None

            # Attempt to reconnect
            await self.connect()

        except asyncio.CancelledError:
            logger.debug("Reconnect cancelled")
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            # Will be rescheduled by message loop

    def is_connected(self) -> bool:
        """
        Check if WebSocket is currently connected.

        Returns:
            True if connected, False otherwise
        """
        return self.running and self.websocket is not None and self.websocket.open
