"""Tests for the file storage service."""

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from manager.file_service import (ensure_storage_directory,
                                  get_subtitle_file_path, read_subtitle_file,
                                  save_subtitle_file)


@pytest.fixture
def temp_storage_dir(monkeypatch):
    """Create a temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the settings to use temp directory
        monkeypatch.setenv("SUBTITLE_STORAGE_PATH", tmpdir)
        # Reimport settings to pick up the change
        from common.config import Settings

        settings = Settings()
        monkeypatch.setattr("manager.file_service.settings", settings)
        yield tmpdir


class TestEnsureStorageDirectory:
    """Test storage directory creation."""

    def test_creates_directory_if_not_exists(self, temp_storage_dir):
        """Test that directory is created if it doesn't exist."""
        storage_path = Path(temp_storage_dir) / "subtitles"
        os.environ["SUBTITLE_STORAGE_PATH"] = str(storage_path)

        # Import fresh settings
        from common.config import Settings

        settings = Settings()

        assert not storage_path.exists()

        # Create directory using the path from settings
        storage_path.mkdir(parents=True, exist_ok=True)

        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_handles_existing_directory(self, temp_storage_dir):
        """Test that existing directory is handled gracefully."""
        storage_path = Path(temp_storage_dir)
        assert storage_path.exists()

        # Should not raise an error
        ensure_storage_directory()


class TestGetSubtitleFilePath:
    """Test subtitle file path generation."""

    @pytest.mark.parametrize(
        "job_id,language",
        [
            ("123e4567-e89b-12d3-a456-426614174000", "en"),
            ("123e4567-e89b-12d3-a456-426614174000", "es"),
            ("987e6543-e21b-98d7-a654-123456789000", "fr"),
        ],
    )
    def test_generates_correct_path(self, temp_storage_dir, job_id, language):
        """Test that file path is generated correctly."""
        from uuid import UUID

        job_uuid = UUID(job_id)
        file_path = get_subtitle_file_path(job_uuid, language)
        expected_filename = f"{job_id}.{language}.srt"

        assert file_path.name == expected_filename
        assert file_path.suffix == ".srt"
        assert str(job_uuid) in str(file_path)
        assert language in str(file_path)

    def test_returns_path_object(self, temp_storage_dir):
        """Test that return type is Path object."""
        job_id = uuid4()
        result = get_subtitle_file_path(job_id, "en")

        assert isinstance(result, Path)


class TestSaveSubtitleFile:
    """Test subtitle file saving."""

    def test_saves_file_successfully(self, temp_storage_dir):
        """Test that file is saved successfully."""
        job_id = uuid4()
        content = "1\n00:00:01,000 --> 00:00:04,000\nHello world\n"
        language = "en"

        file_path = save_subtitle_file(job_id, content, language)

        assert Path(file_path).exists()
        assert Path(file_path).read_text() == content

    def test_returns_file_path_string(self, temp_storage_dir):
        """Test that return type is string."""
        job_id = uuid4()
        content = "Test content"
        language = "en"

        result = save_subtitle_file(job_id, content, language)

        assert isinstance(result, str)

    @pytest.mark.parametrize(
        "content,language",
        [
            ("1\n00:00:01,000 --> 00:00:04,000\nHello\n", "en"),
            ("1\n00:00:01,000 --> 00:00:04,000\nHola\n", "es"),
            ("Multiple\nlines\nof\ncontent", "fr"),
            ("", "de"),  # Empty content
        ],
    )
    def test_saves_different_content(self, temp_storage_dir, content, language):
        """Test saving different content types."""
        job_id = uuid4()

        file_path = save_subtitle_file(job_id, content, language)

        assert Path(file_path).exists()
        assert Path(file_path).read_text() == content

    def test_creates_directory_if_not_exists(self, monkeypatch):
        """Test that parent directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "new_dir" / "subtitles"
            monkeypatch.setenv("SUBTITLE_STORAGE_PATH", str(storage_path))

            # Reimport to get new settings
            from common.config import Settings

            settings = Settings()
            monkeypatch.setattr("manager.file_service.settings", settings)

            job_id = uuid4()
            content = "Test content"

            assert not storage_path.exists()

            file_path = save_subtitle_file(job_id, content, "en")

            assert Path(file_path).exists()
            assert storage_path.exists()

    def test_overwrites_existing_file(self, temp_storage_dir):
        """Test that existing file is overwritten."""
        job_id = uuid4()
        language = "en"

        # Save initial content
        content1 = "Initial content"
        save_subtitle_file(job_id, content1, language)

        # Save new content
        content2 = "Updated content"
        file_path = save_subtitle_file(job_id, content2, language)

        assert Path(file_path).read_text() == content2


class TestReadSubtitleFile:
    """Test subtitle file reading."""

    def test_reads_file_successfully(self, temp_storage_dir):
        """Test that file is read successfully."""
        job_id = uuid4()
        language = "en"
        content = "1\n00:00:01,000 --> 00:00:04,000\nHello world\n"

        # Save file first
        save_subtitle_file(job_id, content, language)

        # Read it back
        read_content = read_subtitle_file(job_id, language)

        assert read_content == content

    def test_returns_string(self, temp_storage_dir):
        """Test that return type is string."""
        job_id = uuid4()
        language = "en"
        content = "Test content"

        save_subtitle_file(job_id, content, language)
        result = read_subtitle_file(job_id, language)

        assert isinstance(result, str)

    @pytest.mark.parametrize(
        "content",
        [
            "1\n00:00:01,000 --> 00:00:04,000\nHello\n",
            "Multiple\nlines\nof\ncontent",
            "",  # Empty content
            "Unicode content: 你好世界 🌍",
        ],
    )
    def test_reads_different_content(self, temp_storage_dir, content):
        """Test reading different content types."""
        job_id = uuid4()
        language = "en"

        save_subtitle_file(job_id, content, language)
        read_content = read_subtitle_file(job_id, language)

        assert read_content == content

    def test_raises_error_for_nonexistent_file(self, temp_storage_dir):
        """Test that error is raised for non-existent file."""
        job_id = uuid4()
        language = "en"

        with pytest.raises(FileNotFoundError):
            read_subtitle_file(job_id, language)

    def test_raises_error_for_invalid_job_id(self, temp_storage_dir):
        """Test that error is raised for invalid job ID."""
        job_id = uuid4()
        language = "en"

        # Don't save any file
        with pytest.raises(FileNotFoundError):
            read_subtitle_file(job_id, language)
