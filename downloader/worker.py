"""Downloader worker for consuming download tasks and publishing events."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.event_publisher import event_publisher
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils

# Configure logging
service_logger = setup_service_logging("downloader", enable_file_logging=True)
logger = service_logger.logger


async def process_message(message: AbstractIncomingMessage) -> None:
    """Process a single message from the queue."""
    request_id = None
    try:
        # Parse the message body
        message_data = json.loads(message.body.decode())

        logger.info("=" * 50)
        logger.info("📥 RECEIVED MESSAGE")
        logger.info("=" * 50)
        logger.info(f"Routing Key: {message.routing_key}")
        logger.info(f"Exchange: {message.exchange}")
        logger.info(f"Message ID: {message.message_id}")
        logger.info(f"Timestamp: {message.timestamp}")
        logger.info(f"Body: {json.dumps(message_data, indent=2)}")
        logger.info("=" * 50)

        # Extract request_id from message
        request_id_str = message_data.get("request_id")
        if request_id_str:
            request_id = UUID(request_id_str)

        # Update status to DOWNLOAD_IN_PROGRESS
        if request_id:
            await redis_client.update_phase(
                request_id, SubtitleStatus.DOWNLOAD_IN_PROGRESS, source="downloader"
            )

        # Simulate some processing time (subtitle download)
        await asyncio.sleep(1)

        # Simulate subtitle found scenario (90% success rate for demo)
        import random
        subtitle_found = random.random() > 0.1

        if request_id:
            if subtitle_found:
                # Subtitle found - publish SUBTITLE_READY event
                subtitle_path = f"/subtitles/{request_id}.srt"
                download_url = f"https://example.com/subtitles/{request_id}.srt"

                event = SubtitleEvent(
                    event_type=EventType.SUBTITLE_READY,
                    job_id=request_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="downloader",
                    payload={
                        "subtitle_path": subtitle_path,
                        "language": message_data.get("language", "en"),
                        "download_url": download_url,
                    },
                )
                await event_publisher.publish_event(event)

                logger.info(f"✅ Subtitle found! Published SUBTITLE_READY event for job {request_id}")

            else:
                # Subtitle not found - need translation fallback
                logger.warning(f"⚠️  Subtitle not found for job {request_id}, will need translation")

                # In a real implementation, this would trigger translation request
                # For now, just log it
                event = SubtitleEvent(
                    event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
                    job_id=request_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="downloader",
                    payload={
                        "subtitle_file_path": f"/subtitles/fallback_{request_id}.en.srt",
                        "source_language": "en",
                        "target_language": message_data.get("language", "he"),
                    },
                )
                await event_publisher.publish_event(event)

                logger.info(f"📤 Published SUBTITLE_TRANSLATE_REQUESTED event for job {request_id}")

        logger.info("✅ Message processed successfully!")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON: {e}")
        logger.error(f"Raw body: {message.body}")
        # Publish JOB_FAILED event
        if request_id:
            event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={"error_message": f"Failed to parse message: {str(e)}"},
            )
            await event_publisher.publish_event(event)
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        # Publish JOB_FAILED event
        if request_id:
            event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={"error_message": f"Processing error: {str(e)}"},
            )
            await event_publisher.publish_event(event)


async def consume_messages() -> None:
    """Consume messages from the subtitle download queue."""
    connection = None

    try:
        # Connect to Redis
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()

        # Connect event publisher
        logger.info("🔌 Connecting event publisher...")
        await event_publisher.connect()

        # Connect to RabbitMQ
        logger.info("🔌 Connecting to RabbitMQ...")
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")

        # Create channel
        channel = await connection.channel()

        # Set QoS to process one message at a time
        await channel.set_qos(prefetch_count=1)

        # Declare the queue
        queue_name = "subtitle.download"
        logger.info(f"📋 Declaring queue: {queue_name}")
        queue = await channel.declare_queue(queue_name, durable=True)

        logger.info("🎧 Starting to consume messages...")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 50)

        # Start consuming messages
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await process_message(message)

    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"❌ Error in consumer: {e}")
    finally:
        logger.info("🔌 Disconnecting event publisher...")
        await event_publisher.disconnect()
        
        if connection and not connection.is_closed:
            logger.info("🔌 Closing RabbitMQ connection...")
            await connection.close()
        logger.info("🔌 Closing Redis connection...")
        await redis_client.disconnect()


async def main() -> None:
    """Main entry point for the downloader worker."""
    logger.info("🚀 Starting Subtitle Downloader Worker")
    logger.info("This worker will consume download tasks and publish events")
    logger.info("=" * 60)

    await consume_messages()


if __name__ == "__main__":
    asyncio.run(main())
