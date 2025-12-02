"""Tests for scanner's media file event handler."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from watchdog.events import FileSystemEvent

from common.schemas import EventType, SubtitleStatus
from scanner.event_handler import MediaFileEventHandler


@pytest.fixture
def mock_scanner():
    """Create a mock MediaScanner instance."""
    scanner = MagicMock()
    return scanner


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    with patch("scanner.event_handler.redis_client") as mock:
        mock.save_job = AsyncMock()
        mock.update_phase = AsyncMock()
        yield mock


@pytest.fixture
def mock_event_publisher():
    """Create mock event publisher."""
    with patch("scanner.event_handler.event_publisher") as mock:
        mock.publish_event = AsyncMock()
        yield mock


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    with patch("scanner.event_handler.settings") as mock:
        mock.subtitle_desired_language = "en"
        mock.subtitle_fallback_language = "en"
        mock.scanner_auto_translate = True
        mock.scanner_debounce_seconds = 2.0
        mock.scanner_media_extensions = {".mp4", ".mkv", ".avi"}
        yield mock


@pytest.fixture
def event_handler(mock_scanner):
    """Create MediaFileEventHandler instance."""
    return MediaFileEventHandler(mock_scanner)


class TestMediaFileEventHandler:
    """Test suite for MediaFileEventHandler class."""

    def test_initialization(self, event_handler):
        """Test that event handler initializes correctly."""
        assert event_handler.scanner is not None
        assert event_handler.pending_files == {}
        assert ".mp4" in event_handler.media_extensions
        assert ".mkv" in event_handler.media_extensions

    def test_is_media_file_valid(self, event_handler):
        """Test media file detection with valid extensions."""
        with patch("pathlib.Path.is_file", return_value=True):
            assert event_handler._is_media_file("/path/to/video.mp4") is True
            assert event_handler._is_media_file("/path/to/video.mkv") is True
            assert event_handler._is_media_file("/path/to/video.avi") is True

    def test_is_media_file_invalid(self, event_handler):
        """Test media file detection with invalid extensions."""
        with patch("pathlib.Path.is_file", return_value=True):
            assert event_handler._is_media_file("/path/to/file.txt") is False
            assert event_handler._is_media_file("/path/to/file.srt") is False
            assert event_handler._is_media_file("/path/to/file.jpg") is False

    def test_is_media_file_not_file(self, event_handler):
        """Test that directories are not considered media files."""
        with patch("pathlib.Path.is_file", return_value=False):
            assert event_handler._is_media_file("/path/to/directory") is False

    def test_extract_video_title(self, event_handler):
        """Test video title extraction from file path."""
        title = event_handler._extract_video_title("/path/to/my_awesome_movie.mp4")
        assert title == "my awesome movie"

        title = event_handler._extract_video_title(
            "/path/to/Movie.Title.2024.1080p.BluRay.mp4"
        )
        assert title == "Movie Title 2024 1080p BluRay"

    def test_extract_video_title_edge_cases(self, event_handler):
        """Test video title extraction edge cases."""
        # Multiple spaces
        title = event_handler._extract_video_title("/path/to/movie___with___spaces.mp4")
        assert title == "movie with spaces"

        # Just filename
        title = event_handler._extract_video_title("movie.mp4")
        assert title == "movie"

    @pytest.mark.asyncio
    async def test_wait_for_file_stability_success(self, event_handler, mock_settings):
        """Test file stability check with stable file."""
        file_path = "/tmp/test_movie.mp4"

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1000000
                result = await event_handler._wait_for_file_stability(file_path)
                assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_file_stability_file_disappeared(
        self, event_handler, mock_settings
    ):
        """Test file stability check when file disappears."""
        file_path = "/tmp/test_movie.mp4"

        with patch("pathlib.Path.exists", return_value=False):
            result = await event_handler._wait_for_file_stability(file_path)
            assert result is False

    @pytest.mark.asyncio
    async def test_process_media_file_publishes_both_events(
        self, event_handler, mock_redis_client, mock_event_publisher, mock_settings
    ):
        """Test that processing media file publishes both MEDIA_FILE_DETECTED and SUBTITLE_REQUESTED events."""
        file_path = "/media/movies/test_movie.mp4"

        # Mock file stability check
        event_handler._wait_for_file_stability = AsyncMock(return_value=True)

        # Mock duplicate prevention to return not duplicate
        with patch("scanner.event_handler.duplicate_prevention") as mock_dup:
            from common.duplicate_prevention import DuplicateCheckResult

            mock_dup.check_and_register = AsyncMock(
                return_value=DuplicateCheckResult(
                    is_duplicate=False, existing_job_id=None, message="Not a duplicate"
                )
            )

            await event_handler._process_media_file(file_path)

        # Verify job was saved to Redis
        mock_redis_client.save_job.assert_called_once()
        saved_job = mock_redis_client.save_job.call_args[0][0]
        assert saved_job.video_url == file_path
        assert saved_job.video_title == "test movie"
        assert saved_job.language == "en"
        assert (
            saved_job.target_language is None
        )  # target_language is no longer set by scanner
        assert saved_job.status == SubtitleStatus.PENDING

        # Verify both events were published
        actual_count = mock_event_publisher.publish_event.call_count
        assert actual_count == 2, f"Expected 2 events, got {actual_count}"

        # Check first event (MEDIA_FILE_DETECTED)
        first_event = mock_event_publisher.publish_event.call_args_list[0][0][0]
        assert first_event.event_type == EventType.MEDIA_FILE_DETECTED
        assert first_event.source == "scanner"
        assert first_event.payload["file_path"] == file_path
        assert first_event.payload["video_title"] == "test movie"

        # Check second event (SUBTITLE_REQUESTED)
        second_event = mock_event_publisher.publish_event.call_args_list[1][0][0]
        assert second_event.event_type == EventType.SUBTITLE_REQUESTED
        assert second_event.source == "scanner"
        assert second_event.payload["video_url"] == file_path
        assert second_event.payload["video_title"] == "test movie"
        assert second_event.payload["language"] == "en"
        assert (
            second_event.payload["target_language"] is None
        )  # target_language is no longer set by scanner
        assert second_event.payload["preferred_sources"] == ["opensubtitles"]
        # auto_translate is False when target_language is None (scanner doesn't set target_language)
        assert second_event.payload["auto_translate"] is False

    @pytest.mark.asyncio
    async def test_process_media_file_auto_translate_disabled(
        self, event_handler, mock_redis_client, mock_event_publisher, mock_settings
    ):
        """Test that auto_translate flag is False when disabled in settings."""
        file_path = "/media/movies/test_movie.mp4"
        mock_settings.scanner_auto_translate = False

        # Mock file stability check
        event_handler._wait_for_file_stability = AsyncMock(return_value=True)

        await event_handler._process_media_file(file_path)

        # Check SUBTITLE_REQUESTED event has auto_translate = False
        second_event = mock_event_publisher.publish_event.call_args_list[1][0][0]
        assert second_event.event_type == EventType.SUBTITLE_REQUESTED
        assert second_event.payload["auto_translate"] is False

    @pytest.mark.asyncio
    async def test_process_media_file_no_target_language(
        self, event_handler, mock_redis_client, mock_event_publisher, mock_settings
    ):
        """Test that auto_translate is False when no target language is set."""
        file_path = "/media/movies/test_movie.mp4"
        mock_settings.subtitle_fallback_language = None

        # Mock file stability check
        event_handler._wait_for_file_stability = AsyncMock(return_value=True)

        await event_handler._process_media_file(file_path)

        # Check SUBTITLE_REQUESTED event has auto_translate = False
        second_event = mock_event_publisher.publish_event.call_args_list[1][0][0]
        assert second_event.event_type == EventType.SUBTITLE_REQUESTED
        assert second_event.payload["auto_translate"] is False

    @pytest.mark.asyncio
    async def test_process_media_file_unstable_file(
        self, event_handler, mock_redis_client, mock_event_publisher, mock_settings
    ):
        """Test that unstable files are not processed."""
        file_path = "/media/movies/test_movie.mp4"

        # Mock file stability check to return False
        event_handler._wait_for_file_stability = AsyncMock(return_value=False)

        await event_handler._process_media_file(file_path)

        # Verify no job was saved and no events were published
        mock_redis_client.save_job.assert_not_called()
        mock_event_publisher.publish_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_media_file_exception_handling(
        self, event_handler, mock_redis_client, mock_event_publisher, mock_settings
    ):
        """Test exception handling during media file processing."""
        file_path = "/media/movies/test_movie.mp4"

        # Mock file stability check to succeed
        event_handler._wait_for_file_stability = AsyncMock(return_value=True)

        # Mock Redis save to raise an exception
        mock_redis_client.save_job = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise exception
        await event_handler._process_media_file(file_path)

        # Verify no events were published
        mock_event_publisher.publish_event.assert_not_called()

    def test_on_created_media_file(self, event_handler, mock_settings):
        """Test on_created handler with media file."""
        file_path = "/media/movies/test_movie.mp4"

        # Create mock event
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.is_directory = False
        mock_event.src_path = file_path

        with patch("pathlib.Path.is_file", return_value=True):
            with patch("asyncio.create_task") as mock_create_task:
                event_handler.on_created(mock_event)

                # Verify task was created
                mock_create_task.assert_called_once()

    def test_on_created_non_media_file(self, event_handler, mock_settings):
        """Test on_created handler with non-media file."""
        file_path = "/media/movies/subtitle.srt"

        # Create mock event
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.is_directory = False
        mock_event.src_path = file_path

        with patch("pathlib.Path.is_file", return_value=True):
            with patch("asyncio.create_task") as mock_create_task:
                event_handler.on_created(mock_event)

                # Verify no task was created
                mock_create_task.assert_not_called()

    def test_on_created_directory(self, event_handler, mock_settings):
        """Test on_created handler with directory."""
        # Create mock event for directory
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.is_directory = True
        mock_event.src_path = "/media/movies/"

        with patch("asyncio.create_task") as mock_create_task:
            event_handler.on_created(mock_event)

            # Verify no task was created
            mock_create_task.assert_not_called()

    def test_on_modified_media_file(self, event_handler, mock_settings):
        """Test on_modified handler with media file."""
        file_path = "/media/movies/test_movie.mp4"

        # Create mock event
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.is_directory = False
        mock_event.src_path = file_path

        with patch("pathlib.Path.is_file", return_value=True):
            with patch("asyncio.create_task") as mock_create_task:
                event_handler.on_modified(mock_event)

                # Verify task was created
                mock_create_task.assert_called_once()

    def test_cleanup_completed_tasks(self, event_handler):
        """Test cleanup of completed pending tasks."""
        # Add some completed tasks
        completed_task = MagicMock()
        completed_task.done = MagicMock(return_value=True)

        pending_task = MagicMock()
        pending_task.done = MagicMock(return_value=False)

        event_handler.pending_files = {
            "/path/to/completed.mp4": completed_task,
            "/path/to/pending.mp4": pending_task,
        }

        event_handler._cleanup_completed_tasks()

        # Verify only pending task remains
        assert "/path/to/completed.mp4" not in event_handler.pending_files
        assert "/path/to/pending.mp4" in event_handler.pending_files

    def test_on_created_cancels_existing_task(self, event_handler, mock_settings):
        """Test that on_created cancels existing pending task for the same file."""
        file_path = "/media/movies/test_movie.mp4"

        # Add existing pending task
        existing_task = MagicMock()
        existing_task.done = MagicMock(return_value=False)
        existing_task.cancel = MagicMock()
        event_handler.pending_files[file_path] = existing_task

        # Create mock event
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.is_directory = False
        mock_event.src_path = file_path

        with patch("pathlib.Path.is_file", return_value=True):
            with patch("asyncio.create_task"):
                event_handler.on_created(mock_event)

                # Verify existing task was cancelled
                existing_task.cancel.assert_called_once()
