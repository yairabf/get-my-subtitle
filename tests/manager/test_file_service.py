"""Unit tests for file service module."""

from pathlib import Path
from uuid import uuid4

import pytest

from manager.file_service import (
    ensure_storage_directory,
    get_subtitle_file_path,
    read_subtitle_file,
    save_subtitle_file,
)


@pytest.mark.unit
class TestEnsureStorageDirectory:
    """Test ensure_storage_directory function."""

    def test_ensure_storage_directory_creates_directory(self, tmp_path, monkeypatch):
        """Test that ensure_storage_directory creates the directory."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        ensure_storage_directory()

        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_ensure_storage_directory_creates_parent_directories(
        self, tmp_path, monkeypatch
    ):
        """Test that ensure_storage_directory creates parent directories."""
        storage_path = tmp_path / "deep" / "nested" / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        ensure_storage_directory()

        assert storage_path.exists()
        assert storage_path.is_dir()
        # Check parent directories
        assert (tmp_path / "deep").exists()
        assert (tmp_path / "deep" / "nested").exists()

    def test_ensure_storage_directory_idempotent(self, tmp_path, monkeypatch):
        """Test ensure_storage_directory is idempotent."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        # Call multiple times
        ensure_storage_directory()
        ensure_storage_directory()
        ensure_storage_directory()

        # Should still exist and be a directory
        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_ensure_storage_directory_with_existing_directory(
        self, tmp_path, monkeypatch
    ):
        """Test that ensure_storage_directory works with existing directory."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        # Should not raise error
        ensure_storage_directory()

        assert storage_path.exists()
        assert storage_path.is_dir()


@pytest.mark.unit
class TestGetSubtitleFilePath:
    """Test get_subtitle_file_path function."""

    def test_get_subtitle_file_path_format(self, tmp_path, monkeypatch):
        """Test that get_subtitle_file_path generates correct format."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"

        file_path = get_subtitle_file_path(job_id, language)

        assert isinstance(file_path, Path)
        assert file_path.name == f"{job_id}.{language}.srt"
        assert file_path.parent == storage_path

    @pytest.mark.parametrize(
        "language",
        ["en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko"],
    )
    def test_get_subtitle_file_path_with_different_languages(
        self, tmp_path, monkeypatch, language
    ):
        """Test get_subtitle_file_path with different language codes."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        file_path = get_subtitle_file_path(job_id, language)

        assert file_path.name.endswith(f".{language}.srt")
        assert str(job_id) in file_path.name

    def test_get_subtitle_file_path_with_different_uuids(self, tmp_path, monkeypatch):
        """Test get_subtitle_file_path with different UUIDs."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id1 = uuid4()
        job_id2 = uuid4()

        file_path1 = get_subtitle_file_path(job_id1, "en")
        file_path2 = get_subtitle_file_path(job_id2, "en")

        assert file_path1 != file_path2
        assert str(job_id1) in file_path1.name
        assert str(job_id2) in file_path2.name

    def test_get_subtitle_file_path_returns_path_object(self, tmp_path, monkeypatch):
        """Test that get_subtitle_file_path returns a Path object."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        file_path = get_subtitle_file_path(job_id, "en")

        assert isinstance(file_path, Path)


@pytest.mark.unit
class TestSaveSubtitleFile:
    """Test save_subtitle_file function."""

    def test_save_subtitle_file_creates_file(self, tmp_path, monkeypatch):
        """Test that save_subtitle_file creates a file with content."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = "1\n00:00:01,000 --> 00:00:04,000\nHello world\n"
        language = "en"

        file_path_str = save_subtitle_file(job_id, content, language)

        # Check that file was created
        file_path = Path(file_path_str)
        assert file_path.exists()
        assert file_path.is_file()

        # Check content
        assert file_path.read_text(encoding="utf-8") == content

    def test_save_subtitle_file_creates_directory(self, tmp_path, monkeypatch):
        """Test save_subtitle_file creates directory if it doesn't exist."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = "Test content"
        language = "en"

        # Directory shouldn't exist yet
        assert not storage_path.exists()

        save_subtitle_file(job_id, content, language)

        # Directory should be created
        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_save_subtitle_file_utf8_encoding(self, tmp_path, monkeypatch):
        """Test that save_subtitle_file uses UTF-8 encoding."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = "Hello 世界! 🌍\nTest with unicode"
        language = "en"

        file_path_str = save_subtitle_file(job_id, content, language)

        # Read back and verify
        file_path = Path(file_path_str)
        read_content = file_path.read_text(encoding="utf-8")
        assert read_content == content
        assert "世界" in read_content
        assert "🌍" in read_content

    def test_save_subtitle_file_returns_string_path(self, tmp_path, monkeypatch):
        """Test that save_subtitle_file returns string path."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = "Test content"
        language = "en"

        file_path_str = save_subtitle_file(job_id, content, language)

        assert isinstance(file_path_str, str)
        assert Path(file_path_str).exists()

    def test_save_subtitle_file_multiline_content(self, tmp_path, monkeypatch):
        """Test that save_subtitle_file handles multiline content correctly."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

