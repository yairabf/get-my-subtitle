"""Tests for utility functions."""

import pytest
from datetime import datetime, timezone
from common.utils import MathUtils, StringUtils, DateTimeUtils, StatusProgressCalculator
from common.schemas import SubtitleStatus


class TestMathUtils:
    """Test mathematical utility functions."""

    @pytest.mark.parametrize(
        "completed,total,expected",
        [
            (0, 10, 0.0),
            (5, 10, 50.0),
            (10, 10, 100.0),
            (7, 10, 70.0),
            (3, 12, 25.0),
            (1, 3, 33.33),  # Approximate due to floating point
            (0, 0, 0.0),  # Edge case: zero total
            (5, 0, 0.0),  # Edge case: zero total with completed items
            (10, -5, 0.0),  # Edge case: negative total
        ],
    )
    def test_calculate_percentage(self, completed, total, expected):
        """Test percentage calculation with various inputs."""
        result = MathUtils.calculate_percentage(completed, total)
        # Use approximate comparison for floating point
        assert abs(result - expected) < 0.01


class TestStringUtils:
    """Test string utility functions."""

    @pytest.mark.parametrize(
        "job_id,expected",
        [
            ("123-456", "job:123-456"),
            ("abc", "job:abc"),
            ("", "job:"),
            ("uuid-with-dashes", "job:uuid-with-dashes"),
        ],
    )
    def test_generate_job_key(self, job_id, expected):
        """Test job key generation with various inputs."""
        result = StringUtils.generate_job_key(job_id)
        assert result == expected

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("HELLO", "hello"),
            ("MixedCase", "mixedcase"),
            ("already_lowercase", "already_lowercase"),
            ("", ""),
            ("123ABC", "123abc"),
        ],
    )
    def test_safe_to_lowercase(self, text, expected):
        """Test safe lowercase conversion."""
        result = StringUtils.safe_to_lowercase(text)
        assert result == expected

    def test_safe_to_lowercase_with_none(self):
        """Test safe lowercase conversion with None input."""
        result = StringUtils.safe_to_lowercase(None)
        assert result == ""


class TestDateTimeUtils:
    """Test date and time utility functions."""

    def test_get_current_utc_datetime(self):
        """Test getting current UTC datetime."""
        result = DateTimeUtils.get_current_utc_datetime()
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    @pytest.mark.parametrize(
        "dt,expected",
        [
            (datetime(2024, 1, 1, 12, 0, 0), "2024-01-01 12:00:00"),
            (datetime(2024, 12, 31, 23, 59, 59), "2024-12-31 23:59:59"),
            (datetime(2000, 6, 15, 6, 30, 45), "2000-06-15 06:30:45"),
        ],
    )
    def test_format_timestamp_for_logging(self, dt, expected):
        """Test timestamp formatting for logging."""
        result = DateTimeUtils.format_timestamp_for_logging(dt)
        assert result == expected

    def test_get_date_string_for_log_file(self):
        """Test getting date string for log file names."""
        result = DateTimeUtils.get_date_string_for_log_file()
        assert isinstance(result, str)
        assert len(result) == 8  # YYYYMMDD format
        assert result.isdigit()


class TestStatusProgressCalculator:
    """Test status progress calculation functions."""

    @pytest.mark.parametrize(
        "status,expected_progress",
        [
            (SubtitleStatus.PENDING, 0),
            (SubtitleStatus.DOWNLOADING, 25),
            (SubtitleStatus.TRANSLATING, 75),
            (SubtitleStatus.COMPLETED, 100),
            (SubtitleStatus.FAILED, 0),
        ],
    )
    def test_calculate_progress_for_status(self, status, expected_progress):
        """Test progress calculation for different subtitle statuses."""
        progress_mapping = (
            StatusProgressCalculator.get_subtitle_status_progress_mapping()
        )
        result = StatusProgressCalculator.calculate_progress_for_status(
            status, progress_mapping
        )
        assert result == expected_progress

    def test_get_subtitle_status_progress_mapping(self):
        """Test getting the subtitle status progress mapping."""
        mapping = StatusProgressCalculator.get_subtitle_status_progress_mapping()

        assert isinstance(mapping, dict)
        assert len(mapping) == 5
        assert SubtitleStatus.PENDING in mapping
        assert SubtitleStatus.DOWNLOADING in mapping
        assert SubtitleStatus.TRANSLATING in mapping
        assert SubtitleStatus.COMPLETED in mapping
        assert SubtitleStatus.FAILED in mapping

    def test_calculate_progress_for_unknown_status(self):
        """Test progress calculation with empty mapping returns default."""
        # Create a mock status that's not in mapping
        progress_mapping = {}
        result = StatusProgressCalculator.calculate_progress_for_status(
            SubtitleStatus.PENDING, progress_mapping
        )
        assert result == 0  # Should return default value
