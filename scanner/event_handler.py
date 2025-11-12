"""Event handler for media file detection with debouncing."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Dict

from watchdog.events import FileSystemEvent, FileSystemEventHandler

from common.config import settings
from common.duplicate_prevention import DuplicatePreventionService
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

if TYPE_CHECKING:
    from scanner.scanner import MediaScanner

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger

# Initialize duplicate prevention service
duplicate_prevention = DuplicatePreventionService(redis_client)


class MediaFileEventHandler(FileSystemEventHandler):
    """Event handler for media file detection with debouncing."""

    def __init__(self, scanner_instance: "MediaScanner"):
        """
        Initialize the event handler.

        Args:
            scanner_instance: MediaScanner instance to handle file processing
        """
        super().__init__()
        self.scanner = scanner_instance
        self.pending_files: Dict[str, asyncio.Task] = {}
        self.media_extensions = set(
            ext.lower() for ext in settings.scanner_media_extensions
        )

    def _is_media_file(self, file_path: str) -> bool:
        """
        Check if a file is a supported media file.

        Args:
            file_path: Path to the file

        Returns:
            True if file has a supported media extension, False otherwise
        """
        path = Path(file_path)
        if not path.is_file():
            return False

        extension = path.suffix.lower()
        return extension in self.media_extensions

    def _extract_video_title(self, file_path: str) -> str:
        """
        Extract video title from file path.

        Args:
            file_path: Path to the video file

        Returns:
            Cleaned video title
        """
        path = Path(file_path)
        # Remove extension and clean up the filename
        title = path.stem
        # Replace common separators with spaces
        title = title.replace("_", " ").replace(".", " ").replace("-", " ")
        # Clean up multiple spaces
        title = " ".join(title.split())
        return title or path.name

    async def _wait_for_file_stability(self, file_path: str) -> bool:
        """
        Wait for file size to stabilize (debouncing).

        Args:
            file_path: Path to the file

        Returns:
            True if file is stable, False if file doesn't exist or error occurred
        """
        path = Path(file_path)
        if not path.exists():
            return False

        debounce_seconds = settings.scanner_debounce_seconds
        check_interval = 0.5  # Check every 500ms
        checks_needed = int(debounce_seconds / check_interval)
        stable_checks = 0

        last_size = None

        for _ in range(checks_needed * 2):  # Max wait time is 2x debounce
            try:
                if not path.exists():
                    logger.debug(f"File disappeared: {file_path}")
                    return False

                current_size = path.stat().st_size

                if last_size is not None and current_size == last_size:
                    stable_checks += 1
                    if stable_checks >= checks_needed:
                        logger.debug(
                            f"File is stable: {file_path} (size: {current_size} bytes)"
                        )
                        return True
                else:
                    stable_checks = 0

                last_size = current_size
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.debug(f"Error checking file stability for {file_path}: {e}")
                await asyncio.sleep(check_interval)

        # If we get here, file exists but may still be changing
        # Process it anyway if it exists
        if path.exists():
            logger.info(
                f"File stability timeout, processing anyway: {file_path} "
                f"(size: {path.stat().st_size} bytes)"
            )
            return True

        return False

    async def _process_media_file(self, file_path: str) -> None:
        """
        Process a detected media file.

        Args:
            file_path: Path to the media file
        """
        try:
            logger.info(f"📁 Processing media file: {file_path}")

            # Wait for file to stabilize
            if not await self._wait_for_file_stability(file_path):
                logger.warning(f"File not stable or disappeared: {file_path}")
                return

            # Extract video title from filename
            video_title = self._extract_video_title(file_path)

            # Create subtitle request
            subtitle_request = SubtitleRequest(
                video_url=file_path,
                video_title=video_title,
                language=settings.scanner_default_source_language,
                target_language=settings.scanner_default_target_language,
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

            # Check for duplicate request before processing
            dedup_result = await duplicate_prevention.check_and_register(
                file_path, subtitle_request.language, subtitle_response.id
            )

            if dedup_result.is_duplicate:
                logger.info(
                    f"⏭️ Skipping duplicate request for {video_title} - "
                    f"already processing as job {dedup_result.existing_job_id}"
                )
                return

            # Store job in Redis
            await redis_client.save_job(subtitle_response)

            logger.info(f"✅ Created job {subtitle_response.id} for {video_title}")

            # Publish MEDIA_FILE_DETECTED event (for observability)
            media_detected_event = SubtitleEvent(
                event_type=EventType.MEDIA_FILE_DETECTED,
                job_id=subtitle_response.id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="scanner",
                payload={
                    "file_path": file_path,
                    "video_title": video_title,
                    "video_url": file_path,
                    "language": subtitle_request.language,
                    "target_language": subtitle_request.target_language,
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
                    "auto_translate": settings.scanner_auto_translate
                    and subtitle_request.target_language is not None,
                },
            )
            await event_publisher.publish_event(subtitle_requested_event)

            logger.info(
                f"✅ Published SUBTITLE_REQUESTED event for job {subtitle_response.id}"
            )

        except Exception as e:
            logger.error(
                f"❌ Error processing media file {file_path}: {e}", exc_info=True
            )

    def on_created(self, event: FileSystemEvent) -> None:
        """
        Handle file creation event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = event.src_path

        if not self._is_media_file(file_path):
            return

        logger.info(f"📥 File created: {file_path}")

        # Cancel any pending task for this file (in case of rapid create/modify)
        if file_path in self.pending_files:
            task = self.pending_files[file_path]
            if not task.done():
                task.cancel()

        # Schedule async processing
        task = asyncio.create_task(self._process_media_file(file_path))
        self.pending_files[file_path] = task

        # Clean up completed tasks
        self._cleanup_completed_tasks()

    def on_modified(self, event: FileSystemEvent) -> None:
        """
        Handle file modification event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = event.src_path

        if not self._is_media_file(file_path):
            return

        logger.debug(f"📝 File modified: {file_path}")

        # Cancel any pending task for this file
        if file_path in self.pending_files:
            task = self.pending_files[file_path]
            if not task.done():
                task.cancel()

        # Schedule async processing (treat modification as potential new file)
        task = asyncio.create_task(self._process_media_file(file_path))
        self.pending_files[file_path] = task

        # Clean up completed tasks
        self._cleanup_completed_tasks()

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from pending_files dictionary."""
        completed = [
            file_path for file_path, task in self.pending_files.items() if task.done()
        ]
        for file_path in completed:
            del self.pending_files[file_path]
