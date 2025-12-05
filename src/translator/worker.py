"""Translator worker for processing translation messages from RabbitMQ."""

import asyncio
import json
import sys
from pathlib import Path
from typing import List
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
from common.schemas import EventType, SubtitleEvent, SubtitleStatus  # noqa: E402
from common.subtitle_parser import (  # noqa: E402
    SRTParser,
    SubtitleSegment,
    extract_text_for_translation,
    merge_translated_chunks,
    merge_translations,
    split_subtitle_content,
)
from common.utils import DateTimeUtils, LanguageUtils, PathUtils  # noqa: E402
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
        source_language_raw = message_data.get("source_language")
        target_language_raw = message_data.get("target_language")

        if not all(
            [
                request_id_str,
                subtitle_file_path,
                source_language_raw,
                target_language_raw,
            ]
        ):
            raise ValueError("Missing required fields in translation task")

        # Convert language codes to ISO format (safety check - ensures consistency)
        source_language = LanguageUtils.opensubtitles_to_iso(source_language_raw)
        target_language = LanguageUtils.opensubtitles_to_iso(target_language_raw)

        # Log conversion if it changed
        if source_language != source_language_raw:
            logger.debug(
                f"Converted source language '{source_language_raw}' to ISO '{source_language}'"
            )
        if target_language != target_language_raw:
            logger.info(
                f"Converted target language '{target_language_raw}' to ISO '{target_language}'"
            )

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
        # Also limit by segment count to prevent API timeouts with very large chunks
        chunks = split_subtitle_content(
            segments,
            max_tokens=settings.translation_max_tokens_per_chunk,
            model=settings.openai_model,
            safety_margin=settings.translation_token_safety_margin,
            max_segments_per_chunk=settings.translation_max_segments_per_chunk,
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

        # Translate remaining chunks in parallel
        parallel_requests = settings.get_translation_parallel_requests()
        semaphore = asyncio.Semaphore(parallel_requests)

        logger.info(
            f"🚀 Starting parallel translation of {len(chunks) - start_chunk_idx} chunks "
            f"with {parallel_requests} concurrent requests"
        )

        async def _translate_chunk_parallel(
            chunk_idx: int,
            chunk: List[SubtitleSegment],
            semaphore: asyncio.Semaphore,
        ) -> tuple[int, List[SubtitleSegment]]:
            """
            Translate a single chunk with semaphore-controlled concurrency.

            Args:
                chunk_idx: Index of the chunk being translated
                chunk: List of SubtitleSegment objects to translate
                semaphore: Semaphore to limit concurrent API requests

            Returns:
                Tuple of (chunk_idx, translated_chunk) for ordering
            """
            async with semaphore:
                logger.info(
                    f"🔄 Translating chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} segments)"
                )

                # Extract text from segments
                texts = extract_text_for_translation(chunk)

                # Translate
                translations = await translator.translate_batch(
                    texts, source_language, target_language
                )

                # Get parsed segment numbers if available (for accurate missing segment identification)
                parsed_segment_numbers = translator.get_last_parsed_segment_numbers()

                # Merge translations back (with chunk context for better error messages)
                translated_chunk = merge_translations(
                    chunk,
                    translations,
                    chunk_index=chunk_idx,
                    total_chunks=len(chunks),
                    parsed_segment_numbers=parsed_segment_numbers,
                )

                logger.info(
                    f"✅ Completed chunk {chunk_idx + 1}/{len(chunks)} "
                    f"({len(translated_chunk)} segments translated)"
                )

                return chunk_idx, translated_chunk

        # Create tasks for all remaining chunks
        tasks = [
            _translate_chunk_parallel(chunk_idx, chunk, semaphore)
            for chunk_idx, chunk in enumerate(chunks[start_chunk_idx:], start_chunk_idx)
        ]

        # Execute all chunks in parallel (results may complete out of order)
        logger.info(f"⚡ Executing {len(tasks)} translation tasks in parallel...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any exceptions
        # Sort results by chunk_idx to ensure correct segment ordering
        valid_results = []
        failed_chunks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                chunk_idx = start_chunk_idx + i
                logger.error(
                    f"❌ Chunk {chunk_idx + 1}/{len(chunks)} translation failed: {result}"
                )
                failed_chunks.append((chunk_idx, result))
            else:
                valid_results.append(result)

        # If any chunks failed, raise an error with context about which chunks failed
        if failed_chunks:
            failed_indices = [idx for idx, _ in failed_chunks]
            error_msg = (
                f"Translation failed for {len(failed_chunks)} chunk(s): "
                f"{', '.join(f'chunk {idx + 1}' for idx in failed_indices)}. "
                f"First error: {failed_chunks[0][1]}"
            )
            logger.error(f"❌ {error_msg}")
            # Raise the first exception to maintain backward compatibility
            raise failed_chunks[0][1]

        # Sort by chunk_idx to ensure segments are in correct order
        valid_results.sort(key=lambda x: x[0])

        # Extend segments in correct order
        completed_chunk_indices = []
        for chunk_idx, translated_chunk in valid_results:
            all_translated_segments.extend(translated_chunk)
            completed_chunk_indices.append(chunk_idx)

        if completed_chunk_indices:
            chunk_range = (
                f"{min(completed_chunk_indices) + 1}-{max(completed_chunk_indices) + 1}"
            )
            logger.info(
                f"✅ Completed parallel translation batch: "
                f"{len(completed_chunk_indices)} chunks ({chunk_range})"
            )
        else:
            logger.info("✅ No chunks to translate")

        # Save checkpoint after parallel batch completion
        if settings.checkpoint_enabled:
            try:
                # Include all previously completed chunks plus newly completed ones
                all_completed_chunks = (
                    list(range(start_chunk_idx)) + completed_chunk_indices
                )
                await checkpoint_manager.save_checkpoint(
                    request_id=request_id,
                    subtitle_file_path=subtitle_file_path,
                    source_language=source_language,
                    target_language=target_language,
                    total_chunks=len(chunks),
                    completed_chunks=all_completed_chunks,
                    translated_segments=all_translated_segments,
                )
                logger.info(
                    f"💾 Saved checkpoint: {len(all_completed_chunks)}/{len(chunks)} chunks completed"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  Failed to save checkpoint after parallel batch: {e}"
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

        # Save translated file - generate path by replacing language code
        output_path = PathUtils.generate_subtitle_path_from_source(
            subtitle_file_path, target_language
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
    """Consume translation messages from the RabbitMQ queue with automatic reconnection."""
    connection = None
    translator = SubtitleTranslator()
    reconnect_delay = settings.rabbitmq_reconnect_initial_delay
    consecutive_failures = 0
    max_consecutive_failures = 3
    should_stop = False

    while not should_stop:
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
                lambda conn: logger.info("🔄 Translator worker reconnected to RabbitMQ successfully!")
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

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    # Periodic health check
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_health_check > health_check_interval:
                        # Check Redis connection
                        if not await check_and_log_reconnection(
                            redis_client.ensure_connected,
                            "Redis",
                            "translator",
                            lambda: redis_client.connected
                        ):
                            logger.error("Redis connection failed, stopping message processing...")
                            raise ConnectionError("Redis connection unavailable")
                        
                        # Check RabbitMQ connection
                        if connection.is_closed:
                            logger.warning("RabbitMQ connection lost, reconnecting...")
                            raise ConnectionError("RabbitMQ connection closed")
                        
                        last_health_check = current_time

                    async with message.process():
                        await process_translation_message(message, translator)

        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
            should_stop = True
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"❌ Error in translator (failure #{consecutive_failures}): {e}")
            
            if not should_stop:
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"❌ Too many consecutive failures ({consecutive_failures}), "
                        f"increasing reconnect delay to {reconnect_delay * 2}s"
                    )
                    reconnect_delay = min(
                        reconnect_delay * 2,
                        settings.rabbitmq_reconnect_max_delay
                    )
                    consecutive_failures = 0

                logger.warning(f"Attempting to reconnect in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
        finally:
            if should_stop:
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
