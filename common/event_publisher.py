"""Event publisher for RabbitMQ topic exchange."""

import logging
from typing import Optional

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from common.config import settings
from common.schemas import SubtitleEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes events to RabbitMQ topic exchange."""

    def __init__(self):
        """Initialize the event publisher."""
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.exchange: Optional[AbstractExchange] = None
        self.exchange_name = "subtitle.events"

    async def connect(self) -> None:
        """Establish connection to RabbitMQ and declare topic exchange."""
        try:
            self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            self.channel = await self.connection.channel()

            # Declare topic exchange for event publishing
            self.exchange = await self.channel.declare_exchange(
                self.exchange_name, ExchangeType.TOPIC, durable=True
            )

            logger.info(
                f"Connected to RabbitMQ and declared topic exchange: {self.exchange_name}"
            )
        except Exception as e:
            logger.warning(f"Failed to connect to RabbitMQ for event publishing: {e}")
            logger.warning(
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
            logger.warning(
                f"Mock mode: Would publish event {event.event_type.value} for job {event.job_id}"
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
