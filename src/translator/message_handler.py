"""Message parsing and validation for translation tasks."""

import json
import logging
from uuid import UUID

from aio_pika.abc import AbstractIncomingMessage

from common.schemas import TranslationCheckpoint
from common.utils import LanguageUtils
from translator.schemas import TranslationTaskData

logger = logging.getLogger(__name__)


async def parse_and_validate_message(
    message: AbstractIncomingMessage,
) -> TranslationTaskData:
    """
    Parse and validate translation task message.

    Args:
        message: RabbitMQ message containing translation task

    Returns:
        TranslationTaskData object with parsed task information

    Raises:
        ValueError: If message is invalid or missing required fields
        json.JSONDecodeError: If message body is not valid JSON
    """
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

    return TranslationTaskData(
        request_id=request_id,
        subtitle_file_path=subtitle_file_path,
        source_language=source_language,
        target_language=target_language,
    )


def validate_checkpoint_metadata(
    checkpoint: TranslationCheckpoint,
    subtitle_file_path: str,
    source_language: str,
    target_language: str,
) -> bool:
    """
    Validate checkpoint metadata matches current request.

    Args:
        checkpoint: TranslationCheckpoint to validate
        subtitle_file_path: Expected subtitle file path
        source_language: Expected source language code
        target_language: Expected target language code

    Returns:
        True if checkpoint metadata matches, False otherwise
    """
    return (
        checkpoint.subtitle_file_path == subtitle_file_path
        and checkpoint.source_language == source_language
        and checkpoint.target_language == target_language
    )


