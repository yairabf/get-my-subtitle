"""Event consumer for processing SUBTITLE_REQUESTED events from Scanner service."""

import asyncio
import logging
from typing import Optional

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
)

from common.config import settings
from common.duplicate_prevention import DuplicatePreventionService
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleRequest, SubtitleStatus
from common.utils import ValidationUtils
from manager.orchestrator import orchestrator

logger = logging.getLogger(__name__)

# Initialize duplicate prevention service
duplicate_prevention = DuplicatePreventionService(redis_client)


class SubtitleEventConsumer:
    """Consumes SUBTITLE_REQUESTED events from RabbitMQ topic exchange."""

    def __init__(self):
        """Initialize the event consumer."""
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.exchange: Optional[AbstractExchange] = None
        self.queue: Optional[AbstractQueue] = None
        self.exchange_name = "subtitle.events"
        self.queue_name = "manager.subtitle.requests"
        self.routing_key = "subtitle.requested"
        self.is_consuming = False

    async def connect(self) -> None:
        """Establish connection to RabbitMQ and bind queue to topic exchange."""
        try:
            self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            self.channel = await self.connection.channel()

            # Declare topic exchange (should already exist from event_publisher)
            self.exchange = await self.channel.declare_exchange(
                self.exchange_name, ExchangeType.TOPIC, durable=True
            )

            # Declare durable queue for this consumer
            self.queue = await self.channel.declare_queue(self.queue_name, durable=True)

            # Bind queue to exchange with routing key for SUBTITLE_REQUESTED
            await self.queue.bind(exchange=self.exchange, routing_key=self.routing_key)

            logger.info(
                f"Connected to RabbitMQ - Queue '{self.queue_name}' bound to "
                f"exchange '{self.exchange_name}' with routing key '{self.routing_key}'"
            )

        except Exception as e:
            logger.warning(f"Failed to connect to RabbitMQ for event consumption: {e}")
            logger.warning(
                "Running in mock mode - events will not be consumed from queue"
            )
            # Don't raise the exception, allow the service to start in mock mode

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        self.is_consuming = False

        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Disconnected event consumer from RabbitMQ")

    async def start_consuming(self) -> None:
        """Start consuming messages from the queue."""
        if not self.queue or not self.channel:
            logger.warning(
                "Mock mode: Event consumer not connected, cannot consume messages"
            )
            return

        try:
            self.is_consuming = True
            logger.info(
                f"Starting to consume SUBTITLE_REQUESTED events from queue "
                f"'{self.queue_name}'"
            )

            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self.is_consuming:
                        logger.info("Consumer stopped, breaking message loop")
                        break

                    await self._on_message(message)

        except asyncio.CancelledError:
            logger.info("Event consumer task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in event consumer loop: {e}", exc_info=True)
            raise

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        """
        Handle incoming message from queue.

        Args:
            message: Incoming RabbitMQ message
        """
        async with message.process():
            try:
                # Parse message body as SubtitleEvent
                event_data = message.body.decode()
                event = SubtitleEvent.model_validate_json(event_data)

                logger.info(
                    f"Received event {event.event_type.value} for job {event.job_id}"
                )

                # Only process SUBTITLE_REQUESTED events
                if event.event_type != EventType.SUBTITLE_REQUESTED:
                    logger.debug(
                        f"Ignoring event type {event.event_type.value}, "
                        f"only processing {EventType.SUBTITLE_REQUESTED.value}"
                    )
                    return

                # Process the subtitle request
                await self._process_subtitle_request(event)

            except Exception as e:
                logger.error(f"Failed to process message: {e}", exc_info=True)
                # Message is still acknowledged to avoid reprocessing bad messages

    async def _process_subtitle_request(self, event: SubtitleEvent) -> None:
        """
        Process a SUBTITLE_REQUESTED event by enqueuing download task.

        Args:
            event: SubtitleEvent containing request details in payload
        """
        try:
            payload = event.payload

            # Extract required fields from payload
            video_url = payload.get("video_url")
            video_title = payload.get("video_title")
            language = payload.get("language")
            target_language = payload.get("target_language")
            preferred_sources = payload.get("preferred_sources", [])

            # Validate required fields
            if (
                not ValidationUtils.is_non_empty_string(video_url)
                or not ValidationUtils.is_non_empty_string(video_title)
                or not ValidationUtils.is_non_empty_string(language)
            ):
                error_msg = (
                    f"Missing required fields in event payload: "
                    f"video_url={video_url}, video_title={video_title}, "
                    f"language={language}"
                )
                logger.error(error_msg)
                await redis_client.update_phase(
                    event.job_id,
                    SubtitleStatus.FAILED,
                    source="manager",
                    metadata={"error_message": error_msg},
                )
                return

            # Create SubtitleRequest from event payload
            subtitle_request = SubtitleRequest(
                video_url=video_url,
                video_title=video_title,
                language=language,
                target_language=target_language,
                preferred_sources=preferred_sources,
            )

            logger.info(
                f"Processing subtitle request for job {event.job_id}: "
                f"{video_title} ({language} -> {target_language or 'none'})"
            )

            # Check for duplicate request at manager level (defense in depth)
            dedup_result = await duplicate_prevention.check_and_register(
                video_url, language, event.job_id
            )

            if dedup_result.is_duplicate:
                logger.warning(
                    f"⚠️ Duplicate event reached manager for {video_title} - "
                    f"already processing as job {dedup_result.existing_job_id}. "
                    f"Scanner-level deduplication may have been bypassed."
                )
                # Idempotent behavior: treat as success (already being processed)
                return

            # Enqueue download task via orchestrator
            success = await orchestrator.enqueue_download_task(
                subtitle_request, event.job_id
            )

            if not success:
                logger.error(f"Failed to enqueue download task for job {event.job_id}")
                await redis_client.update_phase(
                    event.job_id,
                    SubtitleStatus.FAILED,
                    source="manager",
                    metadata={"error_message": "Failed to enqueue download task"},
                )
                return

            logger.info(f"Successfully enqueued download task for job {event.job_id}")

        except Exception as e:
            error_msg = f"Error processing subtitle request: {e}"
            logger.error(error_msg, exc_info=True)

            # Update job status to FAILED
            try:
                await redis_client.update_phase(
                    event.job_id,
                    SubtitleStatus.FAILED,
                    source="manager",
                    metadata={"error_message": str(e)},
                )
            except Exception as redis_error:
                logger.error(
                    f"Failed to update job status in Redis: {redis_error}",
                    exc_info=True,
                )

    def stop(self) -> None:
        """Signal the consumer to stop consuming messages."""
        logger.info("Stopping event consumer...")
        self.is_consuming = False


# Global event consumer instance
event_consumer = SubtitleEventConsumer()
