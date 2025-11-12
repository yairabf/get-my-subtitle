"""Tests for utility functions."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from common.schemas import SubtitleStatus
from common.utils import (
    DateTimeUtils,
    JobIdUtils,
    MathUtils,
    StatusProgressCalculator,
    StringUtils,
    ValidationUtils,
)


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

    def test_get_current_timestamp(self):
        """Test getting current Unix timestamp."""
        result = DateTimeUtils.get_current_timestamp()
        assert isinstance(result, float)
        assert result > 0
        # Should be close to current time (within 1 second)
        current_time = datetime.now(timezone.utc).timestamp()
        assert abs(result - current_time) < 1.0

    def test_get_current_timestamp_ms(self):
        """Test getting current Unix timestamp in milliseconds."""
        result = DateTimeUtils.get_current_timestamp_ms()
        assert isinstance(result, int)
        assert result > 0
        # Should be close to current time (within 1 second = 1000ms)
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        assert abs(result - current_time_ms) < 1000

    @pytest.mark.parametrize(
        "dt,expected_prefix",
        [
            (
                datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "2024-01-01T12:00:00",
            ),
            (
                datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                "2024-12-31T23:59:59",
            ),
            (
                datetime(2000, 6, 15, 6, 30, 45, tzinfo=timezone.utc),
                "2000-06-15T06:30:45",
            ),
        ],
    )
    def test_format_timestamp_iso8601(self, dt, expected_prefix):
        """Test ISO 8601 timestamp formatting."""
        result = DateTimeUtils.format_timestamp_iso8601(dt)
        assert isinstance(result, str)
        assert result.startswith(expected_prefix)
        assert "+00:00" in result or "Z" in result or result.endswith("+00:00")

    @pytest.mark.parametrize(
        "timestamp,expected_year",
        [
            (1704110400.0, 2024),  # 2024-01-01 12:00:00 UTC
            (946684800.0, 2000),  # 2000-01-01 00:00:00 UTC
            (0.0, 1970),  # Epoch start
        ],
    )
    def test_parse_timestamp(self, timestamp, expected_year):
        """Test parsing Unix timestamp to datetime."""
        result = DateTimeUtils.parse_timestamp(timestamp)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.year == expected_year

    @pytest.mark.parametrize(
        "timestamp,expected",
        [
            (1704110400.0, True),  # 2024
            (0.0, True),  # 1970 (epoch start)
            (4102444800.0, True),  # 2100
            (4102444801.0, False),  # After 2100
            (-1.0, False),  # Before epoch
            (10000000000.0, False),  # Far future
        ],
    )
    def test_is_valid_timestamp(self, timestamp, expected):
        """Test timestamp validation."""
        result = DateTimeUtils.is_valid_timestamp(timestamp)
        assert result == expected


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


class TestJobIdUtils:
    """Test job ID utility functions."""

    def test_generate_job_id(self):
        """Test generating a new job ID."""
        job_id = JobIdUtils.generate_job_id()
        assert isinstance(job_id, UUID)
        # Generate multiple to ensure uniqueness
        job_ids = [JobIdUtils.generate_job_id() for _ in range(10)]
        assert len(set(job_ids)) == 10  # All should be unique

    def test_generate_job_id_string(self):
        """Test generating a new job ID as string."""
        job_id_str = JobIdUtils.generate_job_id_string()
        assert isinstance(job_id_str, str)
        assert len(job_id_str) == 36  # Standard UUID format length
        # Should be valid UUID
        uuid_obj = UUID(job_id_str)
        assert isinstance(uuid_obj, UUID)

    @pytest.mark.parametrize(
        "job_id,expected",
        [
            ("123e4567-e89b-12d3-a456-426614174000", True),
            ("00000000-0000-0000-0000-000000000000", True),  # Nil UUID
            ("ffffffff-ffff-ffff-ffff-ffffffffffff", True),  # Max UUID
            ("invalid-uuid", False),
            ("123e4567-e89b-12d3-a456", False),  # Incomplete UUID
            ("", False),
            ("not-a-uuid-at-all", False),
        ],
    )
    def test_is_valid_job_id_string(self, job_id, expected):
        """Test job ID validation with string inputs."""
        result = JobIdUtils.is_valid_job_id(job_id)
        assert result == expected

    def test_is_valid_job_id_uuid_object(self):
        """Test job ID validation with UUID object."""
        uuid_obj = uuid4()
        result = JobIdUtils.is_valid_job_id(uuid_obj)
        assert result is True

    @pytest.mark.parametrize(
        "job_id,should_raise",
        [
            (None, True),
            (123, True),
            ([], True),
            ({}, True),
        ],
    )
    def test_is_valid_job_id_invalid_types(self, job_id, should_raise):
        """Test job ID validation with invalid types."""
        result = JobIdUtils.is_valid_job_id(job_id)
        assert result is False

    def test_normalize_job_id_uuid_object(self):
        """Test normalizing UUID object."""
        uuid_obj = uuid4()
        result = JobIdUtils.normalize_job_id(uuid_obj)
        assert result == uuid_obj
        assert isinstance(result, UUID)

    @pytest.mark.parametrize(
        "job_id_str",
        [
            "123e4567-e89b-12d3-a456-426614174000",
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
        ],
    )
    def test_normalize_job_id_string(self, job_id_str):
        """Test normalizing UUID string."""
        result = JobIdUtils.normalize_job_id(job_id_str)
        assert isinstance(result, UUID)
        assert str(result) == job_id_str

    @pytest.mark.parametrize(
        "invalid_job_id",
        [
            "invalid-uuid",
            "",
            "123e4567-e89b-12d3-a456",
            "not-a-uuid",
        ],
    )
    def test_normalize_job_id_invalid_string(self, invalid_job_id):
        """Test normalizing invalid UUID string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid UUID format"):
            JobIdUtils.normalize_job_id(invalid_job_id)

    @pytest.mark.parametrize(
        "invalid_job_id",
        [
            None,
            123,
            [],
            {},
        ],
    )
    def test_normalize_job_id_invalid_type(self, invalid_job_id):
        """Test normalizing invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid job_id type"):
            JobIdUtils.normalize_job_id(invalid_job_id)


class TestValidationUtils:
    """Test validation utility functions."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("hello", True),
            ("  hello  ", True),  # Whitespace trimmed
            ("", False),
            ("   ", False),  # Only whitespace
            (None, False),
            ("a", True),  # Single character
        ],
    )
    def test_is_non_empty_string(self, value, expected):
        """Test non-empty string validation."""
        result = ValidationUtils.is_non_empty_string(value)
        assert result == expected

    def test_is_non_empty_string_invalid_type(self):
        """Test non-empty string validation with invalid types."""
        assert ValidationUtils.is_non_empty_string(123) is False
        assert ValidationUtils.is_non_empty_string([]) is False
        assert ValidationUtils.is_non_empty_string({}) is False

    @pytest.mark.parametrize(
        "value,min_length,max_length,expected",
        [
            ("hello", 3, 10, True),
            ("hi", 3, 10, False),  # Too short
            ("very long string", 3, 10, False),  # Too long
            ("abc", 3, 10, True),  # Exact min
            ("abcdefghij", 3, 10, True),  # Exact max
            ("ab", 3, 10, False),  # Below min
            ("abcdefghijk", 3, 10, False),  # Above max
        ],
    )
    def test_is_valid_length(self, value, min_length, max_length, expected):
        """Test string length validation."""
        result = ValidationUtils.is_valid_length(value, min_length, max_length)
        assert result == expected

    def test_is_valid_length_invalid_type(self):
        """Test string length validation with invalid types."""
        assert ValidationUtils.is_valid_length(123, 1, 10) is False
        assert ValidationUtils.is_valid_length(None, 1, 10) is False

    @pytest.mark.parametrize(
        "min_length,max_length",
        [
            (5, 3),  # min > max
            (-1, 10),  # Negative min
            (3, -1),  # Negative max
        ],
    )
    def test_is_valid_length_invalid_params(self, min_length, max_length):
        """Test string length validation with invalid parameters."""
        with pytest.raises(ValueError):
            ValidationUtils.is_valid_length("test", min_length, max_length)

    @pytest.mark.parametrize(
        "value,expected",
        [
            (5, True),
            (0, False),
            (-1, False),
            (3.14, True),
            (0.0, False),
            (-0.1, False),
        ],
    )
    def test_is_positive_number(self, value, expected):
        """Test positive number validation."""
        result = ValidationUtils.is_positive_number(value)
        assert result == expected

    def test_is_positive_number_invalid_type(self):
        """Test positive number validation with invalid types."""
        assert ValidationUtils.is_positive_number("5") is False
        assert ValidationUtils.is_positive_number(None) is False
        assert ValidationUtils.is_positive_number([]) is False

    @pytest.mark.parametrize(
        "value,expected",
        [
            (5, True),
            (0, True),  # Zero is non-negative
            (-1, False),
            (3.14, True),
            (0.0, True),  # Zero is non-negative
            (-0.1, False),
        ],
    )
    def test_is_non_negative_number(self, value, expected):
        """Test non-negative number validation."""
        result = ValidationUtils.is_non_negative_number(value)
        assert result == expected

    def test_is_non_negative_number_invalid_type(self):
        """Test non-negative number validation with invalid types."""
        assert ValidationUtils.is_non_negative_number("5") is False
        assert ValidationUtils.is_non_negative_number(None) is False

    @pytest.mark.parametrize(
        "value,min_val,max_val,expected",
        [
            (5, 1, 10, True),
            (0, 1, 10, False),  # Below min
            (15, 1, 10, False),  # Above max
            (1, 1, 10, True),  # Exact min
            (10, 1, 10, True),  # Exact max
            (5.5, 1.0, 10.0, True),  # Float values
            (0.5, 1.0, 10.0, False),  # Float below min
        ],
    )
    def test_is_in_range(self, value, min_val, max_val, expected):
        """Test number range validation."""
        result = ValidationUtils.is_in_range(value, min_val, max_val)
        assert result == expected

    def test_is_in_range_invalid_type(self):
        """Test number range validation with invalid types."""
        assert ValidationUtils.is_in_range("5", 1, 10) is False
        assert ValidationUtils.is_in_range(None, 1, 10) is False

    def test_is_in_range_invalid_params(self):
        """Test number range validation with invalid parameters."""
        with pytest.raises(ValueError, match="min_val must be <= max_val"):
            ValidationUtils.is_in_range(5, 10, 1)

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://example.com", True),
            ("http://example.com", True),
            ("https://example.com/path", True),
            ("http://example.com/path?query=1", True),
            ("https://example.com:8080/path", True),
            ("not-a-url", False),
            ("ftp://example.com", False),  # Invalid scheme
            ("", False),  # Empty string
            ("   ", False),  # Whitespace only
            ("https://", False),  # No domain
            ("http://", False),  # No domain
        ],
    )
    def test_is_valid_url_format(self, url, expected):
        """Test URL format validation."""
        result = ValidationUtils.is_valid_url_format(url)
        assert result == expected

    def test_is_valid_url_format_invalid_type(self):
        """Test URL format validation with invalid types."""
        assert ValidationUtils.is_valid_url_format(None) is False
        assert ValidationUtils.is_valid_url_format(123) is False
        assert ValidationUtils.is_valid_url_format([]) is False
