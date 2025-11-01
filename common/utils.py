"""Utility functions for common operations across the application."""

import logging
import struct
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MathUtils:
    """Mathematical utility functions."""

    @staticmethod
    def calculate_percentage(completed: int, total: int) -> float:
        """
        Calculate the percentage of completed items out of total items.

        Args:
            completed: Number of completed items
            total: Total number of items

        Returns:
            Percentage as a float between 0 and 100

        Example:
            >>> MathUtils.calculate_percentage(5, 10)
            50.0
        """
        if total <= 0:
            return 0.0
        return (completed / total) * 100


class StringUtils:
    """String manipulation utility functions."""

    @staticmethod
    def generate_job_key(job_id: str) -> str:
        """
        Generate a Redis key for a job.

        Args:
            job_id: Unique identifier for the job

        Returns:
            Formatted Redis key string

        Example:
            >>> StringUtils.generate_job_key("123-456")
            'job:123-456'
        """
        return f"job:{job_id}"

    @staticmethod
    def safe_to_lowercase(text: str) -> str:
        """
        Safely convert text to lowercase.

        Args:
            text: Input text

        Returns:
            Lowercase text, or empty string if input is None
        """
        return text.lower() if text else ""


class DateTimeUtils:
    """Date and time utility functions."""

    @staticmethod
    def get_current_utc_datetime() -> datetime:
        """
        Get the current UTC datetime.

        Returns:
            Current datetime in UTC timezone

        Note:
            Uses datetime.now(timezone.utc) instead of deprecated datetime.utcnow()
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def format_timestamp_for_logging(dt: datetime) -> str:
        """
        Format a datetime object for logging purposes.

        Args:
            dt: Datetime object to format

        Returns:
            Formatted timestamp string

        Example:
            >>> dt = datetime(2024, 1, 1, 12, 0, 0)
            >>> DateTimeUtils.format_timestamp_for_logging(dt)
            '2024-01-01 12:00:00'
        """
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def get_date_string_for_log_file() -> str:
        """
        Get a date string suitable for log file names.

        Returns:
            Date string in YYYYMMDD format

        Example:
            >>> DateTimeUtils.get_date_string_for_log_file()
            '20240101'
        """
        return datetime.now().strftime("%Y%m%d")


class StatusProgressCalculator:
    """Calculate progress based on status values."""

    @staticmethod
    def calculate_progress_for_status(
        status: Enum, progress_mapping: Dict[Enum, int]
    ) -> int:
        """
        Calculate progress percentage based on status.

        Args:
            status: Current status enum value
            progress_mapping: Dictionary mapping status to progress percentage

        Returns:
            Progress percentage (0-100)

        Example:
            >>> from common.schemas import SubtitleStatus
            >>> mapping = {
            ...     SubtitleStatus.PENDING: 0,
            ...     SubtitleStatus.DOWNLOADING: 25,
            ...     SubtitleStatus.COMPLETED: 100
            ... }
            >>> StatusProgressCalculator.calculate_progress_for_status(
            ...     SubtitleStatus.DOWNLOADING, mapping
            ... )
            25
        """
        return progress_mapping.get(status, 0)

    @staticmethod
    def get_subtitle_status_progress_mapping():
        """
        Get the standard progress mapping for subtitle processing statuses.

        Returns:
            Dictionary mapping SubtitleStatus to progress percentage
        """
        from common.schemas import SubtitleStatus

        return {
            SubtitleStatus.PENDING: 0,
            SubtitleStatus.DOWNLOADING: 25,
            SubtitleStatus.TRANSLATING: 75,
            SubtitleStatus.COMPLETED: 100,
            SubtitleStatus.FAILED: 0,
        }


class FileHashUtils:
    """File hashing utility functions for subtitle matching."""

    @staticmethod
    def calculate_opensubtitles_hash(file_path: str) -> Optional[Tuple[str, int]]:
        """
        Calculate OpenSubtitles hash for a video file.

        The OpenSubtitles hash algorithm:
        1. Read first 64KB of file
        2. Read last 64KB of file
        3. Sum all 64-bit chunks from both blocks with the file size
        4. Return as 16-character hex string

        Args:
            file_path: Path to the video file

        Returns:
            Tuple of (hash_string, file_size) if successful, None if error

        Note:
            Returns None for files that cannot be accessed, are too small,
            or encounter any errors during calculation.

        Example:
            >>> result = FileHashUtils.calculate_opensubtitles_hash("/path/to/video.mp4")
            >>> if result:
            ...     hash_str, file_size = result
            ...     print(f"Hash: {hash_str}, Size: {file_size}")
        """
        try:
            path = Path(file_path)

            # Check if file exists and is accessible
            if not path.exists() or not path.is_file():
                logger.debug(f"File does not exist or is not a file: {file_path}")
                return None

            # Get file size
            file_size = path.stat().st_size

            # OpenSubtitles hash requires at least 128KB (64KB * 2)
            if file_size < 65536 * 2:
                logger.debug(
                    f"File too small for OpenSubtitles hash (< 128KB): {file_path}"
                )
                return None

            # Initialize hash with file size
            hash_value = file_size

            # Read and process first 64KB
            with open(path, "rb") as f:
                # Read first 64KB in 8-byte chunks
                for _ in range(65536 // 8):
                    chunk = f.read(8)
                    if len(chunk) < 8:
                        break
                    (value,) = struct.unpack("<Q", chunk)
                    hash_value = (hash_value + value) & 0xFFFFFFFFFFFFFFFF

                # Seek to last 64KB
                f.seek(max(0, file_size - 65536), 0)

                # Read last 64KB in 8-byte chunks
                for _ in range(65536 // 8):
                    chunk = f.read(8)
                    if len(chunk) < 8:
                        break
                    (value,) = struct.unpack("<Q", chunk)
                    hash_value = (hash_value + value) & 0xFFFFFFFFFFFFFFFF

            # Format as 16-character hex string (64-bit value)
            hash_string = f"{hash_value:016x}"

            logger.debug(
                f"Calculated OpenSubtitles hash for {file_path}: {hash_string}"
            )
            return (hash_string, file_size)

        except PermissionError:
            logger.warning(f"Permission denied accessing file: {file_path}")
            return None
        except OSError as e:
            logger.warning(f"OS error calculating hash for {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calculating hash for {file_path}: {e}")
            return None


class PathUtils:
    """Path manipulation utility functions."""

    @staticmethod
    def generate_subtitle_path_from_video(
        video_path: str, language: str
    ) -> Optional[Path]:
        """
        Generate subtitle file path based on video file location.

        Args:
            video_path: Path to the video file
            language: Language code (e.g., 'en', 'es')

        Returns:
            Path object for subtitle file, or None if video_path is not a local file

        Example:
            >>> PathUtils.generate_subtitle_path_from_video(
            ...     "/mnt/media/movies/matrix/matrix.mkv", "en"
            ... )
            Path('/mnt/media/movies/matrix/matrix.en.srt')
        """
        try:
            video_file_path = Path(video_path)

            # Check if it's a valid local file
            if not video_file_path.exists() or not video_file_path.is_file():
                return None

            # Extract directory and basename (without extension)
            video_dir = video_file_path.parent
            video_stem = video_file_path.stem

            # Generate subtitle filename: {basename}.{language}.srt
            subtitle_filename = f"{video_stem}.{language}.srt"

            # Return full path
            return video_dir / subtitle_filename

        except Exception as e:
            logger.debug(f"Error generating subtitle path from video path: {e}")
            return None
