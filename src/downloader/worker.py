"""Downloader worker for consuming download tasks and publishing events."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from common.config import settings  # noqa: E402
from common.connection_utils import check_and_log_reconnection  # noqa: E402
from common.event_publisher import event_publisher  # noqa: E402
from common.logging_config import setup_service_logging  # noqa: E402
from common.redis_client import redis_client  # noqa: E402
from common.schemas import (  # noqa: E402
    EventType,
    SubtitleEvent,
    SubtitleStatus,
    TranslationTask,
)
from common.utils import DateTimeUtils, LanguageUtils, PathUtils  # noqa: E402
from downloader.opensubtitles_client import (  # noqa: E402
    OpenSubtitlesAPIError,
    OpenSubtitlesAuthenticationError,
    OpenSubtitlesClient,
    OpenSubtitlesRateLimitError,
)

# Configure logging
service_logger = setup_service_logging("downloader", enable_file_logging=True)
logger = service_logger.logger

# Global OpenSubtitles client instance
opensubtitles_client = OpenSubtitlesClient()


async def process_message(
    message: AbstractIncomingMessage, channel: aio_pika.abc.AbstractChannel
) -> None:
    # Note: channel parameter kept for backward compatibility but no longer used
    # Translation tasks are now enqueued by manager's event consumer
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

        # Extract video metadata for subtitle search
        video_url = message_data.get("video_url")
        video_title = message_data.get("video_title")
        imdb_id = message_data.get("imdb_id")
        language = message_data.get("language", "en")

        logger.info(
            f"🔍 Searching for subtitles: url={video_url}, title={video_title}, imdb_id={imdb_id}, language={language}"
        )

        # Try to calculate file hash if video_url is a local file
        movie_hash = None
        file_size = None

        if video_url:
            from common.utils import FileHashUtils

            try:
                video_path = Path(video_url)
                if video_path.exists() and video_path.is_file():
                    logger.info("📁 Local file detected, calculating hash...")
                    hash_result = FileHashUtils.calculate_opensubtitles_hash(
                        str(video_path)
                    )
                    if hash_result:
                        movie_hash, file_size = hash_result
                        logger.info(
                            f"📊 Calculated file hash: {movie_hash} (size: {file_size} bytes)"
                        )
                    else:
                        logger.debug(f"Could not calculate hash for: {video_url}")
                else:
                    logger.debug(
                        f"video_url is not a local file, skipping hash: {video_url}"
                    )
            except Exception as e:
                logger.debug(f"Error checking/hashing file path: {e}")

        try:
            # Try hash-based search first if available
            # Note: All OpenSubtitles API calls include automatic retry with exponential backoff
            search_results = []

            if movie_hash:
                logger.info(f"🔍 Searching by file hash: {movie_hash}")
                search_results = await opensubtitles_client.search_subtitles_by_hash(
                    movie_hash=movie_hash,
                    file_size=file_size,
                    languages=[language] if language else None,
                )

                if search_results:
                    logger.info(
                        f"✅ Found {len(search_results)} subtitle(s) by hash search"
                    )
                else:
                    logger.info("⚠️  No results by hash, falling back to query search")

            # Fallback to query search if hash search returned no results
            if not search_results:
                logger.info(
                    f"🔍 Searching by metadata: title={video_title}, imdb_id={imdb_id}"
                )
                search_results = await opensubtitles_client.search_subtitles(
                    imdb_id=imdb_id,
                    query=video_title,
                    languages=[language] if language else None,
                )

            if search_results:
                # Subtitle found - download it
                logger.info(f"✅ Found {len(search_results)} subtitle(s)")
                best_result = search_results[0]

                # Get subtitle ID from XML-RPC result
                subtitle_id = best_result.get("IDSubtitleFile")

                # Determine output path based on video location
                output_path = PathUtils.generate_subtitle_path_from_video(
                    video_url, language
                )

                if not output_path:
                    # video_url is not a local file - cannot save to video directory
                    logger.error(
                        f"❌ Cannot save subtitle: video_url is not a local file path: {video_url}"
                    )

                    if request_id:
                        event = SubtitleEvent(
                            event_type=EventType.JOB_FAILED,
                            job_id=request_id,
                            timestamp=DateTimeUtils.get_current_utc_datetime(),
                            source="downloader",
                            payload={
                                "error_message": "Cannot save subtitle: video is not a local file",
                                "error_type": "invalid_video_path",
                                "video_url": video_url,
                            },
                        )
                        await event_publisher.publish_event(event)

                    logger.info(
                        "✅ Message processed (skipped due to invalid video path)"
                    )
                else:
                    logger.info(f"📁 Will save subtitle to: {output_path}")

                    # Ensure parent directory exists
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    # Download subtitle to calculated path
                    subtitle_path = await opensubtitles_client.download_subtitle(
                        subtitle_id=str(subtitle_id),
                        output_path=output_path,
                    )

                    if request_id:
                        # Subtitle downloaded successfully - publish SUBTITLE_READY event
                        event = SubtitleEvent(
                            event_type=EventType.SUBTITLE_READY,
                            job_id=request_id,
                            timestamp=DateTimeUtils.get_current_utc_datetime(),
                            source="downloader",
                            payload={
                                "subtitle_path": str(subtitle_path),
                                "language": language,
                                "download_url": f"file://{subtitle_path}",
                                "source": "opensubtitles",
                            },
                        )
                        await event_publisher.publish_event(event)

                        logger.info(
                            f"✅ Subtitle downloaded! Published SUBTITLE_READY event for job {request_id}"
                        )
            else:
                # Subtitle not found in requested language - try fallback search
                logger.warning(
                    f"⚠️  No subtitle found for language '{language}' for job {request_id}"
                )

                if request_id:
                    # Check if auto-translate is enabled
                    if settings.jellyfin_auto_translate:
                        # Translation enabled - search for fallback subtitle
                        logger.info(
                            f"🔍 Translation enabled, searching for fallback subtitle for job {request_id}"
                        )

                        # Try to find fallback subtitle (prefer fallback language, then any language)
                        fallback_language = settings.subtitle_fallback_language
                        fallback_search_results = []

                        # Step 1: Search for default source language (usually English)
                        logger.info(
                            f"🔍 Searching for fallback subtitle in language: {fallback_language}"
                        )

                        # Try hash-based search with fallback language
                        if movie_hash:
                            logger.info(
                                f"🔍 Searching by hash for fallback language: {fallback_language}"
                            )
                            fallback_search_results = (
                                await opensubtitles_client.search_subtitles_by_hash(
                                    movie_hash=movie_hash,
                                    file_size=file_size,
                                    languages=[fallback_language],
                                )
                            )

                        # If no results, try metadata search with fallback language
                        if not fallback_search_results:
                            logger.info(
                                f"🔍 Searching by metadata for fallback language: {fallback_language}"
                            )
                            fallback_search_results = (
                                await opensubtitles_client.search_subtitles(
                                    imdb_id=imdb_id,
                                    query=video_title,
                                    languages=[fallback_language],
                                )
                            )

                        # Step 2: If still no results, search for ANY language
                        if not fallback_search_results:
                            logger.info(
                                "🔍 No subtitle found in default language, searching for ANY available language"
                            )
                            if movie_hash:
                                fallback_search_results = (
                                    await opensubtitles_client.search_subtitles_by_hash(
                                        movie_hash=movie_hash,
                                        file_size=file_size,
                                        languages=None,  # Search all languages
                                    )
                                )

                            if not fallback_search_results:
                                fallback_search_results = (
                                    await opensubtitles_client.search_subtitles(
                                        imdb_id=imdb_id,
                                        query=video_title,
                                        languages=None,  # Search all languages
                                    )
                                )

                        if fallback_search_results:
                            # Found a fallback subtitle - download it
                            logger.info(
                                f"✅ Found {len(fallback_search_results)} fallback subtitle(s)"
                            )
                            best_fallback = fallback_search_results[0]

                            # Extract actual language from API response and convert to ISO
                            opensubtitles_language_code = best_fallback.get(
                                "SubLanguageID", fallback_language
                            )
                            iso_language_code = LanguageUtils.opensubtitles_to_iso(
                                opensubtitles_language_code
                            )
                            subtitle_id = best_fallback.get("IDSubtitleFile")

                            logger.info(
                                f"📥 Found subtitle in language '{opensubtitles_language_code}' "
                                f"(ISO: '{iso_language_code}'), downloading..."
                            )

                            # Determine output path - save with the found language code
                            output_path = PathUtils.generate_subtitle_path_from_video(
                                video_url, iso_language_code
                            )

                            if not output_path:
                                # video_url is not a local file - cannot save to video directory
                                logger.error(
                                    f"❌ Cannot save fallback subtitle: video_url is not a local file path: {video_url}"
                                )
                                event = SubtitleEvent(
                                    event_type=EventType.JOB_FAILED,
                                    job_id=request_id,
                                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                                    source="downloader",
                                    payload={
                                        "error_message": "Cannot save subtitle: video is not a local file",
                                        "error_type": "invalid_video_path",
                                        "video_url": video_url,
                                    },
                                )
                                await event_publisher.publish_event(event)
                            else:
                                logger.info(
                                    f"📁 Will save fallback subtitle to: {output_path}"
                                )

                                # Ensure parent directory exists
                                output_path.parent.mkdir(parents=True, exist_ok=True)

                                # Download the fallback subtitle
                                subtitle_path = (
                                    await opensubtitles_client.download_subtitle(
                                        subtitle_id=str(subtitle_id),
                                        output_path=output_path,
                                    )
                                )

                                logger.info(
                                    f"✅ Downloaded fallback subtitle in '{iso_language_code}' to: {subtitle_path}"
                                )

                                # Validate file exists before creating translation task
                                if not subtitle_path.exists():
                                    error_msg = f"Downloaded subtitle file not found: {subtitle_path}"
                                    logger.error(f"❌ {error_msg}")
                                    event = SubtitleEvent(
                                        event_type=EventType.JOB_FAILED,
                                        job_id=request_id,
                                        timestamp=DateTimeUtils.get_current_utc_datetime(),
                                        source="downloader",
                                        payload={
                                            "error_message": error_msg,
                                            "error_type": "file_not_found",
                                            "subtitle_file_path": str(subtitle_path),
                                        },
                                    )
                                    await event_publisher.publish_event(event)
                                else:
                                    # Enqueue TranslationTask directly to translation queue
                                    # Convert target language to ISO format if needed
                                    target_language_iso = (
                                        LanguageUtils.opensubtitles_to_iso(language)
                                    )
                                    translation_task = TranslationTask(
                                        request_id=request_id,
                                        subtitle_file_path=str(subtitle_path),
                                        source_language=iso_language_code,  # Actual fallback language (ISO)
                                        target_language=target_language_iso,  # Originally requested (ISO)
                                    )

                                    task_message = Message(
                                        body=translation_task.model_dump_json().encode(),
                                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                    )

                                    try:
                                        await channel.default_exchange.publish(
                                            task_message,
                                            routing_key=settings.rabbitmq_translation_queue_routing_key,
                                        )

                                        logger.info(
                                            f"📤 Enqueued translation task to "
                                            f"{settings.rabbitmq_translation_queue_routing_key} queue "
                                            f"for job {request_id} "
                                            f"(source: {iso_language_code} -> target: {target_language_iso})"
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"❌ Failed to enqueue translation task for job {request_id}: {e}",
                                            exc_info=True,
                                        )
                                        # Publish JOB_FAILED event since we can't enqueue the task
                                        event = SubtitleEvent(
                                            event_type=EventType.JOB_FAILED,
                                            job_id=request_id,
                                            timestamp=DateTimeUtils.get_current_utc_datetime(),
                                            source="downloader",
                                            payload={
                                                "error_message": f"Failed to enqueue translation task: {str(e)}",
                                                "error_type": "queue_publish_failed",
                                                "subtitle_file_path": str(
                                                    subtitle_path
                                                ),
                                            },
                                        )
                                        await event_publisher.publish_event(event)
                                        # Re-raise to trigger message retry/nack
                                        raise

                                    # Publish SUBTITLE_TRANSLATE_REQUESTED event (for observability only)
                                    # This event is informational and does not trigger task creation
                                    event = SubtitleEvent(
                                        event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
                                        job_id=request_id,
                                        timestamp=DateTimeUtils.get_current_utc_datetime(),
                                        source="downloader",
                                        payload={
                                            "subtitle_file_path": str(subtitle_path),
                                            "source_language": iso_language_code,
                                            "target_language": target_language_iso,
                                            "reason": "subtitle_not_found_in_target_language",
                                        },
                                    )
                                    await event_publisher.publish_event(event)
                                    logger.info(
                                        f"📤 Published SUBTITLE_TRANSLATE_REQUESTED "
                                        f"event for job {request_id} (observability only)"
                                    )
                        else:
                            # No subtitle found in ANY language - publish SUBTITLE_MISSING
                            logger.warning(
                                f"❌ No subtitle found in any language for job {request_id}"
                            )
                            event = SubtitleEvent(
                                event_type=EventType.SUBTITLE_MISSING,
                                job_id=request_id,
                                timestamp=DateTimeUtils.get_current_utc_datetime(),
                                source="downloader",
                                payload={
                                    "language": language,
                                    "reason": "subtitle_not_found_any_language",
                                    "video_url": video_url,
                                    "video_title": video_title,
                                },
                            )
                            await event_publisher.publish_event(event)
                            logger.info(
                                f"📤 Published SUBTITLE_MISSING event for job {request_id}"
                            )
                    else:
                        # Translation disabled - publish SUBTITLE_MISSING
                        logger.warning(
                            f"❌ Translation disabled, publishing SUBTITLE_MISSING for job {request_id}"
                        )
                        event = SubtitleEvent(
                            event_type=EventType.SUBTITLE_MISSING,
                            job_id=request_id,
                            timestamp=DateTimeUtils.get_current_utc_datetime(),
                            source="downloader",
                            payload={
                                "language": language,
                                "reason": "subtitle_not_found_no_translation",
                                "video_url": video_url,
                                "video_title": video_title,
                            },
                        )
                        await event_publisher.publish_event(event)
                        logger.info(
                            f"📤 Published SUBTITLE_MISSING event for job {request_id}"
                        )

        except OpenSubtitlesRateLimitError as e:
            logger.error(f"⚠️  Rate limit exceeded: {e}")
            if request_id:
                event = SubtitleEvent(
                    event_type=EventType.JOB_FAILED,
                    job_id=request_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="downloader",
                    payload={
                        "error_message": "OpenSubtitles rate limit exceeded, please try again later",
                        "error_type": "rate_limit",
                    },
                )
                await event_publisher.publish_event(event)

        except (OpenSubtitlesAPIError, OpenSubtitlesAuthenticationError) as e:
            logger.error(f"❌ OpenSubtitles API error: {e}")
            logger.warning(
                f"⚠️  API error occurred, falling back to translation for job {request_id}. "
                f"Note: This is a fallback scenario - no subtitle was downloaded."
            )

            if request_id:
                # Fallback to translation on API errors
                # Note: In this case, we cannot download a subtitle due to API error,
                # so we use a placeholder path. The translator will need to handle this case.
                # This is a fallback scenario when the API is unavailable.
                # Convert target language to ISO format
                target_language_iso = LanguageUtils.opensubtitles_to_iso(language)
                event = SubtitleEvent(
                    event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
                    job_id=request_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="downloader",
                    payload={
                        "subtitle_file_path": f"/subtitles/fallback_{request_id}.en.srt",
                        "source_language": settings.subtitle_fallback_language,
                        "target_language": target_language_iso,
                        "reason": "api_error_fallback",
                        "error_note": "Subtitle file not available due to API error - this is a fallback scenario",
                    },
                )
                await event_publisher.publish_event(event)

                logger.warning(
                    f"📤 Published SUBTITLE_TRANSLATE_REQUESTED event for job {request_id} "
                    f"(fallback scenario - API error prevented subtitle download)"
                )

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
    """Consume messages from the subtitle download queue with automatic reconnection."""
    connection = None
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

            # Connect OpenSubtitles client
            logger.info("🔌 Connecting to OpenSubtitles API...")
            await opensubtitles_client.connect()

            # Connect to RabbitMQ
            logger.info("🔌 Connecting to RabbitMQ...")
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)

            # Create channel
            channel = await connection.channel()

            # Set QoS to process one message at a time
            await channel.set_qos(prefetch_count=1)

            # Declare the queue
            queue_name = "subtitle.download"
            logger.info(f"📋 Declaring queue: {queue_name}")
            queue = await channel.declare_queue(queue_name, durable=True)

            # Reset failure counter on successful connection
            consecutive_failures = 0
            reconnect_delay = settings.rabbitmq_reconnect_initial_delay

            logger.info("🎧 Starting to consume messages...")
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
                            "downloader",
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
                        await process_message(message, channel)

        except KeyboardInterrupt:
            logger.info("🛑 Received interrupt signal, shutting down...")
            should_stop = True
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"❌ Error in consumer (failure #{consecutive_failures}): {e}")
            
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
                logger.info("🔌 Disconnecting OpenSubtitles client...")
                await opensubtitles_client.disconnect()

                logger.info("🔌 Disconnecting event publisher...")
                await event_publisher.disconnect()

                if connection and not connection.is_closed:
                    logger.info("🔌 Closing RabbitMQ connection...")
                    await connection.close()
                logger.info("🔌 Closing Redis connection...")
                await redis_client.disconnect()
                break


async def main() -> None:
    """Main entry point for the downloader worker."""
    logger.info("🚀 Starting Subtitle Downloader Worker")
    logger.info("This worker will consume download tasks and publish events")
    logger.info("=" * 60)

    await consume_messages()


if __name__ == "__main__":
    asyncio.run(main())
