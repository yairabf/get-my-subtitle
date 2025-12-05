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
from common.connection_utils import check_and_log_reconnection
from common.duplicate_prevention import DuplicatePreventionService
from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleRequest
from common.utils import DateTimeUtils, ValidationUtils
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
        self._should_stop = False

    async def connect(self, max_retries: int = 10, retry_delay: float = 3.0) -> None:
        """Establish connection to RabbitMQ and bind queue to topic exchange with retry logic."""
        for attempt in range(max_retries):
            try:
                self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)

                # Add reconnection callbacks
                self.connection.reconnect_callbacks.add(
                    lambda conn: logger.info(
                        "🔄 Manager event consumer reconnected to RabbitMQ successfully!"
                    )
                )

                self.channel = await self.connection.channel()

                # Declare topic exchange (should already exist from event_publisher)
                self.exchange = await self.channel.declare_exchange(
                    self.exchange_name, ExchangeType.TOPIC, durable=True
                )

                # Declare durable queue for this consumer
                self.queue = await self.channel.declare_queue(
                    self.queue_name, durable=True
                )

                # Bind queue to exchange for SUBTITLE_REQUESTED events only
                # Note: SUBTITLE_TRANSLATE_REQUESTED events are ignored - downloader handles task creation directly
                await self.queue.bind(
                    exchange=self.exchange, routing_key=self.routing_key
                )

                logger.info(
                    f"Connected to RabbitMQ - Queue '{self.queue_name}' bound to "
                    f"exchange '{self.exchange_name}' with routing key: '{self.routing_key}'"
                )
                return  # Success, exit retry loop

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.warning(
                        f"Failed to connect to RabbitMQ after {max_retries} attempts: {e}"
                    )
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
        """Start consuming messages with automatic reconnection and health monitoring."""
        self._should_stop = False
        reconnect_delay = settings.rabbitmq_reconnect_initial_delay
        consecutive_failures = 0
        max_consecutive_failures = 3

        while not self._should_stop:
            try:
                # Clean up any existing connections before reconnecting
                if self.connection and not self.connection.is_closed:
                    try:
                        await self.connection.close()
                    except Exception:
                        pass
                    self.connection = None
                    self.channel = None
                    self.exchange = None
                    self.queue = None

                # Connect to RabbitMQ
                await self.connect()

                # Check if connection succeeded
                if not self.queue or not self.channel:
                    logger.warning(
                        "Mock mode: Event consumer not connected, cannot consume messages"
                    )
                    # In mock mode, just sleep and retry
                    if not self._should_stop:
                        await asyncio.sleep(reconnect_delay)
                    continue

                # Reset failure counter on successful connection
                consecutive_failures = 0
                reconnect_delay = settings.rabbitmq_reconnect_initial_delay

                self.is_consuming = True
                logger.info("🎧 Starting to consume SUBTITLE_REQUESTED events...")
                logger.info("Press Ctrl+C to stop")
                logger.info("=" * 60)

                # Start consuming with health monitoring
                await self._consume_with_health_monitoring()

            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal, shutting down...")
                self._should_stop = True
                break
            except asyncio.CancelledError:
                logger.info("Event consumer task cancelled")
                self._should_stop = True
                raise
            except Exception as e:
                self.is_consuming = False
                consecutive_failures += 1
                logger.error(
                    f"❌ Error in event consumer (failure #{consecutive_failures}): {e}",
                    exc_info=True,
                )

                if not self._should_stop:
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            f"❌ Too many consecutive failures ({consecutive_failures}), "
                            f"increasing reconnect delay to {reconnect_delay * 2}s"
                        )
                        reconnect_delay = min(
                            reconnect_delay * 2, settings.rabbitmq_reconnect_max_delay
                        )
                        consecutive_failures = 0  # Reset after backing off

                    logger.warning(f"Attempting to reconnect in {reconnect_delay}s...")
                    await asyncio.sleep(reconnect_delay)
                else:
                    break
            finally:
                if self._should_stop:
                    await self.disconnect()

    async def _consume_with_health_monitoring(self) -> None:
        """Consume messages with periodic health checks."""
        last_health_check = asyncio.get_event_loop().time()
        health_check_interval = settings.rabbitmq_health_check_interval

        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                if self._should_stop or not self.is_consuming:
                    logger.info("Consumer stopped, breaking message loop")
                    break

                # Periodic health check
                current_time = asyncio.get_event_loop().time()
                if current_time - last_health_check > health_check_interval:
                    if not await self.is_healthy():
                        logger.warning(
                            "⚠️ Health check failed during consumption, will reconnect..."
                        )
                        raise ConnectionError("Health check failed")
                    last_health_check = current_time

                logger.debug(
                    f"Received message from queue '{self.queue_name}', routing_key: {message.routing_key}"
                )
                await self._on_message(message)

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
                logger.debug(
                    f"Parsing event data: {event_data[:200]}..."
                )  # Log first 200 chars
                event = SubtitleEvent.model_validate_json(event_data)

                logger.info(
                    f"Received event {event.event_type.value} for job {event.job_id} "
                    f"(routing_key: {message.routing_key})"
                )

                # Route to appropriate handler based on event type
                if event.event_type == EventType.SUBTITLE_REQUESTED:
                    # Process the subtitle request
                    await self._process_subtitle_request(event)
                elif event.event_type == EventType.SUBTITLE_TRANSLATE_REQUESTED:
                    # Ignore translation request events - downloader handles task creation directly
                    # Manager only creates translation tasks via direct API calls (/subtitles/translate)
                    logger.debug(
                        f"Ignoring SUBTITLE_TRANSLATE_REQUESTED event for job {event.job_id} - "
                        f"downloader handles task creation directly"
                    )
                else:
                    logger.debug(
                        f"Ignoring event type {event.event_type.value}, "
                        f"only processing {EventType.SUBTITLE_REQUESTED.value}"
                    )
                    return

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
                # Publish failure event instead of updating Redis directly
                failure_event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=event.job_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="manager",
                    payload={"error_message": error_msg},
                )
                await event_publisher.publish_event(failure_event)
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
                # If the existing job_id matches the event job_id, this is the same job
                # (scanner already registered it), so proceed with processing
                if dedup_result.existing_job_id == event.job_id:
                    logger.info(
                        f"✅ Event for job {event.job_id} matches registered job - "
                        f"proceeding with processing"
                    )
                else:
                    # Different job_id means this is a true duplicate
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
                # Publish failure event instead of updating Redis directly
                failure_event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=event.job_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="manager",
                    payload={"error_message": "Failed to enqueue download task"},
                )
                await event_publisher.publish_event(failure_event)
                return

            logger.info(f"Successfully enqueued download task for job {event.job_id}")

        except Exception as e:
            error_msg = f"Error processing subtitle request: {e}"
            logger.error(error_msg, exc_info=True)

            # Publish failure event instead of updating Redis directly
            try:
                failure_event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=event.job_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="manager",
                    payload={"error_message": str(e)},
                )
                await event_publisher.publish_event(failure_event)
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish failure event: {publish_error}",
                    exc_info=True,
                )

    async def _process_translation_request(self, event: SubtitleEvent) -> None:
        """
        Process a SUBTITLE_TRANSLATE_REQUESTED event by enqueuing translation task.

        Args:
            event: SubtitleEvent containing translation request details in payload
        """
        try:
            payload = event.payload

            # Extract required fields from payload
            subtitle_file_path = payload.get("subtitle_file_path")
            source_language = payload.get("source_language")
            target_language = payload.get("target_language")

            # Validate required fields
            if (
                not ValidationUtils.is_non_empty_string(subtitle_file_path)
                or not ValidationUtils.is_non_empty_string(source_language)
                or not ValidationUtils.is_non_empty_string(target_language)
            ):
                error_msg = (
                    f"Missing required fields in translation event payload: "
                    f"subtitle_file_path={subtitle_file_path}, "
                    f"source_language={source_language}, "
                    f"target_language={target_language}"
                )
                logger.error(error_msg)
                # Publish failure event
                failure_event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=event.job_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="manager",
                    payload={"error_message": error_msg},
                )
                await event_publisher.publish_event(failure_event)
                return

            logger.info(
                f"Processing translation request for job {event.job_id}: "
                f"{subtitle_file_path} ({source_language} -> {target_language})"
            )

            # Enqueue translation task via orchestrator
            success = await orchestrator.enqueue_translation_task(
                event.job_id,
                subtitle_file_path,
                source_language,
                target_language,
            )

            if not success:
                logger.error(
                    f"Failed to enqueue translation task for job {event.job_id}"
                )
                # Publish failure event
                failure_event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=event.job_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="manager",
                    payload={"error_message": "Failed to enqueue translation task"},
                )
                await event_publisher.publish_event(failure_event)
                return

            logger.info(
                f"Successfully enqueued translation task for job {event.job_id}"
            )

        except Exception as e:
            error_msg = f"Error processing translation request: {e}"
            logger.error(error_msg, exc_info=True)

            # Publish failure event
            try:
                failure_event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=event.job_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="manager",
                    payload={"error_message": str(e)},
                )
                await event_publisher.publish_event(failure_event)
            except Exception as publish_error:
                logger.error(
                    f"Failed to publish failure event: {publish_error}",
                    exc_info=True,
                )

    async def is_healthy(self) -> bool:
        """
        Check if the consumer is healthy and consuming messages.

        Returns:
            True if consumer is connected and consuming, False otherwise
        """
        try:
            # Check if connection exists and is open
            if not self.connection or self.connection.is_closed:
                return False

            # Check if channel exists
            if not self.channel:
                return False

            # Check if exchange and queue are set up
            if not self.exchange or not self.queue:
                return False

            # Check if consuming flag is set
            if not self.is_consuming:
                return False

            # Check Redis connection health
            if not await check_and_log_reconnection(
                redis_client.ensure_connected,
                "Redis",
                "manager event consumer",
                lambda: redis_client.connected,
            ):
                return False

            return True
        except Exception as e:
            logger.warning(f"Event consumer health check failed with exception: {e}")
            return False

    def stop(self) -> None:
        """Signal the consumer to stop consuming messages."""
        logger.info("Stopping event consumer...")
        self._should_stop = True
        self.is_consuming = False


# Global event consumer instance
event_consumer = SubtitleEventConsumer()
