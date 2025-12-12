"""Event publishing and finalization helpers for translation tasks."""

import logging
from pathlib import Path
from uuid import UUID

from common.config import settings
from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils, URLUtils
from translator.checkpoint_manager import CheckpointManager
from translator.schemas import TranslationTaskData

logger = logging.getLogger(__name__)


async def publish_translation_events(
    request_id: UUID,
    output_path: Path,
    source_language: str,
    target_language: str,
    duration_seconds: float,
    subtitle_file_path: str,
    download_url: str,
) -> None:
    """
    Publish all translation-related events.

    Args:
        request_id: Unique identifier for the translation request
        output_path: Path to translated subtitle file
        source_language: Source language code
        target_language: Target language code
        duration_seconds: Translation duration in seconds
        subtitle_file_path: Path to source subtitle file
        download_url: Download URL for translated subtitle
    """
    # Publish TRANSLATION_COMPLETED event
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
    subtitle_translated_event = SubtitleEvent(
        event_type=EventType.SUBTITLE_TRANSLATED,
        job_id=request_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="translator",
        payload={
            "translated_path": str(output_path),
            "source_language": source_language,
            "target_language": target_language,
            "download_url": download_url,
        },
    )
    await event_publisher.publish_event(subtitle_translated_event)

    logger.info(f"✅ Published SUBTITLE_TRANSLATED event for job {request_id}")


async def finalize_translation(
    request_id: UUID,
    output_path: Path,
    task_data: TranslationTaskData,
    duration_seconds: float,
) -> None:
    """
    Finalize translation by updating status and publishing events.

    Args:
        request_id: Unique identifier for the translation request
        output_path: Path to translated subtitle file
        task_data: Translation task data
        duration_seconds: Translation duration in seconds
    """
    # Generate download URL
    download_url = URLUtils.generate_download_url(
        request_id, task_data.target_language, settings.download_base_url
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
            checkpoint_manager = CheckpointManager()
            await checkpoint_manager.cleanup_checkpoint(
                request_id, task_data.target_language
            )
        except Exception as e:
            logger.warning(f"⚠️  Failed to cleanup checkpoint after completion: {e}")

    # Publish translation events
    await publish_translation_events(
        request_id=request_id,
        output_path=output_path,
        source_language=task_data.source_language,
        target_language=task_data.target_language,
        duration_seconds=duration_seconds,
        subtitle_file_path=task_data.subtitle_file_path,
        download_url=download_url,
    )