2
00:00:04,500 --> 00:00:08,000
Second subtitle
"""
        language = "en"

        file_path_str = save_subtitle_file(job_id, content, language)

        # Read back and verify
        file_path = Path(file_path_str)
        read_content = file_path.read_text(encoding="utf-8")
        assert read_content == content
        assert "First subtitle" in read_content
        assert "Second subtitle" in read_content

    def test_save_subtitle_file_overwrites_existing(self, tmp_path, monkeypatch):
        """Test that save_subtitle_file overwrites existing file."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"

        # Save first content
        content1 = "First content"
        save_subtitle_file(job_id, content1, language)

        # Save different content
        content2 = "Second content"
        file_path_str = save_subtitle_file(job_id, content2, language)

        # Should have second content
        file_path = Path(file_path_str)
        assert file_path.read_text(encoding="utf-8") == content2

    @pytest.mark.parametrize(
        "language",
        ["en", "es", "fr", "de", "zh", "ja"],
    )
    def test_save_subtitle_file_with_different_languages(
        self, tmp_path, monkeypatch, language
    ):
        """Test save_subtitle_file with different language codes."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = f"Content in {language}"
        file_path_str = save_subtitle_file(job_id, content, language)

        file_path = Path(file_path_str)
        assert file_path.exists()
        assert file_path.name.endswith(f".{language}.srt")
        assert file_path.read_text(encoding="utf-8") == content


@pytest.mark.unit
class TestReadSubtitleFile:
    """Test read_subtitle_file function."""

    def test_read_subtitle_file_successful_read(self, tmp_path, monkeypatch):
        """Test that read_subtitle_file reads file content successfully."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"
        content = "1\n00:00:01,000 --> 00:00:04,000\nHello world\n"

        # Create file first
        file_path = get_subtitle_file_path(job_id, language)
        file_path.write_text(content, encoding="utf-8")

        # Read it back
        read_content = read_subtitle_file(job_id, language)

        assert read_content == content

    def test_read_subtitle_file_file_not_found(self, tmp_path, monkeypatch):
        """Test read_subtitle_file raises FileNotFoundError."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"

        # File doesn't exist
        with pytest.raises(FileNotFoundError) as exc_info:
            read_subtitle_file(job_id, language)

        assert "Subtitle file not found" in str(exc_info.value)
        assert str(job_id) in str(exc_info.value)

    def test_read_subtitle_file_utf8_encoding(self, tmp_path, monkeypatch):
        """Test read_subtitle_file reads UTF-8 encoded content correctly."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"
        content = "Hello 世界! 🌍\nTest with unicode"

        # Create file with UTF-8 content
        file_path = get_subtitle_file_path(job_id, language)
        file_path.write_text(content, encoding="utf-8")

        # Read it back
        read_content = read_subtitle_file(job_id, language)

        assert read_content == content
        assert "世界" in read_content
        assert "🌍" in read_content

    def test_read_subtitle_file_content_integrity(self, tmp_path, monkeypatch):
        """Test that read_subtitle_file preserves content integrity."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"
        content = """1
00:00:01,000 --> 00:00:04,000
First subtitle

2
00:00:04,500 --> 00:00:08,000
Second subtitle
"""

        # Create file
        file_path = get_subtitle_file_path(job_id, language)
        file_path.write_text(content, encoding="utf-8")

        # Read it back
        read_content = read_subtitle_file(job_id, language)

        # Should match exactly
        assert read_content == content
        assert len(read_content) == len(content)

    @pytest.mark.parametrize(
        "language",
        ["en", "es", "fr", "de", "zh", "ja"],
    )
    def test_read_subtitle_file_with_different_languages(
        self, tmp_path, monkeypatch, language
    ):
        """Test read_subtitle_file with different language codes."""
        storage_path = tmp_path / "storage" / "subtitles"
        storage_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        content = f"Content in {language}"

        # Create file
        file_path = get_subtitle_file_path(job_id, language)
        file_path.write_text(content, encoding="utf-8")

        # Read it back
        read_content = read_subtitle_file(job_id, language)

        assert read_content == content


@pytest.mark.unit
class TestFileServiceIntegration:
    """Integration tests for file service operations."""

    def test_save_and_read_round_trip(self, tmp_path, monkeypatch):
        """Test saving and reading a file in a round trip."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"
        original_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:04,500 --> 00:00:08,000
This is a test
"""

        # Save file
        file_path_str = save_subtitle_file(job_id, original_content, language)

        # Read it back
        read_content = read_subtitle_file(job_id, language)

        # Should match
        assert read_content == original_content
        assert Path(file_path_str).exists()

    def test_multiple_files_same_language(self, tmp_path, monkeypatch):
        """Test handling multiple files with same language."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id1 = uuid4()
        job_id2 = uuid4()
        language = "en"

        content1 = "Content 1"
        content2 = "Content 2"

        # Save both files
        save_subtitle_file(job_id1, content1, language)
        save_subtitle_file(job_id2, content2, language)

        # Read both back
        read_content1 = read_subtitle_file(job_id1, language)
        read_content2 = read_subtitle_file(job_id2, language)

        assert read_content1 == content1
        assert read_content2 == content2

    def test_multiple_languages_same_job(self, tmp_path, monkeypatch):
        """Test handling multiple languages for same job."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        languages = ["en", "es", "fr"]

        contents = {
            "en": "English content",
            "es": "Contenido en español",
            "fr": "Contenu en français",
        }

        # Save files for all languages
        for lang in languages:
            save_subtitle_file(job_id, contents[lang], lang)

        # Read all back
        for lang in languages:
            read_content = read_subtitle_file(job_id, lang)
            assert read_content == contents[lang]

    def test_file_path_consistency(self, tmp_path, monkeypatch):
        """Test get_subtitle_file_path and save_subtitle_file paths."""
        storage_path = tmp_path / "storage" / "subtitles"
        monkeypatch.setattr(
            "manager.file_service.settings.subtitle_storage_path",
            str(storage_path),
        )

        job_id = uuid4()
        language = "en"
        content = "Test content"

        # Get expected path
        expected_path = get_subtitle_file_path(job_id, language)

        # Save file
        saved_path_str = save_subtitle_file(job_id, content, language)

        # Paths should match
        assert Path(saved_path_str) == expected_path
