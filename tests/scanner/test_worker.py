"""Tests for the scanner worker."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from watchdog.events import FileCreatedEvent, FileModifiedEvent

from common.schemas import EventType, SubtitleStatus
from scanner.event_handler import MediaFileEventHandler
from scanner.scanner import MediaScanner


class TestMediaFileEventHandler:
    """Test MediaFileEventHandler class."""

    @pytest.fixture
    def mock_scanner(self):
        """Create a mock scanner instance."""
        return MagicMock()

    @pytest.fixture
    def event_handler(self, mock_scanner):
        """Create an event handler instance."""
        with patch("scanner.event_handler.settings") as mock_settings:
            mock_settings.scanner_media_extensions = [".mp4", ".mkv", ".avi"]
            mock_settings.scanner_debounce_seconds = 0.1
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "en"
            mock_settings.scanner_auto_translate = False
            handler = MediaFileEventHandler(mock_scanner)
            return handler

    def test_is_media_file_with_supported_extension(self, event_handler, tmp_path):
        """Test that media files with supported extensions are recognized."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("test content")
        assert event_handler._is_media_file(str(test_file)) is True

    def test_is_media_file_with_unsupported_extension(self, event_handler, tmp_path):
        """Test that files with unsupported extensions are not recognized."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        assert event_handler._is_media_file(str(test_file)) is False

    def test_is_media_file_with_directory(self, event_handler, tmp_path):
        """Test that directories are not recognized as media files."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        assert event_handler._is_media_file(str(test_dir)) is False

    def test_extract_video_title_from_filename(self, event_handler):
        """Test video title extraction from filename."""
        test_cases = [
            ("/path/to/movie.mp4", "movie"),
            ("/path/to/movie_title.mp4", "movie title"),
            ("/path/to/movie-title.mp4", "movie title"),
            ("/path/to/movie.title.mp4", "movie title"),
            ("/path/to/The.Matrix.1999.mp4", "The Matrix 1999"),
        ]

        for file_path, expected_title in test_cases:
            title = event_handler._extract_video_title(file_path)
            assert title == expected_title

    @pytest.mark.asyncio
    async def test_wait_for_file_stability_stable_file(self, event_handler, tmp_path):
        """Test that stable files are detected correctly."""
        test_file = tmp_path / "test.mp4"
        test_file.write_text("stable content")
        await asyncio.sleep(0.2)  # Wait a bit

        result = await event_handler._wait_for_file_stability(str(test_file))
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_file_stability_nonexistent_file(self, event_handler):
        """Test that nonexistent files return False."""
        result = await event_handler._wait_for_file_stability("/nonexistent/file.mp4")
        assert result is False

    @pytest.mark.asyncio
    async def test_process_media_file_creates_job(
        self, event_handler, tmp_path, mock_scanner
    ):
        """Test that processing a media file creates a job and publishes event."""
        test_file = tmp_path / "test_movie.mp4"
        test_file.write_text("test content")
        await asyncio.sleep(0.2)  # Wait for file to be stable

        with patch("scanner.event_handler.redis_client") as mock_redis:
            mock_redis.save_job = AsyncMock()
            mock_redis.update_phase = AsyncMock(return_value=True)

            with patch("scanner.event_handler.event_publisher") as mock_publisher:
                mock_publisher.publish_event = AsyncMock()

                with patch("scanner.event_handler.orchestrator") as mock_orchestrator:
                    mock_orchestrator.enqueue_download_task = AsyncMock(
                        return_value=True
                    )

                    await event_handler._process_media_file(str(test_file))

                    # Verify job was created
                    assert mock_redis.save_job.called
                    call_args = mock_redis.save_job.call_args[0][0]
                    assert call_args.video_url == str(test_file)
                    assert call_args.video_title == "test movie"

                    # Verify event was published
                    assert mock_publisher.publish_event.called
                    event_call = mock_publisher.publish_event.call_args[0][0]
                    assert event_call.event_type == EventType.MEDIA_FILE_DETECTED

                    # Verify download task was enqueued
                    assert mock_orchestrator.enqueue_download_task.called

    @pytest.mark.asyncio
    async def test_on_created_triggers_processing(self, event_handler, tmp_path):
        """Test that file creation events trigger processing."""
        test_file = tmp_path / "new_movie.mp4"

        with patch.object(
            event_handler, "_process_media_file", new_callable=AsyncMock
        ) as mock_process:
            # Create file
            test_file.write_text("content")
            await asyncio.sleep(0.1)

            # Create event
            event = FileCreatedEvent(str(test_file))
            event_handler.on_created(event)

            # Wait for async task
            await asyncio.sleep(0.2)

            # Verify processing was triggered
            assert mock_process.called
            assert mock_process.call_args[0][0] == str(test_file)

    @pytest.mark.asyncio
    async def test_on_created_ignores_directories(self, event_handler, tmp_path):
        """Test that directory creation events are ignored."""
        test_dir = tmp_path / "new_dir"
        test_dir.mkdir()

        with patch.object(
            event_handler, "_process_media_file", new_callable=AsyncMock
        ) as mock_process:
            event = FileCreatedEvent(str(test_dir))
            event.is_directory = True
            event_handler.on_created(event)

            await asyncio.sleep(0.1)

            # Verify processing was not triggered
            assert not mock_process.called

    @pytest.mark.asyncio
    async def test_on_created_ignores_non_media_files(self, event_handler, tmp_path):
        """Test that non-media file creation events are ignored."""
        test_file = tmp_path / "document.txt"
        test_file.write_text("content")

        with patch.object(
            event_handler, "_process_media_file", new_callable=AsyncMock
        ) as mock_process:
            event = FileCreatedEvent(str(test_file))
            event_handler.on_created(event)

            await asyncio.sleep(0.1)

            # Verify processing was not triggered
            assert not mock_process.called

    @pytest.mark.asyncio
    async def test_on_modified_triggers_processing(self, event_handler, tmp_path):
        """Test that file modification events trigger processing."""
        test_file = tmp_path / "updated_movie.mp4"
        test_file.write_text("initial content")

        with patch.object(
            event_handler, "_process_media_file", new_callable=AsyncMock
        ) as mock_process:
            # Modify file
            test_file.write_text("updated content")
            await asyncio.sleep(0.1)

            # Create event
            event = FileModifiedEvent(str(test_file))
            event_handler.on_modified(event)

            # Wait for async task
            await asyncio.sleep(0.2)

            # Verify processing was triggered
            assert mock_process.called
            assert mock_process.call_args[0][0] == str(test_file)


