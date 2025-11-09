"""Scanner worker for monitoring media files and triggering subtitle processing."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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
from manager.orchestrator import orchestrator

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger


class MediaFileEventHandler(FileSystemEventHandler):
    """Event handler for media file detection with debouncing."""

    def __init__(self, scanner_instance):
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

            # Store job in Redis
            await redis_client.save_job(subtitle_response)

            logger.info(f"✅ Created job {subtitle_response.id} for {video_title}")

            # Publish MEDIA_FILE_DETECTED event
            event = SubtitleEvent(
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
            await event_publisher.publish_event(event)

            # Enqueue download task
            if settings.scanner_auto_translate and subtitle_request.target_language:
                success = await orchestrator.enqueue_download_with_translation(
                    subtitle_request, subtitle_response.id
                )
            else:
                success = await orchestrator.enqueue_download_task(
                    subtitle_request, subtitle_response.id
                )

            if not success:
                logger.error(
                    f"Failed to enqueue download task for job {subtitle_response.id}"
                )
                await redis_client.update_phase(
                    subtitle_response.id,
                    SubtitleStatus.FAILED,
                    source="scanner",
                    metadata={"error_message": "Failed to enqueue download task"},
                )
            else:
                logger.info(
                    f"✅ Successfully enqueued download task for job {subtitle_response.id}"
                )

        except Exception as e:
            logger.error(f"❌ Error processing media file {file_path}: {e}", exc_info=True)

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
            file_path
            for file_path, task in self.pending_files.items()
            if task.done()
        ]
        for file_path in completed:
            del self.pending_files[file_path]


class MediaScanner:
    """Media file scanner that monitors directory for new/updated files."""

    def __init__(self):
        """Initialize the media scanner."""
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[MediaFileEventHandler] = None
        self.running = False

    async def connect(self) -> None:
        """Connect to Redis, RabbitMQ, and orchestrator."""
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()

        logger.info("🔌 Connecting to RabbitMQ...")
        await orchestrator.connect()

        logger.info("🔌 Connecting to event publisher...")
        await event_publisher.connect()

        logger.info("✅ All connections established")

    async def disconnect(self) -> None:
        """Disconnect from services."""
        logger.info("🔌 Disconnecting from services...")
        await orchestrator.disconnect()
        await event_publisher.disconnect()
        await redis_client.disconnect()
        logger.info("✅ All connections closed")

    def start(self) -> None:
        """Start the file system observer."""
        if self.running:
            logger.warning("Scanner is already running")
            return

        media_path = Path(settings.scanner_media_path)

        if not media_path.exists():
            logger.error(f"Media path does not exist: {media_path}")
            raise FileNotFoundError(f"Media path does not exist: {media_path}")

        if not media_path.is_dir():
            logger.error(f"Media path is not a directory: {media_path}")
            raise ValueError(f"Media path is not a directory: {media_path}")

        logger.info(f"📂 Starting file system watcher on: {media_path}")
        logger.info(f"   Recursive: {settings.scanner_watch_recursive}")
        logger.info(f"   Extensions: {settings.scanner_media_extensions}")
        logger.info(f"   Debounce: {settings.scanner_debounce_seconds}s")

        self.event_handler = MediaFileEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler, str(media_path), recursive=settings.scanner_watch_recursive
        )
        self.observer.start()
        self.running = True

        logger.info("✅ File system watcher started")

    def stop(self) -> None:
        """Stop the file system observer."""
        if not self.running:
            return

        logger.info("🛑 Stopping file system watcher...")

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)

        self.running = False
        logger.info("✅ File system watcher stopped")

    def is_running(self) -> bool:
        """
        Check if scanner is running.

        Returns:
            True if scanner is running, False otherwise
        """
        return self.running


async def main() -> None:
    """Main entry point for the scanner service."""
    scanner = MediaScanner()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        scanner.stop()
        asyncio.create_task(scanner.disconnect())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Connect to services
        await scanner.connect()

        # Start file system watcher
        scanner.start()

        # Keep running until stopped
        logger.info("🚀 Scanner service running. Press Ctrl+C to stop.")
        while scanner.is_running():
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        scanner.stop()
        await scanner.disconnect()
        logger.info("👋 Scanner service stopped")


if __name__ == "__main__":
    asyncio.run(main())

