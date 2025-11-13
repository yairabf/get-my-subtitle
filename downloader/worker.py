"""Downloader worker for consuming download tasks and publishing events."""

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
from common.utils import DateTimeUtils, PathUtils  # noqa: E402
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
                # Subtitle not found - check if translation is enabled
                logger.warning(f"⚠️  No subtitle found for job {request_id}")

                if request_id:
                    # Check if auto-translate is enabled
                    if settings.jellyfin_auto_translate:
                        # Translation enabled - request fallback translation
                        logger.info(
                            f"📤 Translation enabled, requesting translation for job {request_id}"
                        )
                        event = SubtitleEvent(
                            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
                            job_id=request_id,
                            timestamp=DateTimeUtils.get_current_utc_datetime(),
                            source="downloader",
                            payload={
                                "subtitle_file_path": f"/subtitles/fallback_{request_id}.en.srt",
                                "source_language": "en",
                                "target_language": language,
                                "reason": "subtitle_not_found",
                            },
                        )
                        await event_publisher.publish_event(event)
                        logger.info(
                            f"📤 Published SUBTITLE_TRANSLATE_REQUESTED event for job {request_id}"
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
            logger.warning(f"⚠️  Falling back to translation for job {request_id}")

            if request_id:
                # Fallback to translation on API errors
                event = SubtitleEvent(
                    event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
                    job_id=request_id,
                    timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="downloader",
                    payload={
                        "subtitle_file_path": f"/subtitles/fallback_{request_id}.en.srt",
                        "source_language": "en",
                        "target_language": language,
                        "reason": "api_error",
                    },
                )
                await event_publisher.publish_event(event)

                logger.info(
                    f"📤 Published SUBTITLE_TRANSLATE_REQUESTED event for job {request_id}"
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
    """Consume messages from the subtitle download queue."""
    connection = None

    try:
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
        logger.info("🔌 Disconnecting OpenSubtitles client...")
        await opensubtitles_client.disconnect()

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