class TestMediaScanner:
    """Test MediaScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create a scanner instance."""
        return MediaScanner()

    def test_scanner_initialization(self, scanner):
        """Test that scanner initializes correctly."""
        assert scanner.observer is None
        assert scanner.event_handler is None
        assert scanner.running is False

    @pytest.mark.asyncio
    async def test_connect_establishes_connections(self, scanner):
        """Test that connect establishes all required connections."""
        with patch("scanner.scanner.redis_client") as mock_redis:
            mock_redis.connect = AsyncMock()

            with patch("scanner.scanner.orchestrator") as mock_orchestrator:
                mock_orchestrator.connect = AsyncMock()

                with patch("scanner.scanner.event_publisher") as mock_publisher:
                    mock_publisher.connect = AsyncMock()

                    await scanner.connect()

                    mock_redis.connect.assert_called_once()
                    mock_orchestrator.connect.assert_called_once()
                    mock_publisher.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_closes_connections(self, scanner):
        """Test that disconnect closes all connections."""
        with patch("scanner.scanner.orchestrator") as mock_orchestrator:
            mock_orchestrator.disconnect = AsyncMock()

            with patch("scanner.scanner.event_publisher") as mock_publisher:
                mock_publisher.disconnect = AsyncMock()

                with patch("scanner.scanner.redis_client") as mock_redis:
                    mock_redis.disconnect = AsyncMock()

                    await scanner.disconnect()

                    mock_orchestrator.disconnect.assert_called_once()
                    mock_publisher.disconnect.assert_called_once()
                    mock_redis.disconnect.assert_called_once()

    def test_start_initializes_observer(self, scanner, tmp_path):
        """Test that start initializes the file system observer."""
        with patch("scanner.scanner.settings") as mock_settings:
            mock_settings.scanner_media_path = str(tmp_path)
            mock_settings.scanner_watch_recursive = True
            mock_settings.scanner_media_extensions = [".mp4"]
            mock_settings.scanner_debounce_seconds = 1.0

            with patch("scanner.scanner.Observer") as mock_observer_class:
                mock_observer = MagicMock()
                mock_observer_class.return_value = mock_observer

                scanner.start()

                assert scanner.running is True
                assert scanner.observer is not None
                mock_observer.schedule.assert_called_once()
                mock_observer.start.assert_called_once()

    def test_start_raises_error_for_nonexistent_path(self, scanner):
        """Test that start raises error for nonexistent path."""
        with patch("scanner.scanner.settings") as mock_settings:
            mock_settings.scanner_media_path = "/nonexistent/path"

            with pytest.raises(FileNotFoundError):
                scanner.start()

    def test_start_raises_error_for_non_directory(self, scanner, tmp_path):
        """Test that start raises error for non-directory path."""
        test_file = tmp_path / "not_a_dir"
        test_file.write_text("content")

        with patch("scanner.scanner.settings") as mock_settings:
            mock_settings.scanner_media_path = str(test_file)

            with pytest.raises(ValueError):
                scanner.start()

    def test_stop_stops_observer(self, scanner):
        """Test that stop stops the observer."""
        mock_observer = MagicMock()
        scanner.observer = mock_observer
        scanner.running = True

        scanner.stop()

        assert scanner.running is False
        mock_observer.stop.assert_called_once()
        mock_observer.join.assert_called_once()

    def test_stop_handles_not_running(self, scanner):
        """Test that stop handles case when scanner is not running."""
        scanner.running = False
        scanner.stop()  # Should not raise error

    def test_is_running_returns_correct_state(self, scanner):
        """Test that is_running returns correct state."""
        assert scanner.is_running() is False
        scanner.running = True
        assert scanner.is_running() is True


