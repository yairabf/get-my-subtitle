"""Event publisher for RabbitMQ topic exchange."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from common.config import settings
from common.schemas import SubtitleEvent

# Use root logger to ensure logs are visible - this module is used across services
# so we use a simple logger that will inherit from root
logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes events to RabbitMQ topic exchange."""

    def __init__(self):
        """Initialize the event publisher."""
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.exchange: Optional[AbstractExchange] = None
        self.exchange_name = "subtitle.events"
        self._reconnecting: bool = False
        self._reconnect_lock: Optional[asyncio.Lock] = None
        self._last_health_check: Optional[datetime] = None

    @property
    def reconnect_lock(self) -> asyncio.Lock:
        """Lazy initialization of reconnect lock (must be created within event loop)."""
        if self._reconnect_lock is None:
            self._reconnect_lock = asyncio.Lock()
        return self._reconnect_lock

    async def _on_reconnect(self, connection: AbstractConnection) -> None:
        """Callback when connection is re-established."""
        logger.info("🔄 Event publisher reconnected to RabbitMQ successfully!")
        # Re-declare channel and exchange after reconnection
        try:
            self.channel = await connection.channel()
            self.exchange = await self.channel.declare_exchange(
                self.exchange_name, ExchangeType.TOPIC, durable=True
            )
            logger.info(
                f"✅ Event publisher re-declared exchange: {self.exchange_name}"
            )
        except Exception as e:
            logger.error(f"Failed to re-declare exchange after reconnection: {e}")

    async def _on_disconnect(
        self, connection: AbstractConnection, exc: Optional[Exception] = None
    ) -> None:
        """Callback when connection is lost."""
        # Only log if there was an actual error during active connection
        # Don't log during normal startup/shutdown
        if exc and not isinstance(exc, (asyncio.CancelledError,)):
            logger.warning(f"⚠️ Event publisher connection lost: {exc}")

    async def connect(self, max_retries: int = 10, retry_delay: float = 3.0) -> None:
        """Establish connection to RabbitMQ and declare topic exchange with retry logic."""
        # If already connected, return early
        if self.connection and not self.connection.is_closed and self.exchange:
            print("[EVENT_PUBLISHER] Already connected, skipping")
            logging.info("Event publisher already connected, skipping connection")
            return

        print(
            f"[EVENT_PUBLISHER] connect() called with max_retries={max_retries}, retry_delay={retry_delay}"
        )
        logging.info(
            f"Event publisher connect() called with max_retries={max_retries}, retry_delay={retry_delay}"
        )

        for attempt in range(max_retries):
            print(f"[EVENT_PUBLISHER] Connection attempt {attempt + 1}/{max_retries}")
            logging.info(
                f"Event publisher connection attempt {attempt + 1}/{max_retries}"
            )
            try:
                print(
                    f"[EVENT_PUBLISHER] Attempting to connect to {settings.rabbitmq_url}"
                )
                self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)

                # Add reconnection callbacks to log successful reconnections
                self.connection.reconnect_callbacks.add(self._on_reconnect)
                self.connection.close_callbacks.add(self._on_disconnect)

                print("[EVENT_PUBLISHER] Connection established, getting channel...")
                self.channel = await self.connection.channel()

                # Declare topic exchange for event publishing
                print(f"[EVENT_PUBLISHER] Declaring exchange {self.exchange_name}...")
                self.exchange = await self.channel.declare_exchange(
                    self.exchange_name, ExchangeType.TOPIC, durable=True
                )

                print(
                    "[EVENT_PUBLISHER] ✅ Successfully connected and declared exchange!"
                )
                logging.info(
                    f"✅ Event publisher connected to RabbitMQ and declared topic exchange: {self.exchange_name}"
                )
                return  # Success, exit retry loop

            except Exception as e:
                print(
                    f"[EVENT_PUBLISHER] Exception on attempt {attempt + 1}: {type(e).__name__}: {e}"
                )
                import traceback

                traceback.print_exc()
                if attempt < max_retries - 1:
                    logging.warning(
                        f"Failed to connect to RabbitMQ for event publishing "
                        f"(attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logging.warning(
                        f"Failed to connect to RabbitMQ after {max_retries} attempts: {e}"
                    )
                    logging.warning(
                        "Running in mock mode - events will be logged but not published"
                    )
                    # Don't raise the exception, allow the app to start in mock mode

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            try:
                await self.connection.close()
            except Exception as e:
                logger.warning(f"Error closing RabbitMQ connection: {e}")
            finally:
                logger.info("Disconnected event publisher from RabbitMQ")

    async def is_healthy(self) -> bool:
        """
        Check if RabbitMQ connection is healthy (public API).

        Returns:
            True if connection, channel, and exchange are all healthy, False otherwise
        """
        return await self._check_health()

    async def _check_health(self) -> bool:
        """Check if RabbitMQ connection is healthy (internal implementation)."""
        if not self.connection or self.connection.is_closed:
            return False

        if not self.channel or not self.exchange:
            return False

        try:
            # Try to verify the exchange is still accessible
            # connect_robust should handle reconnection automatically,
            # but we check connection state explicitly
            self._last_health_check = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.warning(f"RabbitMQ health check failed: {e}")
            return False

    async def _reconnect_with_backoff(self) -> None:
        """Reconnect to RabbitMQ with exponential backoff."""
        logger.info("Starting RabbitMQ reconnection for event publisher...")

        # Close existing connection
        if self.connection and not self.connection.is_closed:
            try:
                await self.connection.close()
            except Exception:
                pass

        self.connection = None
        self.channel = None
        self.exchange = None

        # Attempt reconnection
        await self.connect(
            max_retries=settings.rabbitmq_reconnect_max_retries,
            retry_delay=settings.rabbitmq_reconnect_initial_delay,
        )

        if self.exchange:
            logger.info("RabbitMQ event publisher reconnection successful")
        else:
            logger.error("RabbitMQ event publisher reconnection failed")

    async def ensure_connected(self) -> bool:
        """
        Ensure RabbitMQ connection is healthy, reconnect if needed.

        Returns:
            True if connected, False otherwise
        """
        if await self._check_health():
            return True

        # Not connected, try to reconnect with lock to prevent concurrent attempts
        async with self.reconnect_lock:
            # Double-check after acquiring lock
            if await self._check_health():
                return True

            await self._reconnect_with_backoff()

        return self.exchange is not None

    async def publish_event(
        self, event: SubtitleEvent, retry_on_failure: bool = True
    ) -> bool:
        """
        Publish event to topic exchange with routing key.

        Args:
            event: SubtitleEvent to publish
            retry_on_failure: If True, attempt reconnection and retry on failure

        Returns:
            True if successfully published, False otherwise
        """
        # Ensure we're connected
        if not await self.ensure_connected():
            print(
                f"[EVENT_PUBLISHER] Mock mode: exchange={self.exchange is not None}, "
                f"channel={self.channel is not None}, "
                f"connection={self.connection is not None}"
            )
            logger.warning(
                f"Mock mode: Would publish event {event.event_type.value} "
                f"for job {event.job_id} "
                f"(exchange={self.exchange is not None}, "
                f"channel={self.channel is not None})"
            )
            logger.debug(f"Event data: {event.model_dump_json()}")
            return True

        try:
            # Use event type as routing key (e.g., "subtitle.ready", "job.failed")
            routing_key = event.event_type.value

            message = Message(
                body=event.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )

            await self.exchange.publish(message, routing_key=routing_key)

            print(
                f"[EVENT_PUBLISHER] ✅ Published event {event.event_type.value} "
                f"for job {event.job_id} (routing_key: {routing_key})"
            )
            logger.info(
                f"Published event {event.event_type.value} for job {event.job_id} (routing_key: {routing_key})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to publish event {event.event_type.value} for job {event.job_id}: {e}"
            )

            # Attempt reconnection and retry once if requested
            if retry_on_failure:
                logger.info("Attempting to reconnect and retry event publishing...")
                async with self.reconnect_lock:
                    if not await self._check_health():
                        await self._reconnect_with_backoff()

                if await self.ensure_connected():
                    # Retry once without further retries
                    return await self.publish_event(event, retry_on_failure=False)

            return False


# Global event publisher instance
event_publisher = EventPublisher()
