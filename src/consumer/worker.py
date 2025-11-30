"""Event consumer worker for processing subtitle events from RabbitMQ."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings  # noqa: E402
from common.logging_config import setup_service_logging  # noqa: E402
from common.redis_client import redis_client  # noqa: E402
from common.schemas import EventType, SubtitleEvent, SubtitleStatus  # noqa: E402

# Configure logging
service_logger = setup_service_logging("consumer", enable_file_logging=True)
logger = service_logger.logger


class EventConsumer:
    """Consumes subtitle processing events from RabbitMQ."""

    def __init__(self):
        """Initialize the event consumer."""
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.abc.AbstractChannel] = None
        self.queue: Optional[aio_pika.abc.AbstractQueue] = None
        self.exchange_name = "subtitle.events"
        self.queue_name = "subtitle.events.consumer"
        self.is_consuming = False
        self._should_stop = False

    async def connect(self, max_retries: int = 10, retry_delay: float = 3.0) -> None:
        """Establish connection to RabbitMQ and Redis with retry logic."""
        # Connect to Redis
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()

        # Connect to RabbitMQ with retries
        logger.info("🔌 Connecting to RabbitMQ...")
        for attempt in range(max_retries):
            try:
                self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
                self.channel = await self.connection.channel()

                # Set QoS to process one message at a time
                await self.channel.set_qos(prefetch_count=1)

                logger.info("Connected to RabbitMQ successfully")
                return  # Success, exit retry loop

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to connect to RabbitMQ after {max_retries} attempts: {e}"
                    )
                    raise

    async def setup_consumers(self) -> aio_pika.abc.AbstractQueue:
        """Setup topic exchange bindings for event consumption."""
        if not self.channel:
            raise RuntimeError("Channel not initialized. Call connect() first.")

        # Declare the topic exchange (should already exist, but this ensures it)
        exchange = await self.channel.declare_exchange(
            self.exchange_name, ExchangeType.TOPIC, durable=True
        )

        # Declare a queue for this consumer
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)

        # Bind queue to exchange with routing patterns
        # Listen to all subtitle.*, job.*, and media.* events
        # Use # to match multiple words (e.g., subtitle.download.requested)
        await self.queue.bind(exchange, routing_key="subtitle.#")
        await self.queue.bind(exchange, routing_key="job.#")
        await self.queue.bind(exchange, routing_key="media.#")

        logger.info(
            f"Queue '{self.queue_name}' bound to exchange '{self.exchange_name}' "
            f"with patterns: subtitle.#, job.#, media.#"
        )

        return self.queue

    async def handle_subtitle_ready(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.ready event.

        Args:
            event: SubtitleEvent containing subtitle ready information
        """
        try:
            # Update job status to DONE
            await redis_client.update_phase(
                event.job_id,
                SubtitleStatus.DONE,
                source="consumer",
                metadata=event.payload,
            )

            # Record event in history
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.debug(f"✅ Processed SUBTITLE_READY for job {event.job_id}")

        except Exception as e:
            logger.error(
                f"❌ Error handling SUBTITLE_READY for job {event.job_id}: {e}"
            )

    async def handle_subtitle_translated(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.translated event.

        Args:
            event: SubtitleEvent containing translation completion information
        """
        try:
            # Update job status to DONE
            await redis_client.update_phase(
                event.job_id,
                SubtitleStatus.DONE,
                source="consumer",
                metadata=event.payload,
            )

            # Record event in history
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.debug(f"✅ Processed SUBTITLE_TRANSLATED for job {event.job_id}")

        except Exception as e:
            logger.error(
                f"❌ Error handling SUBTITLE_TRANSLATED for job {event.job_id}: {e}"
            )

    async def handle_job_failed(self, event: SubtitleEvent) -> None:
        """
        Handle job.failed event.

        Args:
            event: SubtitleEvent containing failure information
        """
        try:
            # Extract error message from payload
            error_message = event.payload.get("error_message", "Unknown error")

            # Update job status to FAILED
            await redis_client.update_phase(
                event.job_id,
                SubtitleStatus.FAILED,
                source="consumer",
                metadata={"error_message": error_message},
            )

            # Record event in history
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.warning(
                f"⚠️  Processed JOB_FAILED for job {event.job_id}: {error_message}"
            )

        except Exception as e:
            logger.error(f"❌ Error handling JOB_FAILED for job {event.job_id}: {e}")

    async def handle_download_requested(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.download.requested event - update status to DOWNLOAD_QUEUED.

        Args:
            event: SubtitleEvent containing download request information
        """
        try:
            # Update job status to DOWNLOAD_QUEUED
            await redis_client.update_phase(
                event.job_id,
                SubtitleStatus.DOWNLOAD_QUEUED,
                source="consumer",
                metadata=event.payload,
            )

            # Record event in history
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.debug(f"✅ Processed DOWNLOAD_REQUESTED for job {event.job_id}")

        except Exception as e:
            logger.error(
                f"❌ Error handling DOWNLOAD_REQUESTED for job {event.job_id}: {e}"
            )

    async def handle_translate_requested(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.translate.requested event - update status to TRANSLATE_QUEUED.

        Args:
            event: SubtitleEvent containing translation request information
        """
        try:
            # Update job status to TRANSLATE_QUEUED
            await redis_client.update_phase(
                event.job_id,
                SubtitleStatus.TRANSLATE_QUEUED,
                source="consumer",
                metadata=event.payload,
            )

            # Record event in history
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.debug(f"✅ Processed TRANSLATE_REQUESTED for job {event.job_id}")

        except Exception as e:
            logger.error(
                f"❌ Error handling TRANSLATE_REQUESTED for job {event.job_id}: {e}"
            )

    async def handle_media_file_detected(self, event: SubtitleEvent) -> None:
        """
        Handle media.file.detected event.

        Args:
            event: SubtitleEvent containing media file detection information
        """
        try:
            # Record the event for audit trail
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.debug(f"✅ Recorded MEDIA_FILE_DETECTED for job {event.job_id}")

        except Exception as e:
            logger.error(
                f"❌ Error handling MEDIA_FILE_DETECTED for job {event.job_id}: {e}"
            )

    async def handle_subtitle_missing(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.missing event.

        Updates job status to SUBTITLE_MISSING (terminal state) when subtitles
        cannot be found and translation is not available.

        Args:
            event: SubtitleEvent containing subtitle missing information
        """
        try:
            # Update job status to SUBTITLE_MISSING
            await redis_client.update_phase(
                event.job_id,
                SubtitleStatus.SUBTITLE_MISSING,
                source="consumer",
                metadata=event.payload,
            )

            # Record event in history
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.warning(f"⚠️  Processed SUBTITLE_MISSING for job {event.job_id}")

        except Exception as e:
            logger.error(
                f"❌ Error handling SUBTITLE_MISSING for job {event.job_id}: {e}"
            )

    async def process_event(self, message: AbstractIncomingMessage) -> None:
        """
        Process a single event message from the queue.

        Args:
            message: RabbitMQ message containing event data
        """
        try:
            # Parse the message body as SubtitleEvent
            message_data = json.loads(message.body.decode())

            # Validate and parse as SubtitleEvent
            event = SubtitleEvent.model_validate(message_data)

            logger.debug(
                f"📬 Processing event: {event.event_type.value} for job {event.job_id}"
            )

            # Route to appropriate handler based on event type
            if event.event_type == EventType.SUBTITLE_READY:
                await self.handle_subtitle_ready(event)
            elif event.event_type == EventType.SUBTITLE_MISSING:
                await self.handle_subtitle_missing(event)
            elif event.event_type == EventType.SUBTITLE_TRANSLATED:
                await self.handle_subtitle_translated(event)
            elif event.event_type == EventType.JOB_FAILED:
                await self.handle_job_failed(event)
            elif event.event_type == EventType.SUBTITLE_DOWNLOAD_REQUESTED:
                await self.handle_download_requested(event)
            elif event.event_type == EventType.SUBTITLE_TRANSLATE_REQUESTED:
                await self.handle_translate_requested(event)
            elif event.event_type == EventType.MEDIA_FILE_DETECTED:
                await self.handle_media_file_detected(event)
            else:
                logger.warning(f"⚠️  Unknown event type: {event.event_type}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"Raw body: {message.body}")
        except Exception as e:
            logger.error(f"❌ Error processing event: {e}")

    async def start_consuming(self) -> None:
        """Start consuming events from the queue with automatic reconnection and health monitoring."""
        self._should_stop = False
        reconnect_delay = 3.0
        health_check_interval = 30.0  # Check health every 30 seconds
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
                    self.queue = None

                await self.connect()
                queue = await self.setup_consumers()
                self.is_consuming = True
                consecutive_failures = (
                    0  # Reset failure counter on successful connection
                )

                logger.info("🎧 Starting to consume events...")
                logger.info("Press Ctrl+C to stop")
                logger.info("=" * 60)

                # Start consuming messages with health monitoring
                async def consume_with_health_check():
                    """Consume messages with periodic health checks."""
                    last_health_check = asyncio.get_event_loop().time()

                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            if self._should_stop:
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

                            async with message.process():
                                await self.process_event(message)

                await consume_with_health_check()

            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal, shutting down...")
                self._should_stop = True
                break
            except Exception as e:
                self.is_consuming = False
                consecutive_failures += 1
                logger.error(
                    f"❌ Error in consumer (failure #{consecutive_failures}): {e}"
                )
                import traceback

                logger.debug(f"Traceback: {traceback.format_exc()}")

                if not self._should_stop:
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            f"❌ Too many consecutive failures ({consecutive_failures}), "
                            f"increasing reconnect delay to {reconnect_delay * 2}s"
                        )
                        reconnect_delay = min(reconnect_delay * 2, 30.0)  # Cap at 30s
                        consecutive_failures = 0  # Reset after backing off

                    logger.warning(f"Attempting to reconnect in {reconnect_delay}s...")
                    await asyncio.sleep(reconnect_delay)
                else:
                    break
            finally:
                if self._should_stop:
                    await self.disconnect()
                    break

    def stop(self) -> None:
        """Stop consuming events gracefully."""
        logger.info("🛑 Stopping consumer...")
        self._should_stop = True
        self.is_consuming = False

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

            # Check if channel exists and is open
            if not self.channel:
                return False

            # Check if queue is set up
            if not self.queue:
                return False

            # Check if consuming flag is set
            if not self.is_consuming:
                return False

            # Queue object exists, which means channel is valid
            # No need to call get_queue as we already have the queue object

            return True
        except Exception as e:
            logger.warning(f"Health check failed with exception: {e}")
            return False

    async def disconnect(self) -> None:
        """Close connections to RabbitMQ and Redis."""
        if self.connection and not self.connection.is_closed:
            logger.info("🔌 Closing RabbitMQ connection...")
            await self.connection.close()

        logger.info("🔌 Closing Redis connection...")
        await redis_client.disconnect()


async def main() -> None:
    """Main entry point for the event consumer worker."""
    logger.info("🚀 Starting Subtitle Event Consumer Worker")
    logger.info("=" * 60)

    consumer = EventConsumer()

    # Set global instance for health checks
    try:
        from consumer.health import set_consumer_instance

        set_consumer_instance(consumer)
    except ImportError:
        # Health check module not available, continue without it
        pass

    await consumer.start_consuming()


if __name__ == "__main__":
    asyncio.run(main())
