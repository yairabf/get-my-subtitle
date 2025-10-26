#!/usr/bin/env python3
"""Simple debug worker script for testing RabbitMQ message consumption."""

import asyncio
import json
import logging

import aio_pika

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def consume():
    """Simple message consumer for debugging."""
    try:
        # Connect to RabbitMQ
        logger.info("Connecting to RabbitMQ...")
        conn = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
        
        # Create channel
        channel = await conn.channel()
        
        # Declare the queue
        queue = await channel.declare_queue("subtitle.download", durable=True)
        
        logger.info("Waiting for messages. Press Ctrl+C to stop...")
        
        # Consume messages
        async with queue.iterator() as it:
            async for msg in it:
                async with msg.process():
                    try:
                        message_data = json.loads(msg.body.decode())
                        print("\n" + "="*60)
                        print("📥 GOT MESSAGE:")
                        print("="*60)
                        print(json.dumps(message_data, indent=2))
                        print("="*60)
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON Error: {e}")
                        print(f"Raw body: {msg.body}")
                    except Exception as e:
                        print(f"❌ Error: {e}")
                        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(consume())
