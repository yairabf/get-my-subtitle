"""Translator worker for processing translation messages from RabbitMQ."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings  # noqa: E402
from common.event_publisher import event_publisher  # noqa: E402
from common.logging_config import setup_service_logging  # noqa: E402
from common.redis_client import redis_client  # noqa: E402
from common.schemas import EventType, SubtitleEvent, SubtitleStatus  # noqa: E402
from common.subtitle_parser import (  # noqa: E402
    SRTParser,
    extract_text_for_translation,
    merge_translated_chunks,
    merge_translations,
    split_subtitle_content,
)
from common.utils import DateTimeUtils  # noqa: E402
from translator.checkpoint_manager import CheckpointManager  # noqa: E402
from translator.translation_service import SubtitleTranslator  # noqa: E402

# Configure logging
service_logger = setup_service_logging("translator", enable_file_logging=True)
logger = service_logger.logger


async def process_translation_message(
    message: AbstractIncomingMessage, translator: SubtitleTranslator
) -> None:
    """
    Process a translation task message from the queue.

    Args:
        message: RabbitMQ message containing translation task
        translator: SubtitleTranslator instance
    """
    request_id = None

    try:
        # Parse the message body
        message_data = json.loads(message.body.decode())

        logger.info("=" * 50)
        logger.info("📥 RECEIVED TRANSLATION TASK")
        logger.info("=" * 50)
        logger.info(f"Message: {json.dumps(message_data, indent=2)}")
        logger.info("=" * 50)

        # Extract task details
        request_id_str = message_data.get("request_id")
        subtitle_file_path = message_data.get("subtitle_file_path")
        source_language = message_data.get("source_language")
        target_language = message_data.get("target_language")

        if not all(
            [request_id_str, subtitle_file_path, source_language, target_language]
        ):
            raise ValueError("Missing required fields in translation task")

        request_id = UUID(request_id_str)

        # Track translation start time for duration calculation
        translation_start_time = DateTimeUtils.get_current_utc_datetime()
        logger.info(
            f"🕐 Translation started at {DateTimeUtils.format_timestamp_for_logging(translation_start_time)}"
        )

        # Update status to TRANSLATE_IN_PROGRESS
        await redis_client.update_phase(
            request_id, SubtitleStatus.TRANSLATE_IN_PROGRESS, source="translator"
        )

        # Initialize checkpoint manager
        checkpoint_manager = CheckpointManager()

        # Check for existing checkpoint
        checkpoint = None
        all_translated_segments = []
        start_chunk_idx = 0

        if settings.checkpoint_enabled:
            try:
                checkpoint = await checkpoint_manager.load_checkpoint(
                    request_id, target_language
                )
                if checkpoint:
                    logger.info(
                        f"📂 Found checkpoint: {len(checkpoint.completed_chunks)}/"
                        f"{checkpoint.total_chunks} chunks completed"
                    )

                    # Validate checkpoint matches current request
                    if (
                        checkpoint.subtitle_file_path == subtitle_file_path
                        and checkpoint.source_language == source_language
                        and checkpoint.target_language == target_language
                    ):
                        # Deserialize segments from checkpoint
                        all_translated_segments = (
                            checkpoint_manager.deserialize_segments_from_checkpoint(
                                checkpoint
                            )
                        )
                        start_chunk_idx = len(checkpoint.completed_chunks)
                        logger.info(
                            f"🔄 Resuming translation from chunk {start_chunk_idx + 1}"
                        )
                    else:
                        logger.warning(
                            "⚠️  Checkpoint metadata mismatch, starting fresh translation"
                        )
                        checkpoint = None
            except Exception as e:
                logger.warning(
                    f"⚠️  Failed to load checkpoint, starting fresh translation: {e}"
                )
                checkpoint = None

        # Read subtitle file
        logger.info(f"Reading subtitle file: {subtitle_file_path}")

        # Read the actual subtitle file
        subtitle_path = Path(subtitle_file_path)
        if not subtitle_path.exists():
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_file_path}")

        srt_content = subtitle_path.read_text(encoding="utf-8")
        logger.info(f"Read {len(srt_content)} characters from subtitle file")

        # Parse SRT content
        logger.info("Parsing SRT content...")
        segments = SRTParser.parse(srt_content)

        if not segments:
            raise ValueError("No subtitle segments found in file")

        logger.info(f"Parsed {len(segments)} subtitle segments")

        # Split into token-aware chunks for API limits
        chunks = split_subtitle_content(
            segments,
            max_tokens=settings.translation_max_tokens_per_chunk,
            model=settings.openai_model,
            safety_margin=settings.translation_token_safety_margin,
        )

        # If checkpoint exists, validate total chunks match
        if checkpoint and checkpoint.total_chunks != len(chunks):
            logger.warning(
                f"⚠️  Checkpoint total_chunks ({checkpoint.total_chunks}) doesn't match "
                f"current chunks ({len(chunks)}), starting fresh translation"
            )
            checkpoint = None
            all_translated_segments = []
            start_chunk_idx = 0

        # Translate remaining chunks
        for chunk_idx in range(start_chunk_idx, len(chunks)):
            chunk = chunks[chunk_idx]
            logger.info(
                f"Translating chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} segments)"
            )

            # Extract text from segments
            texts = extract_text_for_translation(chunk)

            # Translate
            translations = await translator.translate_batch(
                texts, source_language, target_language
            )

            # Merge translations back
            translated_chunk = merge_translations(chunk, translations)
            all_translated_segments.extend(translated_chunk)

            # Save checkpoint after each successful chunk translation
            if settings.checkpoint_enabled:
                try:
                    completed_chunks = list(range(chunk_idx + 1))
                    await checkpoint_manager.save_checkpoint(
                        request_id=request_id,
                        subtitle_file_path=subtitle_file_path,
                        source_language=source_language,
                        target_language=target_language,
                        total_chunks=len(chunks),
                        completed_chunks=completed_chunks,
                        translated_segments=all_translated_segments,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️  Failed to save checkpoint after chunk {chunk_idx + 1}: {e}"
                    )
                    # Continue translation even if checkpoint save fails

        # Merge and renumber translated segments
        merged_segments = merge_translated_chunks(all_translated_segments)
        logger.info(
            f"✅ Merged {len(all_translated_segments)} segments into "
            f"{len(merged_segments)} sequentially numbered segments"
        )

        # Format back to SRT
        translated_srt = SRTParser.format(merged_segments)

        # Save translated file
        output_path = Path(
            f"{subtitle_file_path.replace('.srt', '')}.{target_language}.srt"
        )

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write translated content to file
        output_path.write_text(translated_srt, encoding="utf-8")
        logger.info(f"✅ Saved translated subtitle to: {output_path}")
        logger.info(f"   File size: {output_path.stat().st_size} bytes")

        download_url = (
            f"https://example.com/subtitles/{request_id}.{target_language}.srt"
        )

        # Update status to COMPLETED after successful translation
        await redis_client.update_phase(
            request_id,
            SubtitleStatus.COMPLETED,
            source="translator",
            metadata={
                "translated_path": str(output_path),
                "download_url": download_url,
            },
        )
        logger.info(f"✅ Updated job {request_id} status to COMPLETED")

        # Clean up checkpoint after successful completion
        if settings.checkpoint_enabled and settings.checkpoint_cleanup_on_success:
            try:
                await checkpoint_manager.cleanup_checkpoint(request_id, target_language)
            except Exception as e:
                logger.warning(f"⚠️  Failed to cleanup checkpoint after completion: {e}")

        # Calculate translation duration
        translation_end_time = DateTimeUtils.get_current_utc_datetime()
        duration_seconds = (
            translation_end_time - translation_start_time
        ).total_seconds()
        logger.info(f"✅ Translation completed in {duration_seconds:.2f} seconds")

        # Publish TRANSLATION_COMPLETED event
        if request_id:
            translation_completed_event = SubtitleEvent(
                event_type=EventType.TRANSLATION_COMPLETED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="translator",
                payload={
                    "file_path": str(output_path),
                    "duration_seconds": duration_seconds,
                    "source_language": source_language,
                    "target_language": target_language,
                    "subtitle_file_path": subtitle_file_path,
                    "translated_path": str(output_path),
                },
            )
            await event_publisher.publish_event(translation_completed_event)

            logger.info(
                f"📤 Published TRANSLATION_COMPLETED event for job {request_id} "
                f"(duration: {duration_seconds:.2f}s)"
            )

        # Publish SUBTITLE_TRANSLATED event
        if request_id:
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_TRANSLATED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="translator",
                payload={
                    "translated_path": output_path,
                    "source_language": source_language,
                    "target_language": target_language,
                    "download_url": download_url,
                },
            )
            await event_publisher.publish_event(event)

            logger.info(f"✅ Published SUBTITLE_TRANSLATED event for job {request_id}")

        logger.info("✅ Translation completed successfully!")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON: {e}")
        logger.error(f"Raw body: {message.body}")
        # Publish JOB_FAILED event
        if request_id:
            event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="translator",
                payload={"error_message": f"Failed to parse message: {str(e)}"},
            )
            await event_publisher.publish_event(event)

    except Exception as e:
        logger.error(f"❌ Error processing translation: {e}")
        # Publish JOB_FAILED event
        if request_id:
            event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="translator",
                payload={"error_message": f"Translation error: {str(e)}"},
            )
            await event_publisher.publish_event(event)


async def consume_translation_messages() -> None:
    """Consume translation messages from the RabbitMQ queue."""
    connection = None
    translator = SubtitleTranslator()

    try:
        # Connect to Redis
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()

        # Connect event publisher
        logger.info("🔌 Connecting event publisher...")
        await event_publisher.connect()

        # Connect to RabbitMQ
        logger.info("🔌 Connecting to RabbitMQ...")
        connection = await aio_pika.connect_robust(settings.rabbitmq_url)

        # Create channel
        channel = await connection.channel()

        # Set QoS to process one message at a time
        await channel.set_qos(prefetch_count=1)

        # Declare the queue
        queue_name = "subtitle.translation"
        logger.info(f"📋 Declaring queue: {queue_name}")
        queue = await channel.declare_queue(queue_name, durable=True)

        logger.info("🎧 Starting to consume translation messages...")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 50)

        # Start consuming messages
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await process_translation_message(message, translator)

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
    """Main entry point for the translator worker."""
    logger.info("🚀 Starting Subtitle Translator Worker")
    logger.info(f"🤖 Using model: {settings.openai_model}")
    logger.info("This worker will consume translation tasks and publish events")
    logger.info("=" * 60)

    await consume_translation_messages()


if __name__ == "__main__":
    asyncio.run(main())
