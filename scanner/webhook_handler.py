"""Webhook handler for Jellyfin notifications."""

import logging
from typing import Optional
from uuid import UUID

from common.config import settings
from common.event_publisher import event_publisher
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from common.schemas import (
    EventType,
    SubtitleEvent,
    SubtitleRequest,
    SubtitleResponse,
    SubtitleStatus,
)
from common.utils import DateTimeUtils
from manager.schemas import JellyfinWebhookPayload, WebhookAcknowledgement

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger


class JellyfinWebhookHandler:
    """Handler for processing Jellyfin webhook notifications."""

    async def process_webhook(
        self, payload: JellyfinWebhookPayload
    ) -> WebhookAcknowledgement:
        """
        Process a Jellyfin webhook notification.

        Args:
            payload: Jellyfin webhook payload

        Returns:
            Webhook acknowledgement response
        """
        try:
            logger.info(
                f"Received Jellyfin webhook: {payload.event} - {payload.item_name}"
            )

            # Only process library item added or updated events
            if payload.event not in ["library.item.added", "library.item.updated"]:
                return WebhookAcknowledgement(
                    status="ignored",
                    message=f"Event type {payload.event} is not processed",
                )

            # Only process video items
            if payload.item_type not in ["Movie", "Episode"]:
                return WebhookAcknowledgement(
                    status="ignored",
                    message=f"Item type {payload.item_type} is not a video",
                )

            # Determine video URL - prefer provided URL, fall back to path
            video_url = payload.video_url or payload.item_path or ""

            if not video_url:
                logger.warning(
                    f"No video URL or path provided for item {payload.item_name}"
                )
                return WebhookAcknowledgement(
                    status="error", message="No video URL or path provided"
                )

            # Create subtitle request with Jellyfin default settings
            subtitle_request = SubtitleRequest(
                video_url=video_url,
                video_title=payload.item_name,
                language=settings.jellyfin_default_source_language,
                target_language=settings.jellyfin_default_target_language,
                preferred_sources=["opensubtitles"],
            )

            # Create subtitle response/job
            subtitle_response = SubtitleResponse(
                video_url=subtitle_request.video_url,
                video_title=subtitle_request.video_title,
                language=subtitle_request.language,
                target_language=subtitle_request.target_language,
                status=SubtitleStatus.PENDING,
            )

            # Store job in Redis
            await redis_client.save_job(subtitle_response)

            logger.info(
                f"✅ Created job {subtitle_response.id} for {payload.item_name}"
            )

            # Publish MEDIA_FILE_DETECTED event (for observability)
            media_detected_event = SubtitleEvent(
                event_type=EventType.MEDIA_FILE_DETECTED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="scanner",
                payload={
                    "file_path": video_url,
                    "video_title": payload.item_name,
                    "video_url": video_url,
                    "language": subtitle_request.language,
                    "target_language": subtitle_request.target_language,
                    "source": "jellyfin_webhook",
                },
            )
            await event_publisher.publish_event(media_detected_event)

            # Publish SUBTITLE_REQUESTED event (for workflow triggering)
            subtitle_requested_event = SubtitleEvent(
                event_type=EventType.SUBTITLE_REQUESTED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                    source="scanner",
                payload={
                    "video_url": subtitle_request.video_url,
                    "video_title": subtitle_request.video_title,
                    "language": subtitle_request.language,
                    "target_language": subtitle_request.target_language,
                    "preferred_sources": subtitle_request.preferred_sources,
                    "auto_translate": settings.jellyfin_auto_translate
                    and subtitle_request.target_language is not None,
                },
            )
            await event_publisher.publish_event(subtitle_requested_event)

            logger.info(
                f"✅ Published SUBTITLE_REQUESTED event for job {subtitle_response.id}"
            )
            return WebhookAcknowledgement(
                status="received",
                job_id=subtitle_response.id,
                message=f"Subtitle processing queued for {payload.item_name}",
            )

        except Exception as e:
            logger.error(f"Error processing Jellyfin webhook: {e}", exc_info=True)
            return WebhookAcknowledgement(
                status="error",
                message=f"Internal server error: {str(e)}",
            )
