"""Event consumer worker for processing subtitle events from RabbitMQ."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleStatus

# Configure logging
service_logger = setup_service_logging("consumer", enable_file_logging=True)
logger = service_logger.logger


class EventConsumer:
    """Consumes subtitle processing events from RabbitMQ."""

    def __init__(self):
        """Initialize the event consumer."""
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.abc.AbstractChannel] = None
        self.exchange_name = "subtitle.events"
        self.queue_name = "subtitle.events.consumer"

    async def connect(self) -> None:
        """Establish connection to RabbitMQ and Redis."""
        # Connect to Redis
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()

        # Connect to RabbitMQ
        logger.info("🔌 Connecting to RabbitMQ...")
        self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self.channel = await self.connection.channel()

        # Set QoS to process one message at a time
        await self.channel.set_qos(prefetch_count=1)

        logger.info("Connected to RabbitMQ successfully")

    async def setup_consumers(self) -> None:
        """Setup topic exchange bindings for event consumption."""
        if not self.channel:
            raise RuntimeError("Channel not initialized. Call connect() first.")

        # Declare the topic exchange (should already exist, but this ensures it)
        exchange = await self.channel.declare_exchange(
            self.exchange_name, ExchangeType.TOPIC, durable=True
        )

        # Declare a queue for this consumer
        queue = await self.channel.declare_queue(self.queue_name, durable=True)

        # Bind queue to exchange with routing patterns
        # Listen to all subtitle.* and job.* events
        await queue.bind(exchange, routing_key="subtitle.*")
        await queue.bind(exchange, routing_key="job.*")

        logger.info(
            f"Queue '{self.queue_name}' bound to exchange '{self.exchange_name}' "
            f"with patterns: subtitle.*, job.*"
        )

        return queue

    async def handle_subtitle_ready(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.ready event.

        Args:
            event: SubtitleEvent containing subtitle ready information
        """
        logger.info(f"📥 Handling SUBTITLE_READY for job {event.job_id}")

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

            logger.info(
                f"✅ Successfully processed SUBTITLE_READY for job {event.job_id}"
            )

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
        logger.info(f"📥 Handling SUBTITLE_TRANSLATED for job {event.job_id}")

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

            logger.info(
                f"✅ Successfully processed SUBTITLE_TRANSLATED for job {event.job_id}"
            )

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
        logger.info(f"📥 Handling JOB_FAILED for job {event.job_id}")

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

            logger.info(f"✅ Successfully processed JOB_FAILED for job {event.job_id}")

        except Exception as e:
            logger.error(f"❌ Error handling JOB_FAILED for job {event.job_id}: {e}")

    async def handle_download_requested(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.download.requested event.

        Args:
            event: SubtitleEvent containing download request information
        """
        logger.info(f"📥 Handling DOWNLOAD_REQUESTED for job {event.job_id}")

        try:
            # Just record the event - status already updated by manager
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.info(
                f"✅ Successfully recorded DOWNLOAD_REQUESTED for job {event.job_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ Error handling DOWNLOAD_REQUESTED for job {event.job_id}: {e}"
            )

    async def handle_translate_requested(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.translate.requested event.

        Args:
            event: SubtitleEvent containing translation request information
        """
        logger.info(f"📥 Handling TRANSLATE_REQUESTED for job {event.job_id}")

        try:
            # Just record the event - status already updated by manager
            await redis_client.record_event(
                event.job_id, event.event_type.value, event.payload, source="consumer"
            )

            logger.info(
                f"✅ Successfully recorded TRANSLATE_REQUESTED for job {event.job_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ Error handling TRANSLATE_REQUESTED for job {event.job_id}: {e}"
            )

    async def handle_subtitle_missing(self, event: SubtitleEvent) -> None:
        """
        Handle subtitle.missing event.

        Updates job status to SUBTITLE_MISSING (terminal state) when subtitles
        cannot be found and translation is not available.

        Args:
            event: SubtitleEvent containing subtitle missing information
        """
        logger.info(f"📥 Handling SUBTITLE_MISSING for job {event.job_id}")

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

            logger.info(
                f"✅ Successfully processed SUBTITLE_MISSING for job {event.job_id}"
            )

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

            logger.info("=" * 50)
            logger.info(f"📬 RECEIVED EVENT: {message.routing_key}")
            logger.info("=" * 50)
            logger.debug(f"Event data: {json.dumps(message_data, indent=2)}")

            # Validate and parse as SubtitleEvent
            event = SubtitleEvent.model_validate(message_data)

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
            else:
                logger.warning(f"⚠️  Unknown event type: {event.event_type}")

            logger.info("=" * 50)

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"Raw body: {message.body}")
        except Exception as e:
            logger.error(f"❌ Error processing event: {e}")

    async def start_consuming(self) -> None:
        """Start consuming events from the queue."""
        try:
            await self.connect()
            queue = await self.setup_consumers()

            logger.info("🎧 Starting to consume events...")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 60)

            # Start consuming messages
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await self.process_event(message)

        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"❌ Error in consumer: {e}")
        finally:
            await self.disconnect()

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
    await consumer.start_consuming()


if __name__ == "__main__":
    asyncio.run(main())
