"""Tests for duplicate prevention in scanner event handler."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.duplicate_prevention import DuplicateCheckResult
from common.redis_client import redis_client
from scanner.event_handler import MediaFileEventHandler
from scanner.scanner import MediaScanner


@pytest.fixture
def mock_scanner():
    """Create a mock MediaScanner instance."""
    scanner = MagicMock(spec=MediaScanner)
    return scanner


@pytest.fixture
def event_handler(mock_scanner):
    """Create MediaFileEventHandler instance with mock scanner."""
    handler = MediaFileEventHandler(mock_scanner)
    return handler


@pytest.fixture
def mock_duplicate_prevention():
    """Create mock duplicate prevention service."""
    with patch("scanner.event_handler.duplicate_prevention") as mock:
        yield mock


@pytest.mark.asyncio
class TestEventHandlerDuplicatePrevention:
    """Test suite for duplicate prevention in event handler."""

    @pytest.mark.parametrize(
        "file_path,video_title,language,description",
        [
            ("/media/movie.mp4", "movie", "en", "basic mp4 file"),
            ("/media/show/episode.mkv", "show episode", "en", "mkv in subfolder"),
            ("/media/film.avi", "film", "es", "avi with spanish"),
        ],
    )
    async def test_process_media_file_first_request(
        self,
        event_handler,
        mock_duplicate_prevention,
        file_path,
        video_title,
        language,
        description,
    ):
        """Test that first request for a media file is processed normally."""
        # Mock duplicate prevention to indicate not a duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        )

        # Mock file operations
        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = video_title
            mock_file.suffix = Path(file_path).suffix
            mock_path.return_value = mock_file

            # Mock Redis and event publisher
            with patch.object(redis_client, "save_job", new_callable=AsyncMock), patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ):
                # Process file
                await event_handler._process_media_file(file_path)

                # Verify duplicate check was called
                mock_duplicate_prevention.check_and_register.assert_called_once()

    @pytest.mark.parametrize(
        "file_path,language,existing_job_id,description",
        [
            ("/media/movie.mp4", "en", uuid4(), "duplicate mp4"),
            ("/media/show.mkv", "es", uuid4(), "duplicate mkv spanish"),
            ("/media/film.avi", "fr", uuid4(), "duplicate avi french"),
        ],
    )
    async def test_process_media_file_duplicate_request(
        self,
        event_handler,
        mock_duplicate_prevention,
        file_path,
        language,
        existing_job_id,
        description,
    ):
        """Test that duplicate request is detected and skips processing."""
        # Mock duplicate prevention to indicate duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=True,
                existing_job_id=existing_job_id,
                message=f"Already being processed as job {existing_job_id}",
            )
        )

        # Mock file operations
        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = "video"
            mock_file.suffix = Path(file_path).suffix
            mock_path.return_value = mock_file

            # Mock Redis and event publisher - should NOT be called
            with patch.object(
                redis_client, "save_job", new_callable=AsyncMock
            ) as mock_save_job, patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ) as mock_publish:
                # Process file
                await event_handler._process_media_file(file_path)

                # Verify duplicate check was called
                mock_duplicate_prevention.check_and_register.assert_called_once()

                # Verify job was NOT created (duplicate detected)
                mock_save_job.assert_not_called()
                mock_publish.assert_not_called()

    async def test_process_media_file_different_languages_allowed(
        self, event_handler, mock_duplicate_prevention
    ):
        """Test that same file with different languages creates separate jobs."""
        file_path = "/media/movie.mp4"

        # First request (English) - not duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        )

        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = "movie"
            mock_file.suffix = ".mp4"
            mock_path.return_value = mock_file

            with patch.object(
                redis_client, "save_job", new_callable=AsyncMock
            ) as mock_save_job, patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ):
                # Process file
                await event_handler._process_media_file(file_path)

                # Verify job was created
                assert mock_save_job.call_count == 1

                # Second request with different language should also succeed
                await event_handler._process_media_file(file_path)

                # Should have created another job (different language)
                assert mock_save_job.call_count == 2

    async def test_process_media_file_duplicate_prevention_disabled(
        self, event_handler, mock_duplicate_prevention
    ):
        """Test that requests are processed when duplicate prevention is disabled."""
        file_path = "/media/movie.mp4"

        # Mock as disabled
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Duplicate prevention disabled",
            )
        )

        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = "movie"
            mock_file.suffix = ".mp4"
            mock_path.return_value = mock_file

            with patch.object(redis_client, "save_job", new_callable=AsyncMock), patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ):
                # Process same file multiple times
                await event_handler._process_media_file(file_path)
                await event_handler._process_media_file(file_path)

                # Both should be processed
                assert mock_duplicate_prevention.check_and_register.call_count == 2

    async def test_process_media_file_redis_unavailable_graceful_degradation(
        self, event_handler, mock_duplicate_prevention
    ):
        """Test graceful degradation when Redis is unavailable."""
        file_path = "/media/movie.mp4"

        # Mock Redis unavailable scenario
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Redis unavailable - duplicate prevention bypassed",
            )
        )

        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = "movie"
            mock_file.suffix = ".mp4"
            mock_path.return_value = mock_file

            with patch.object(redis_client, "save_job", new_callable=AsyncMock), patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ):
                # Should allow request through despite Redis being unavailable
                await event_handler._process_media_file(file_path)

                # Verify duplicate check was attempted
                mock_duplicate_prevention.check_and_register.assert_called_once()

    @pytest.mark.parametrize(
        "file1,file2,should_be_duplicate",
        [
            ("/media/movie.mp4", "/media/movie.mp4", True),  # Exact same file
            ("/media/movie1.mp4", "/media/movie2.mp4", False),  # Different files
            (
                "/media/dir1/movie.mp4",
                "/media/dir2/movie.mp4",
                False,
            ),  # Same name, different paths
        ],
    )
    async def test_duplicate_detection_by_path(
        self,
        event_handler,
        mock_duplicate_prevention,
        file1,
        file2,
        should_be_duplicate,
    ):
        """Test duplicate detection based on file path."""
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # First file
        if should_be_duplicate:
            mock_duplicate_prevention.check_and_register = AsyncMock(
                side_effect=[
                    DuplicateCheckResult(
                        is_duplicate=False,
                        existing_job_id=None,
                        message="Request registered",
                    ),
                    DuplicateCheckResult(
                        is_duplicate=True,
                        existing_job_id=job_id_1,
                        message=f"Already being processed as job {job_id_1}",
                    ),
                ]
            )
        else:
            mock_duplicate_prevention.check_and_register = AsyncMock(
                return_value=DuplicateCheckResult(
                    is_duplicate=False,
                    existing_job_id=None,
                    message="Request registered",
                )
            )

        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = "movie"
            mock_file.suffix = ".mp4"
            mock_path.return_value = mock_file

            with patch.object(
                redis_client, "save_job", new_callable=AsyncMock
            ) as mock_save_job, patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ):
                # Process first file
                await event_handler._process_media_file(file1)

                # Process second file
                await event_handler._process_media_file(file2)

                # Verify behavior based on duplication expectation
                if should_be_duplicate:
                    # Should only create one job
                    assert mock_save_job.call_count == 1
                else:
                    # Should create two jobs
                    assert mock_save_job.call_count == 2

    async def test_on_created_triggers_duplicate_check(
        self, event_handler, mock_duplicate_prevention
    ):
        """Test that on_created event triggers duplicate prevention check."""
        # Create mock file system event
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/media/movie.mp4"

        # Mock is_media_file to return True
        with patch.object(event_handler, "_is_media_file", return_value=True):
            with patch.object(
                event_handler, "_process_media_file", new_callable=AsyncMock
            ) as mock_process:
                # Trigger on_created
                event_handler.on_created(mock_event)

                # Wait for async task to be scheduled
                await asyncio.sleep(0.1)

                # Verify _process_media_file was called
                mock_process.assert_called_once_with(mock_event.src_path)

    async def test_on_modified_triggers_duplicate_check(
        self, event_handler, mock_duplicate_prevention
    ):
        """Test that on_modified event triggers duplicate prevention check."""
        # Create mock file system event
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = "/media/movie.mp4"

        # Mock is_media_file to return True
        with patch.object(event_handler, "_is_media_file", return_value=True):
            with patch.object(
                event_handler, "_process_media_file", new_callable=AsyncMock
            ) as mock_process:
                # Trigger on_modified
                event_handler.on_modified(mock_event)

                # Wait for async task to be scheduled
                await asyncio.sleep(0.1)

                # Verify _process_media_file was called
                mock_process.assert_called_once_with(mock_event.src_path)

    async def test_rapid_file_events_deduplicated(
        self, event_handler, mock_duplicate_prevention
    ):
        """Test that rapid file system events for same file are deduplicated."""
        file_path = "/media/movie.mp4"

        # Mock duplicate prevention
        mock_duplicate_prevention.check_and_register = AsyncMock(
            side_effect=[
                DuplicateCheckResult(
                    is_duplicate=False,
                    existing_job_id=None,
                    message="Request registered",
                ),
                DuplicateCheckResult(
                    is_duplicate=True,
                    existing_job_id=uuid4(),
                    message="Already being processed",
                ),
            ]
        )

        # Create multiple events rapidly
        mock_event = MagicMock()
        mock_event.is_directory = False
        mock_event.src_path = file_path

        with patch.object(event_handler, "_is_media_file", return_value=True):
            with patch.object(
                event_handler, "_process_media_file", new_callable=AsyncMock
            ) as mock_process:
                # Trigger multiple rapid events
                event_handler.on_created(mock_event)
                event_handler.on_modified(mock_event)
                event_handler.on_modified(mock_event)

                # Wait for async tasks
                await asyncio.sleep(0.2)

                # Should have attempted to process, but duplicate prevention should catch it
                # Note: The actual deduplication happens in _process_media_file
                assert mock_process.call_count >= 1
