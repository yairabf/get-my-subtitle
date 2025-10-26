"""Debug worker for consuming and logging RabbitMQ messages."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.redis_client import redis_client
from common.schemas import SubtitleStatus
from common.logging_config import setup_service_logging

# Configure logging
service_logger = setup_service_logging('downloader', enable_file_logging=True)
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
        
        # Simulate some processing time
        await asyncio.sleep(1)
        
        # Update job status to COMPLETED in Redis
        # In a real implementation, this would be based on actual subtitle download success
        if request_id:
            success = await redis_client.update_job_status(
                request_id,
                SubtitleStatus.COMPLETED,
                download_url=f"https://example.com/subtitles/{request_id}.srt"
            )
            if success:
                logger.info(f"✅ Updated job {request_id} status to COMPLETED in Redis")
            else:
                logger.warning(f"⚠️  Failed to update job {request_id} in Redis (but processing succeeded)")
        
        logger.info("✅ Message processed successfully!")
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON: {e}")
        logger.error(f"Raw body: {message.body}")
        # Update job status to FAILED if we have the request_id
        if request_id:
            await redis_client.update_job_status(
                request_id,
                SubtitleStatus.FAILED,
                error_message=f"Failed to parse message: {str(e)}"
            )
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        # Update job status to FAILED if we have the request_id
        if request_id:
            await redis_client.update_job_status(
                request_id,
                SubtitleStatus.FAILED,
                error_message=f"Processing error: {str(e)}"
            )


async def consume_messages() -> None:
    """Consume messages from the subtitle download queue."""
    connection = None
    
    try:
        # Connect to Redis
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()
        
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
        if connection and not connection.is_closed:
            logger.info("🔌 Closing RabbitMQ connection...")
            await connection.close()
        logger.info("🔌 Closing Redis connection...")
        await redis_client.disconnect()


async def main() -> None:
    """Main entry point for the debug worker."""
    logger.info("🚀 Starting Subtitle Downloader Debug Worker")
    logger.info("This worker will consume and log messages from RabbitMQ")
    logger.info("=" * 60)
    
    await consume_messages()


if __name__ == "__main__":
    asyncio.run(main())
