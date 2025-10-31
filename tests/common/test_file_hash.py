"""Tests for file hash utility functions."""

import struct
import tempfile
from pathlib import Path

import pytest

from common.utils import FileHashUtils


class TestFileHashUtils:
    """Test file hash calculation utilities."""

    def test_calculate_opensubtitles_hash_success(self):
        """Test successful hash calculation for a valid file."""
        # Create a temporary file with known content (> 128KB)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            # Write 256KB of data
            tmp_file.write(b"A" * (256 * 1024))
            tmp_file_path = tmp_file.name

        try:
            result = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)

            assert result is not None
            hash_string, file_size = result

            # Verify hash is 16-character hex string
            assert isinstance(hash_string, str)
            assert len(hash_string) == 16
            assert all(c in "0123456789abcdef" for c in hash_string)

            # Verify file size is correct
            assert file_size == 256 * 1024

        finally:
            # Clean up
            Path(tmp_file_path).unlink()

    def test_calculate_hash_consistency(self):
        """Test that same file produces same hash."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"B" * (256 * 1024))
            tmp_file_path = tmp_file.name

        try:
            # Calculate hash twice
            result1 = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)
            result2 = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)

            assert result1 is not None
            assert result2 is not None

            hash1, size1 = result1
            hash2, size2 = result2

            # Both should be identical
            assert hash1 == hash2
            assert size1 == size2

        finally:
            Path(tmp_file_path).unlink()

    def test_calculate_hash_file_not_found(self):
        """Test that missing file returns None."""
        result = FileHashUtils.calculate_opensubtitles_hash(
            "/nonexistent/path/to/file.mp4"
        )

        assert result is None

    def test_calculate_hash_file_too_small(self):
        """Test that file smaller than 128KB returns None."""
        # Create a small file (< 128KB)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"C" * 1024)  # Only 1KB
            tmp_file_path = tmp_file.name

        try:
            result = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)

            # Should return None for files < 128KB
            assert result is None

        finally:
            Path(tmp_file_path).unlink()

    def test_calculate_hash_exactly_128kb(self):
        """Test hash calculation for file exactly 128KB."""
        # Create a file exactly 128KB (minimum size)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(b"D" * (128 * 1024))
            tmp_file_path = tmp_file.name

        try:
            result = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)

            assert result is not None
            hash_string, file_size = result

            assert len(hash_string) == 16
            assert file_size == 128 * 1024

        finally:
            Path(tmp_file_path).unlink()

    def test_calculate_hash_directory_path(self):
        """Test that directory path returns None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = FileHashUtils.calculate_opensubtitles_hash(tmp_dir)

            assert result is None

    def test_calculate_hash_permission_denied(self, tmp_path):
        """Test handling of permission errors."""
        # Create a file
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"E" * (256 * 1024))

        # Make file unreadable (Unix-like systems only)
        import os
        import sys

        if sys.platform != "win32":
            test_file.chmod(0o000)

            try:
                result = FileHashUtils.calculate_opensubtitles_hash(str(test_file))

                # Should return None on permission error
                assert result is None

            finally:
                # Restore permissions for cleanup
                test_file.chmod(0o644)
        else:
            # Skip permission test on Windows
            pytest.skip("Permission test not applicable on Windows")

    def test_calculate_hash_known_values(self):
        """Test hash calculation with known expected values."""
        # Create a file with specific content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            # Write known pattern to verify hash algorithm
            # First 64KB: all zeros
            tmp_file.write(b"\x00" * (64 * 1024))
            # Middle: some data
            tmp_file.write(b"\xFF" * (64 * 1024))
            # Last 64KB: pattern
            tmp_file.write(b"\xAB\xCD\xEF\x12" * (16 * 1024))
            tmp_file_path = tmp_file.name

        try:
            result = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)

            assert result is not None
            hash_string, file_size = result

            # Verify the hash format
            assert len(hash_string) == 16
            assert file_size == 192 * 1024

            # Hash should be deterministic
            result2 = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)
            assert result2 is not None
            hash_string2, _ = result2
            assert hash_string == hash_string2

        finally:
            Path(tmp_file_path).unlink()

    def test_calculate_hash_different_files_different_hashes(self):
        """Test that different files produce different hashes."""
        # Create two files with different content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file1:
            tmp_file1.write(b"A" * (256 * 1024))
            tmp_file1_path = tmp_file1.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file2:
            tmp_file2.write(b"B" * (256 * 1024))
            tmp_file2_path = tmp_file2.name

        try:
            result1 = FileHashUtils.calculate_opensubtitles_hash(tmp_file1_path)
            result2 = FileHashUtils.calculate_opensubtitles_hash(tmp_file2_path)

            assert result1 is not None
            assert result2 is not None

            hash1, _ = result1
            hash2, _ = result2

            # Different content should produce different hashes
            assert hash1 != hash2

        finally:
            Path(tmp_file1_path).unlink()
            Path(tmp_file2_path).unlink()

    def test_calculate_hash_large_file(self):
        """Test hash calculation for a large file (only reads first/last 64KB)."""
        # Create a large file (approximately 9-10MB)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            # Write first 64KB
            tmp_file.write(b"START" * (13 * 1024))  # ~65KB
            # Write middle (won't be read)
            tmp_file.write(b"\x00" * (9 * 1024 * 1024))  # 9MB
            # Write last 64KB
            tmp_file.write(b"END__" * (13 * 1024))  # ~65KB
            tmp_file_path = tmp_file.name

        try:
            result = FileHashUtils.calculate_opensubtitles_hash(tmp_file_path)

            assert result is not None
            hash_string, file_size = result

            assert len(hash_string) == 16
            # File size should be at least 9MB (actual size varies slightly)
            assert file_size > 9 * 1024 * 1024

        finally:
            Path(tmp_file_path).unlink()

    def test_calculate_hash_empty_string_path(self):
        """Test handling of empty string path."""
        result = FileHashUtils.calculate_opensubtitles_hash("")

        assert result is None

    def test_calculate_hash_relative_path(self):
        """Test hash calculation with relative path."""
        # Create file in current directory
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp4", dir="."
        ) as tmp_file:
            tmp_file.write(b"F" * (256 * 1024))
            tmp_file_path = tmp_file.name

        try:
            # Use just the filename (relative path)
            filename = Path(tmp_file_path).name
            result = FileHashUtils.calculate_opensubtitles_hash(filename)

            assert result is not None
            hash_string, file_size = result

            assert len(hash_string) == 16
            assert file_size == 256 * 1024

        finally:
            Path(tmp_file_path).unlink()
