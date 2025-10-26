"""Utility functions for common operations across the application."""

from datetime import datetime, timezone
from typing import Dict
from enum import Enum


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
