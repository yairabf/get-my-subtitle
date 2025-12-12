"""Error handling utilities for translation tasks."""

import json
import logging
from typing import Optional
from uuid import UUID

from common.event_publisher import event_publisher
from common.schemas import EventType, SubtitleEvent
from common.utils import DateTimeUtils

logger = logging.getLogger(__name__)


async def handle_translation_error(
    request_id: Optional[UUID], error: Exception
) -> None:
    """
    Handle translation errors by publishing JOB_FAILED event.

    Args:
        request_id: Unique identifier for the translation request (may be None)
        error: Exception that occurred during translation
    """
    error_message = str(error)

    # Log specific error types with appropriate messages
    if isinstance(error, FileNotFoundError):
        logger.error(f"❌ Subtitle file not found: {error_message}")
        error_message = f"File not found: {error_message}"
    elif isinstance(error, ValueError):
        logger.error(f"❌ Invalid translation request: {error_message}")
        error_message = f"Invalid request: {error_message}"
    elif isinstance(error, json.JSONDecodeError):
        logger.error(f"❌ Failed to parse JSON: {error_message}")
        error_message = f"Failed to parse message: {error_message}"
    else:
        logger.error(
            f"❌ Unexpected error processing translation: {error_message}",
            exc_info=True,
        )
        error_message = f"Translation error: {error_message}"

    # Publish JOB_FAILED event
    if request_id:
        event = SubtitleEvent(
            event_type=EventType.JOB_FAILED,
            job_id=request_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="translator",
            payload={"error_message": error_message},
        )
        await event_publisher.publish_event(event)




