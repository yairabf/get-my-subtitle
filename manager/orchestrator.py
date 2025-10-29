"""Orchestrator for managing subtitle processing workflow."""

import json
import logging
from typing import Optional
from uuid import UUID

import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractChannel, AbstractConnection

from common.config import settings
from common.event_publisher import event_publisher
from common.redis_client import redis_client
from common.schemas import (DownloadTask, EventType, SubtitleEvent,
                            SubtitleRequest, SubtitleStatus, TranslationTask)
from common.utils import DateTimeUtils

logger = logging.getLogger(__name__)


class SubtitleOrchestrator:
    """Orchestrates subtitle processing workflow using RabbitMQ."""

    def __init__(self):
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.download_queue_name = "subtitle.download"
        self.translation_queue_name = "subtitle.translation"

    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            self.channel = await self.connection.channel()

            # Declare queues
            await self._declare_queues()

            # Connect event publisher
            await event_publisher.connect()

            logger.info("Connected to RabbitMQ successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to RabbitMQ: {e}")
            logger.warning(
                "Running in mock mode - messages will be logged but not queued"
            )
            # Don't raise the exception, allow the app to start in mock mode

    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        # Disconnect event publisher
        await event_publisher.disconnect()
        
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")

    async def _declare_queues(self) -> None:
        """Declare required queues."""
        if not self.channel:
            raise RuntimeError("Channel not initialized")

        # Declare download queue
        await self.channel.declare_queue(self.download_queue_name, durable=True)

        # Declare translation queue
        await self.channel.declare_queue(self.translation_queue_name, durable=True)

        logger.info("Queues declared successfully")

    async def enqueue_download_task(
        self, request: SubtitleRequest, request_id: UUID
    ) -> bool:
        """
        Enqueue a subtitle download task.

        Args:
            request: Subtitle request containing video and language information
            request_id: Unique identifier for this request

        Returns:
            True if task was successfully enqueued, False otherwise
        """
        if not self.channel:
            logger.warning(
                f"Mock mode: Would enqueue download task for request {request_id}"
            )
            logger.warning(f"Task data: {request.model_dump()}")
            return True

        try:
            download_task = DownloadTask(
                request_id=request_id,
                video_url=request.video_url,
                video_title=request.video_title,
                language=request.language,
                preferred_sources=request.preferred_sources,
            )

            message = Message(
                body=download_task.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )

            await self.channel.default_exchange.publish(
                message, routing_key=self.download_queue_name
            )

            # Publish event for download request
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={
                    "video_url": request.video_url,
                    "video_title": request.video_title,
                    "language": request.language,
                    "target_language": request.target_language,
                    "preferred_sources": request.preferred_sources,
                },
            )
            await event_publisher.publish_event(event)

            # Update job status to DOWNLOAD_QUEUED in Redis
            await redis_client.update_phase(
                request_id, SubtitleStatus.DOWNLOAD_QUEUED, source="manager"
            )

            logger.info(f"Download task enqueued for request {request_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to enqueue download task: {e}")
            return False

    async def enqueue_translation_task(
        self,
        request_id: UUID,
        subtitle_file_path: str,
        source_language: str,
        target_language: str,
    ) -> bool:
        """
        Enqueue a subtitle translation task.

        Args:
            request_id: Unique identifier for the original request
            subtitle_file_path: Path to the downloaded subtitle file
            source_language: Source language code (e.g., 'en')
            target_language: Target language code (e.g., 'es')

        Returns:
            True if task was successfully enqueued, False otherwise
        """
        if not self.channel:
            logger.warning(
                f"Mock mode: Would enqueue translation task for request {request_id}"
            )
            logger.warning(
                f"Task data: file={subtitle_file_path}, source={source_language}, target={target_language}"
            )
            return True

        try:
            translation_task = TranslationTask(
                request_id=request_id,
                subtitle_file_path=subtitle_file_path,
                source_language=source_language,
                target_language=target_language,
            )

            message = Message(
                body=translation_task.model_dump_json().encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )

            await self.channel.default_exchange.publish(
                message, routing_key=self.translation_queue_name
            )

            # Publish event for translation request
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
                job_id=request_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={
                    "subtitle_file_path": subtitle_file_path,
                    "source_language": source_language,
                    "target_language": target_language,
                },
            )
            await event_publisher.publish_event(event)

            # Update job status to TRANSLATE_QUEUED in Redis
            await redis_client.update_phase(
                request_id, SubtitleStatus.TRANSLATE_QUEUED, source="manager"
            )

            logger.info(f"Translation task enqueued for request {request_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to enqueue translation task: {e}")
            return False

    async def enqueue_download_with_translation(
        self, request: SubtitleRequest, request_id: UUID
    ) -> bool:
        """
        Enqueue a download task that will automatically trigger translation.

        This is used for Jellyfin webhook integration where we want to
        automatically download and then translate subtitles.

        Args:
            request: Subtitle request containing video and language information
            request_id: Unique identifier for this request

        Returns:
            True if task was successfully enqueued, False otherwise
        """
        # Enqueue the download task - the downloader worker will check for
        # target_language and automatically enqueue translation when complete
        return await self.enqueue_download_task(request, request_id)

    async def get_queue_status(self) -> dict:
        """Get status of processing queues."""
        if not self.channel:
            logger.warning("Mock mode: Returning mock queue status")
            return {
                "download_queue_size": 0,
                "translation_queue_size": 0,
                "active_workers": {"downloader": 0, "translator": 0},
            }

        try:
            download_queue = await self.channel.declare_queue(
                self.download_queue_name, passive=True
            )
            translation_queue = await self.channel.declare_queue(
                self.translation_queue_name, passive=True
            )

            return {
                "download_queue_size": download_queue.declaration_result.message_count,
                "translation_queue_size": translation_queue.declaration_result.message_count,
                "active_workers": {
                    "downloader": 0,  # This would be tracked by worker registration
                    "translator": 0,  # This would be tracked by worker registration
                },
            }
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {
                "download_queue_size": 0,
                "translation_queue_size": 0,
                "active_workers": {"downloader": 0, "translator": 0},
            }


# Global orchestrator instance
orchestrator = SubtitleOrchestrator()
