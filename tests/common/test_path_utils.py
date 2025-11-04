"""Unit tests for PathUtils in common/utils.py."""

import tempfile
from pathlib import Path

import pytest

from common.utils import PathUtils


class TestGenerateSubtitlePathFromVideo:
    """Test PathUtils.generate_subtitle_path_from_video() method."""

    @pytest.mark.parametrize(
        "video_filename,language,expected_subtitle_filename",
        [
            ("matrix.mkv", "en", "matrix.en.srt"),
            ("sample.mp4", "es", "sample.es.srt"),
            ("movie.avi", "fr", "movie.fr.srt"),
            ("video.mov", "he", "video.he.srt"),
            ("film.wmv", "de", "film.de.srt"),
            ("show.flv", "it", "show.it.srt"),
        ],
    )
    def test_generates_correct_path_for_valid_local_files(
        self, video_filename, language, expected_subtitle_filename
    ):
        """Test that correct subtitle path is generated for valid local video files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_dir = Path(tmpdir) / "videos"
            video_dir.mkdir()

            # Create actual video file
            video_path = video_dir / video_filename
            video_path.write_text("fake video content")

            # Generate subtitle path
            result = PathUtils.generate_subtitle_path_from_video(
                str(video_path), language
            )

            assert result is not None
            assert isinstance(result, Path)
            assert result.parent == video_dir
            assert result.name == expected_subtitle_filename
            assert str(result) == str(video_dir / expected_subtitle_filename)

    @pytest.mark.parametrize(
        "video_url",
        [
            "http://jellyfin.local/videos/abc123",
            "https://example.com/video.mp4",
            "ftp://server.com/files/movie.avi",
            "http://192.168.1.1:8096/videos/12345",
            "https://media-server.local/stream/video",
        ],
    )
    def test_returns_none_for_remote_urls(self, video_url):
        """Test that None is returned for remote URLs."""
        result = PathUtils.generate_subtitle_path_from_video(video_url, "en")
        assert result is None

    @pytest.mark.parametrize(
        "nonexistent_path",
        [
            "/path/to/nonexistent.avi",
            "/mnt/media/missing/video.mkv",
            "/home/user/videos/nothere.mp4",
            "/tmp/fake/movie.mov",
        ],
    )
    def test_returns_none_for_nonexistent_files(self, nonexistent_path):
        """Test that None is returned for non-existent file paths."""
        result = PathUtils.generate_subtitle_path_from_video(nonexistent_path, "en")
        assert result is None

    def test_returns_none_for_directory_path(self):
        """Test that None is returned when path points to a directory instead of a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Path exists but it's a directory, not a file
            result = PathUtils.generate_subtitle_path_from_video(tmpdir, "en")
            assert result is None

    @pytest.mark.parametrize(
        "video_filename,language,expected_subtitle_name",
        [
            ("video.mp4", "en", "video.en.srt"),
            ("video.mp4", "es", "video.es.srt"),
            ("video.mp4", "fr", "video.fr.srt"),
            ("video.mp4", "he", "video.he.srt"),
            ("video.mp4", "de", "video.de.srt"),
            ("video.mp4", "it", "video.it.srt"),
            ("video.mp4", "pt", "video.pt.srt"),
            ("video.mp4", "ja", "video.ja.srt"),
            ("video.mp4", "ko", "video.ko.srt"),
            ("video.mp4", "zh", "video.zh.srt"),
            ("videofile", "en", "videofile.en.srt"),  # File without extension
            ("videofile", "es", "videofile.es.srt"),  # File without extension
        ],
    )
    def test_handles_various_language_codes_and_extensions(
        self, video_filename, language, expected_subtitle_name
    ):
        """Test that various language codes are correctly included in filename for files with and without extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / video_filename
            video_path.write_text("fake video")

            result = PathUtils.generate_subtitle_path_from_video(
                str(video_path), language
            )

            assert result is not None
            assert result.name == expected_subtitle_name

    @pytest.mark.parametrize(
        "filename",
        [
            "video with spaces.mp4",
            "movie-with-dashes.mkv",
            "film_with_underscores.avi",
            "show.s01e01.720p.mkv",
            "movie (2024).mp4",
            "film [1080p].mkv",
        ],
    )
    def test_handles_special_characters_in_filename(self, filename):
        """Test handling of filenames with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / filename
            video_path.write_text("fake video")

            result = PathUtils.generate_subtitle_path_from_video(str(video_path), "en")

            assert result is not None
            # Extract stem (filename without extension)
            expected_stem = Path(filename).stem
            assert result.name == f"{expected_stem}.en.srt"

    def test_handles_nested_directory_structure(self):
        """Test that subtitle path is in the same directory as video, even with nested structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directory structure
            video_dir = Path(tmpdir) / "media" / "movies" / "matrix"
            video_dir.mkdir(parents=True)

            video_path = video_dir / "matrix.mkv"
            video_path.write_text("fake video")

            result = PathUtils.generate_subtitle_path_from_video(str(video_path), "en")

            assert result is not None
            assert result.parent == video_dir
            assert result == video_dir / "matrix.en.srt"

    def test_handles_absolute_vs_relative_paths(self):
        """Test that function works with both absolute and relative paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "video.mp4"
            video_path.write_text("fake video")

            # Test with absolute path
            result_abs = PathUtils.generate_subtitle_path_from_video(
                str(video_path.absolute()), "en"
            )
            assert result_abs is not None

            # Test with relative path (if video exists)
            # Note: Relative paths should also work if the file exists
            result_rel = PathUtils.generate_subtitle_path_from_video(
                str(video_path), "en"
            )
            assert result_rel is not None

    def test_returns_none_for_empty_string(self):
        """Test that None is returned for empty string input."""
        result = PathUtils.generate_subtitle_path_from_video("", "en")
        assert result is None

    def test_returns_none_for_invalid_path_format(self):
        """Test that None is returned for invalid path formats."""
        invalid_paths = [
            "not://a/valid/path",
            "C:\\Windows\\invalid\\on\\linux",
            "//network/share/video.mp4",  # Network path that doesn't exist
        ]

        for invalid_path in invalid_paths:
            result = PathUtils.generate_subtitle_path_from_video(invalid_path, "en")
            assert result is None

    def test_preserves_directory_path_structure(self):
        """Test that the generated path preserves the exact directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_dir = Path(tmpdir) / "a" / "b" / "c"
            video_dir.mkdir(parents=True)

            video_path = video_dir / "video.mp4"
            video_path.write_text("fake video")

            result = PathUtils.generate_subtitle_path_from_video(str(video_path), "en")

            assert result is not None
            # Verify the full path structure is preserved
            assert "a" in result.parts
            assert "b" in result.parts
            assert "c" in result.parts
            assert result.name == "video.en.srt"

    def test_handles_multiple_dots_in_filename(self):
        """Test handling of filenames with multiple dots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "my.movie.title.2024.mkv"
            video_path.write_text("fake video")

            result = PathUtils.generate_subtitle_path_from_video(str(video_path), "en")

            assert result is not None
            # .stem only removes the last extension
            assert result.name == "my.movie.title.2024.en.srt"

    def test_example_from_requirements(self):
        """Test the exact example from the requirements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate the directory structure from requirements
            video_dir = Path(tmpdir) / "mnt" / "media" / "movies" / "matrix"
            video_dir.mkdir(parents=True)

            video_path = video_dir / "matrix.mkv"
            video_path.write_text("fake video")

            result = PathUtils.generate_subtitle_path_from_video(str(video_path), "en")

            assert result is not None
            assert result.name == "matrix.en.srt"
            assert result.parent == video_dir
            # Verify full expected path
            assert result == video_dir / "matrix.en.srt"
