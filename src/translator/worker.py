"""Translator worker for processing translation messages from RabbitMQ."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings  # noqa: E402
from common.connection_utils import check_and_log_reconnection  # noqa: E402
from common.event_publisher import event_publisher  # noqa: E402
from common.logging_config import setup_service_logging  # noqa: E402
from common.redis_client import redis_client  # noqa: E402
from common.schemas import SubtitleStatus  # noqa: E402
from common.shutdown_manager import ShutdownManager  # noqa: E402
from common.utils import DateTimeUtils  # noqa: E402
from translator.error_handler import handle_translation_error  # noqa: E402
from translator.event_helpers import finalize_translation  # noqa: E402
from translator.file_operations import (  # noqa: E402
    read_and_parse_subtitle_file,
    save_translated_file,
)
from translator.message_handler import parse_and_validate_message  # noqa: E402
from translator.translation_orchestrator import (  # noqa: E402
    load_checkpoint_state,
    translate_segments_with_checkpoint,
)
from translator.translation_service import SubtitleTranslator  # noqa: E402

# Configure logging
service_logger = setup_service_logging("translator", enable_file_logging=True)
logger = service_logger.logger

# Message consumption constants
QUEUE_GET_TIMEOUT = 1.0  # Seconds to wait for message from queue
QUEUE_WAIT_TIMEOUT = 1.1  # asyncio timeout (slightly longer than queue timeout)
BUSY_WAIT_SLEEP = 0.1  # Sleep duration to reduce CPU usage during empty queue


async def process_translation_message(
    message: AbstractIncomingMessage, translator: SubtitleTranslator
) -> None:
    """
    Process a translation task message from the queue.

    This function orchestrates the translation workflow by:
    1. Parsing and validating the message
    2. Loading checkpoint state if available
    3. Reading and parsing the subtitle file
    4. Translating segments (with checkpoint resumption)
    5. Saving the translated file
    6. Finalizing by updating status and publishing events

    Args:
        message: RabbitMQ message containing translation task
        translator: SubtitleTranslator instance
    """
    request_id: Optional[UUID] = None

    try:
        # Parse and validate message
        task_data = await parse_and_validate_message(message)
        request_id = task_data.request_id

        # Track translation start time for duration calculation
        translation_start_time = DateTimeUtils.get_current_utc_datetime()
        logger.info(
            f"🕐 Translation started at {DateTimeUtils.format_timestamp_for_logging(translation_start_time)}"
        )

        # Update status to TRANSLATE_IN_PROGRESS
        await redis_client.update_phase(
            request_id, SubtitleStatus.TRANSLATE_IN_PROGRESS, source="translator"
        )

        # Load checkpoint state if available
        checkpoint_state = await load_checkpoint_state(
            request_id,
            task_data.subtitle_file_path,
            task_data.source_language,
            task_data.target_language,
        )

        # Read and parse subtitle file
        segments = await read_and_parse_subtitle_file(task_data.subtitle_file_path)

        # Translate segments (with checkpoint resumption)
        translated_segments = await translate_segments_with_checkpoint(
            segments, task_data, translator, checkpoint_state
        )

        # Save translated file
        output_path = await save_translated_file(
            translated_segments, task_data.subtitle_file_path, task_data.target_language
        )

        # Calculate translation duration
        translation_end_time = DateTimeUtils.get_current_utc_datetime()
        duration_seconds = (
            translation_end_time - translation_start_time
        ).total_seconds()
        logger.info(f"✅ Translation completed in {duration_seconds:.2f} seconds")

        # Finalize translation (update status and publish events)
        await finalize_translation(request_id, output_path, task_data, duration_seconds)

        logger.info("✅ Translation completed successfully!")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON: {e}")
        logger.error(f"Raw body: {message.body}")
        await handle_translation_error(request_id, e)

    except Exception as e:
        await handle_translation_error(request_id, e)


async def consume_translation_messages() -> None:
    """Consume translation messages from the RabbitMQ queue with automatic reconnection."""
    connection = None
    translator = SubtitleTranslator()
    reconnect_delay = settings.rabbitmq_reconnect_initial_delay
    consecutive_failures = 0
    max_consecutive_failures = 3
    shutdown_manager = ShutdownManager(
        "translator", shutdown_timeout=settings.shutdown_timeout
    )

    # Setup signal handlers
    await shutdown_manager.setup_signal_handlers()

    while not shutdown_manager.is_shutdown_requested():
        try:
            # Clean up stale connections
            if connection and not connection.is_closed:
                try:
                    await connection.close()
                except Exception:
                    pass
                connection = None

            # Connect to Redis
            logger.info("🔌 Connecting to Redis...")
            await redis_client.connect()

            # Connect event publisher
            logger.info("🔌 Connecting event publisher...")
            await event_publisher.connect()

            # Connect to RabbitMQ
            logger.info("🔌 Connecting to RabbitMQ...")
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)

            # Add reconnection callbacks
            connection.reconnect_callbacks.add(
                lambda conn: logger.info(
                    "🔄 Translator worker reconnected to RabbitMQ successfully!"
                )
            )

            # Create channel
            channel = await connection.channel()

            # Set QoS to process one message at a time
            await channel.set_qos(prefetch_count=1)

            # Declare the queue
            queue_name = "subtitle.translation"
            logger.info(f"📋 Declaring queue: {queue_name}")
            queue = await channel.declare_queue(queue_name, durable=True)

            # Reset failure counter on successful connection
            consecutive_failures = 0
            reconnect_delay = settings.rabbitmq_reconnect_initial_delay

            logger.info("🎧 Starting to consume translation messages...")
            logger.info("Press Ctrl+C to stop")
            logger.info("=" * 50)

            # Start consuming messages with health monitoring
            last_health_check = asyncio.get_event_loop().time()
            health_check_interval = settings.rabbitmq_health_check_interval

            # Consume messages with periodic shutdown checks
            while not shutdown_manager.is_shutdown_requested():
                try:
                    # Get message with timeout to allow periodic shutdown checks
                    message = await asyncio.wait_for(
                        queue.get(timeout=QUEUE_GET_TIMEOUT), timeout=QUEUE_WAIT_TIMEOUT
                    )

                    # Periodic health check (skip during shutdown)
                    if shutdown_manager.is_shutdown_requested():
                        break

                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_health_check > health_check_interval:
                        # Check Redis connection
                        if not await check_and_log_reconnection(
                            redis_client.ensure_connected,
                            "Redis",
                            "translator",
                            lambda: redis_client.connected,
                        ):
                            logger.error(
                                "Redis connection failed, stopping message processing..."
                            )
                            raise ConnectionError("Redis connection unavailable")

                        # Check RabbitMQ connection
                        if connection.is_closed:
                            logger.warning("RabbitMQ connection lost, reconnecting...")
                            raise ConnectionError("RabbitMQ connection closed")

                        last_health_check = current_time

                    # Process message with timeout for graceful shutdown
                    try:
                        async with message.process():
                            await asyncio.wait_for(
                                process_translation_message(message, translator),
                                timeout=shutdown_manager.shutdown_timeout,
                            )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"⚠️  Message processing timeout ({shutdown_manager.shutdown_timeout}s) "
                            f"during shutdown - message will be requeued"
                        )
                        # Message will be nacked automatically by context manager
                        break

                except asyncio.TimeoutError:
                    # No message received within timeout, reduce busy-wait
                    await asyncio.sleep(BUSY_WAIT_SLEEP)
                    continue
                except aio_pika.exceptions.QueueEmpty:
                    # No messages in queue, reduce CPU usage
                    await asyncio.sleep(BUSY_WAIT_SLEEP)
                    continue

            # Log shutdown initiation
            if shutdown_manager.is_shutdown_requested():
                logger.info("🛑 Shutdown requested, stopping message consumption...")

        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
            # Signal already handled by shutdown_manager
        except Exception as e:
            consecutive_failures += 1
            logger.error(
                f"❌ Error in translator (failure #{consecutive_failures}): {e}"
            )

            if not shutdown_manager.is_shutdown_requested():
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"❌ Too many consecutive failures ({consecutive_failures}), "
                        f"increasing reconnect delay to {reconnect_delay * 2}s"
                    )
                    reconnect_delay = min(
                        reconnect_delay * 2, settings.rabbitmq_reconnect_max_delay
                    )
                    consecutive_failures = 0

                logger.warning(f"Attempting to reconnect in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
        finally:
            if shutdown_manager.is_shutdown_requested():
                logger.info("🔌 Disconnecting event publisher...")
                await event_publisher.disconnect()

                if connection and not connection.is_closed:
                    logger.info("🔌 Closing RabbitMQ connection...")
                    await connection.close()
                logger.info("🔌 Closing Redis connection...")
                await redis_client.disconnect()
                break


async def main() -> None:
    """Main entry point for the translator worker."""
    logger.info("🚀 Starting Subtitle Translator Worker")
    logger.info(f"🤖 Using model: {settings.openai_model}")
    logger.info("This worker will consume translation tasks and publish events")
    logger.info("=" * 60)

    await consume_translation_messages()


if __name__ == "__main__":
    asyncio.run(main())
