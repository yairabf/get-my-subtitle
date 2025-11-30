"""Event publisher for RabbitMQ topic exchange."""

import asyncio
import logging
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

    async def connect(self, max_retries: int = 10, retry_delay: float = 3.0) -> None:
        """Establish connection to RabbitMQ and declare topic exchange with retry logic."""
        # If already connected, return early
        if self.connection and not self.connection.is_closed and self.exchange:
            print(f"[EVENT_PUBLISHER] Already connected, skipping")
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
                print(f"[EVENT_PUBLISHER] Connection established, getting channel...")
                self.channel = await self.connection.channel()

                # Declare topic exchange for event publishing
                print(f"[EVENT_PUBLISHER] Declaring exchange {self.exchange_name}...")
                self.exchange = await self.channel.declare_exchange(
                    self.exchange_name, ExchangeType.TOPIC, durable=True
                )

                print(
                    f"[EVENT_PUBLISHER] ✅ Successfully connected and declared exchange!"
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
                        f"Failed to connect to RabbitMQ for event publishing (attempt {attempt + 1}/{max_retries}): {e}. "
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
            await self.connection.close()
            logger.info("Disconnected event publisher from RabbitMQ")

    async def publish_event(self, event: SubtitleEvent) -> bool:
        """
        Publish event to topic exchange with routing key.

        Args:
            event: SubtitleEvent to publish

        Returns:
            True if successfully published, False otherwise
        """
        if not self.exchange or not self.channel:
            print(
                f"[EVENT_PUBLISHER] Mock mode: exchange={self.exchange is not None}, channel={self.channel is not None}, connection={self.connection is not None}"
            )
            logger.warning(
                f"Mock mode: Would publish event {event.event_type.value} for job {event.job_id} (exchange={self.exchange is not None}, channel={self.channel is not None})"
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
                f"[EVENT_PUBLISHER] ✅ Published event {event.event_type.value} for job {event.job_id} (routing_key: {routing_key})"
            )
            logger.info(
                f"Published event {event.event_type.value} for job {event.job_id} (routing_key: {routing_key})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to publish event {event.event_type.value} for job {event.job_id}: {e}"
            )
            return False


# Global event publisher instance
event_publisher = EventPublisher()
