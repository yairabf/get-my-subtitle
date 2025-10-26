"""Translator worker for subtitle translation using OpenAI GPT-5-nano."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from openai import AsyncOpenAI

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import SubtitleStatus
from common.subtitle_parser import (DEFAULT_MAX_SEGMENTS_PER_CHUNK, SRTParser,
                                    SubtitleSegment, chunk_segments,
                                    extract_text_for_translation,
                                    merge_translations)

# Configure logging
service_logger = setup_service_logging("translator", enable_file_logging=True)
logger = service_logger.logger


class SubtitleTranslator:
    """Handles subtitle translation using OpenAI GPT-5-nano."""

    def __init__(self):
        """Initialize the translator with OpenAI async client."""
        self.client = None
        if settings.openai_api_key:
            # Initialize AsyncOpenAI client with proper configuration
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=60.0,  # 60 second timeout for translation requests
                max_retries=2,  # Retry failed requests up to 2 times
            )
            logger.info(
                f"Initialized OpenAI async client with model: {settings.openai_model}"
            )
        else:
            logger.warning(
                "OpenAI API key not configured - translator will run in mock mode"
            )

    async def translate_batch(
        self, texts: List[str], source_language: str, target_language: str
    ) -> List[str]:
        """
        Translate a batch of subtitle texts using GPT-5-nano.

        Args:
            texts: List of subtitle text strings to translate
            source_language: Source language code (e.g., 'en')
            target_language: Target language code (e.g., 'es')

        Returns:
            List of translated text strings
        """
        if not self.client:
            logger.warning(
                "Mock mode: Returning original texts with [TRANSLATED] prefix"
            )
            return [f"[TRANSLATED to {target_language}] {text}" for text in texts]

        try:
            # Prepare the prompt for GPT-5-nano
            prompt = self._build_translation_prompt(
                texts, source_language, target_language
            )

            logger.info(
                f"Translating {len(texts)} segments from {source_language} to {target_language}"
            )

            # Call OpenAI Chat Completions API with proper async configuration
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a professional subtitle translator. "
                            f"Translate subtitles from {source_language} to {target_language}. "
                            f"Maintain the same tone, style, and timing suitability. "
                            f"Keep translations concise for subtitle display. "
                            f"Preserve formatting like line breaks."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens,
                timeout=60.0,  # Per-request timeout override
            )

            # Parse the response
            translations = self._parse_translation_response(
                response.choices[0].message.content, len(texts)
            )

            logger.info(f"Successfully translated {len(translations)} segments")
            return translations

        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise

    def _build_translation_prompt(
        self, texts: List[str], source_language: str, target_language: str
    ) -> str:
        """
        Build the translation prompt for GPT-5-nano.

        Args:
            texts: List of texts to translate
            source_language: Source language code
            target_language: Target language code

        Returns:
            Formatted prompt string
        """
        # Number each text for easy parsing
        numbered_texts = []
        for i, text in enumerate(texts, 1):
            numbered_texts.append(f"[{i}]\n{text}")

        prompt = (
            f"Translate the following {len(texts)} subtitle segments "
            f"from {source_language} to {target_language}.\n\n"
            f"Return ONLY the translations, numbered the same way, "
            f"with no additional commentary.\n\n"
            f"Format your response exactly like this:\n"
            f"[1]\nTranslated text\n\n"
            f"[2]\nTranslated text\n\n"
            f"etc.\n\n"
            f"Subtitles to translate:\n\n" + "\n\n".join(numbered_texts)
        )

        return prompt

    def _parse_translation_response(
        self, response: str, expected_count: int
    ) -> List[str]:
        """
        Parse GPT-5-nano's translation response.

        Args:
            response: Raw response from GPT-5-nano
            expected_count: Expected number of translations

        Returns:
            List of translated texts
        """
        translations = []

        # Split by numbered segments
        segments = response.split("[")

        for segment in segments:
            if not segment.strip():
                continue

            # Extract number and text
            parts = segment.split("]", 1)
            if len(parts) == 2:
                try:
                    number = int(parts[0].strip())
                    text = parts[1].strip()
                    translations.append(text)
                except ValueError:
                    continue

        if len(translations) != expected_count:
            logger.warning(
                f"Expected {expected_count} translations but got {len(translations)}"
            )

        return translations


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

        # Read subtitle file
        logger.info(f"Reading subtitle file: {subtitle_file_path}")

        # For now, simulate reading a file (in production, read from storage)
        # You would replace this with actual file reading from settings.subtitle_storage_path
        sample_srt_content = """1
00:00:01,000 --> 00:00:04,000
Welcome to this video

2
00:00:04,500 --> 00:00:08,000
Today we're going to learn something new

3
00:00:08,500 --> 00:00:12,000
Let's get started!
"""

        # Parse SRT content
        logger.info("Parsing SRT content...")
        segments = SRTParser.parse(sample_srt_content)

        if not segments:
            raise ValueError("No subtitle segments found in file")

        logger.info(f"Parsed {len(segments)} subtitle segments")

        # Split into chunks for API limits
        chunks = chunk_segments(segments, max_segments=DEFAULT_MAX_SEGMENTS_PER_CHUNK)

        all_translated_segments = []

        # Translate each chunk
        for chunk_idx, chunk in enumerate(chunks, 1):
            logger.info(
                f"Translating chunk {chunk_idx}/{len(chunks)} ({len(chunk)} segments)"
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

        # Format back to SRT
        translated_srt = SRTParser.format(all_translated_segments)

        # Save translated file (in production, save to storage)
        output_path = f"{subtitle_file_path.replace('.srt', '')}.{target_language}.srt"
        logger.info(f"Would save translated subtitle to: {output_path}")

        # Update job status to COMPLETED in Redis
        if request_id:
            success = await redis_client.update_job_status(
                request_id,
                SubtitleStatus.COMPLETED,
                download_url=f"https://example.com/subtitles/{request_id}.{target_language}.srt",
            )

            if success:
                logger.info(f"✅ Updated job {request_id} status to COMPLETED in Redis")
            else:
                logger.warning(f"⚠️  Failed to update job {request_id} in Redis")

        logger.info("✅ Translation completed successfully!")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON: {e}")
        logger.error(f"Raw body: {message.body}")
        if request_id:
            await redis_client.update_job_status(
                request_id,
                SubtitleStatus.FAILED,
                error_message=f"Failed to parse message: {str(e)}",
            )

    except Exception as e:
        logger.error(f"❌ Error processing translation: {e}")
        if request_id:
            await redis_client.update_job_status(
                request_id,
                SubtitleStatus.FAILED,
                error_message=f"Translation error: {str(e)}",
            )


async def consume_translation_messages() -> None:
    """Consume translation messages from the RabbitMQ queue."""
    connection = None
    translator = SubtitleTranslator()

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
        if connection and not connection.is_closed:
            logger.info("🔌 Closing RabbitMQ connection...")
            await connection.close()
        logger.info("🔌 Closing Redis connection...")
        await redis_client.disconnect()


async def main() -> None:
    """Main entry point for the translator worker."""
    logger.info("🚀 Starting Subtitle Translator Worker")
    logger.info(f"🤖 Using model: {settings.openai_model}")
    logger.info("=" * 60)

    await consume_translation_messages()


if __name__ == "__main__":
    asyncio.run(main())