class TestScannerIntegration:
    """Integration tests for scanner service."""

    @pytest.mark.asyncio
    async def test_full_flow_file_detection_to_job_creation(self, tmp_path):
        """Test full flow from file detection to job creation."""
        test_file = tmp_path / "integration_test.mp4"
        test_file.write_text("test content")
        await asyncio.sleep(0.2)

        with patch("scanner.event_handler.settings") as mock_settings:
            mock_settings.scanner_media_path = str(tmp_path)
            mock_settings.scanner_watch_recursive = False
            mock_settings.scanner_media_extensions = [".mp4"]
            mock_settings.scanner_debounce_seconds = 0.1
            mock_settings.subtitle_desired_language = "en"
            mock_settings.subtitle_fallback_language = "en"
            mock_settings.scanner_auto_translate = False

            scanner = MediaScanner()

            with patch("scanner.scanner.redis_client") as mock_redis:
                mock_redis.connect = AsyncMock()
                mock_redis.disconnect = AsyncMock()

                with patch("scanner.scanner.orchestrator") as mock_orchestrator:
                    mock_orchestrator.connect = AsyncMock()
                    mock_orchestrator.disconnect = AsyncMock()

                    with patch("scanner.scanner.event_publisher") as mock_publisher:
                        mock_publisher.connect = AsyncMock()
                        mock_publisher.disconnect = AsyncMock()

                        await scanner.connect()

                        # Now mock the actual processing dependencies
                        with patch(
                            "scanner.event_handler.redis_client"
                        ) as mock_redis_handler:
                            mock_redis_handler.save_job = AsyncMock()

                            with patch(
                                "scanner.event_handler.event_publisher"
                            ) as mock_publisher_handler:
                                mock_publisher_handler.publish_event = AsyncMock()

                                with patch(
                                    "scanner.event_handler.orchestrator"
                                ) as mock_orchestrator_handler:
                                    mock_orchestrator_handler.enqueue_download_task = (
                                        AsyncMock(return_value=True)
                                    )

                                    # Manually trigger processing (simulating file detection)
                                    handler = MediaFileEventHandler(scanner)
                                    await handler._process_media_file(str(test_file))

                                    # Verify job was created
                                    assert mock_redis_handler.save_job.called

                                    # Verify event was published
                                    assert mock_publisher_handler.publish_event.called
                                    event = (
                                        mock_publisher_handler.publish_event.call_args[
                                            0
                                        ][0]
                                    )
                                    assert (
                                        event.event_type
                                        == EventType.MEDIA_FILE_DETECTED
                                    )

                                    # Verify download task was enqueued
                                    assert (
                                        mock_orchestrator_handler.enqueue_download_task.called
                                    )

                        await scanner.disconnect()
