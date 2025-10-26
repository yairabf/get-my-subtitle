"""Debug worker for consuming and logging RabbitMQ messages."""

import asyncio
import json
import logging
from typing import Dict, Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_message(message: AbstractIncomingMessage) -> None:
    """Process a single message from the queue."""
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
        
        # Simulate some processing time
        await asyncio.sleep(1)
        
        logger.info("✅ Message processed successfully!")
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON: {e}")
        logger.error(f"Raw body: {message.body}")
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")


async def consume_messages() -> None:
    """Consume messages from the subtitle download queue."""
    connection = None
    
    try:
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


async def main() -> None:
    """Main entry point for the debug worker."""
    logger.info("🚀 Starting Subtitle Downloader Debug Worker")
    logger.info("This worker will consume and log messages from RabbitMQ")
    logger.info("=" * 60)
    
    await consume_messages()


if __name__ == "__main__":
    asyncio.run(main())
