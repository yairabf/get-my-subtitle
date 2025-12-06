"""Utility functions for common operations across the application."""

import logging
import struct
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple, Union
from urllib.parse import urlparse
from uuid import UUID, uuid4

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


class JobIdUtils:
    """Job ID generation and validation utility functions."""

    @staticmethod
    def generate_job_id() -> UUID:
        """
        Generate a new UUID4 job identifier.

        Returns:
            UUID object (RFC 4122 compliant random UUID)

        Example:
            >>> job_id = JobIdUtils.generate_job_id()
            >>> isinstance(job_id, UUID)
            True
        """
        return uuid4()

    @staticmethod
    def generate_job_id_string() -> str:
        """
        Generate a new UUID4 job identifier as string.

        Returns:
            UUID string representation

        Example:
            >>> job_id_str = JobIdUtils.generate_job_id_string()
            >>> len(job_id_str) == 36  # Standard UUID format length
            True
        """
        return str(uuid4())

    @staticmethod
    def is_valid_job_id(job_id: Union[str, UUID]) -> bool:
        """
        Validate if input is a valid UUID format.

        Args:
            job_id: Job ID as string or UUID object

        Returns:
            True if valid UUID format, False otherwise

        Example:
            >>> JobIdUtils.is_valid_job_id("123e4567-e89b-12d3-a456-426614174000")
            True
            >>> JobIdUtils.is_valid_job_id("invalid-uuid")
            False
            >>> JobIdUtils.is_valid_job_id(uuid4())
            True
        """
        if isinstance(job_id, UUID):
            return True

        if not isinstance(job_id, str):
            return False

        try:
            UUID(job_id)
            return True
        except (ValueError, AttributeError, TypeError):
            return False

    @staticmethod
    def normalize_job_id(job_id: Union[str, UUID]) -> UUID:
        """
        Convert job_id to UUID object.

        Args:
            job_id: Job ID as string or UUID object

        Returns:
            UUID object

        Raises:
            ValueError: If job_id cannot be converted to valid UUID

        Example:
            >>> uuid_obj = uuid4()
            >>> JobIdUtils.normalize_job_id(uuid_obj) == uuid_obj
            True
            >>> uuid_str = "123e4567-e89b-12d3-a456-426614174000"
            >>> isinstance(JobIdUtils.normalize_job_id(uuid_str), UUID)
            True
        """
        if isinstance(job_id, UUID):
            return job_id

        if not isinstance(job_id, str):
            raise ValueError(
                f"Invalid job_id type: {type(job_id)}. Expected str or UUID."
            )

        try:
            return UUID(job_id)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(f"Invalid UUID format: {job_id}") from e


class ValidationUtils:
    """Generic validation utility functions."""

    @staticmethod
    def is_non_empty_string(value: Optional[str]) -> bool:
        """
        Check if string is not None, not empty, and not whitespace-only.

        Args:
            value: String value to validate

        Returns:
            True if string is non-empty and contains non-whitespace characters, False otherwise

        Example:
            >>> ValidationUtils.is_non_empty_string("hello")
            True
            >>> ValidationUtils.is_non_empty_string("")
            False
            >>> ValidationUtils.is_non_empty_string("   ")
            False
            >>> ValidationUtils.is_non_empty_string(None)
            False
        """
        if value is None:
            return False
        if not isinstance(value, str):
            return False
        return bool(value.strip())

    @staticmethod
    def is_valid_length(value: str, min_length: int, max_length: int) -> bool:
        """
        Validate string length within range.

        Args:
            value: String value to validate
            min_length: Minimum allowed length (inclusive)
            max_length: Maximum allowed length (inclusive)

        Returns:
            True if length is within range, False otherwise

        Raises:
            ValueError: If min_length > max_length or negative values

        Example:
            >>> ValidationUtils.is_valid_length("hello", 3, 10)
            True
            >>> ValidationUtils.is_valid_length("hi", 3, 10)
            False
            >>> ValidationUtils.is_valid_length("very long string", 3, 10)
            False
        """
        if min_length < 0 or max_length < 0:
            raise ValueError("min_length and max_length must be non-negative")
        if min_length > max_length:
            raise ValueError("min_length must be <= max_length")

        if not isinstance(value, str):
            return False

        length = len(value)
        return min_length <= length <= max_length

    @staticmethod
    def is_positive_number(value: Union[int, float]) -> bool:
        """
        Validate number is positive (> 0).

        Args:
            value: Number to validate

        Returns:
            True if number is positive, False otherwise

        Example:
            >>> ValidationUtils.is_positive_number(5)
            True
            >>> ValidationUtils.is_positive_number(0)
            False
            >>> ValidationUtils.is_positive_number(-1)
            False
            >>> ValidationUtils.is_positive_number(3.14)
            True
        """
        if not isinstance(value, (int, float)):
            return False
        return value > 0

    @staticmethod
    def is_non_negative_number(value: Union[int, float]) -> bool:
        """
        Validate number is non-negative (>= 0).

        Args:
            value: Number to validate

        Returns:
            True if number is non-negative, False otherwise

        Example:
            >>> ValidationUtils.is_non_negative_number(5)
            True
            >>> ValidationUtils.is_non_negative_number(0)
            True
            >>> ValidationUtils.is_non_negative_number(-1)
            False
            >>> ValidationUtils.is_non_negative_number(3.14)
            True
        """
        if not isinstance(value, (int, float)):
            return False
        return value >= 0

    @staticmethod
    def is_in_range(
        value: Union[int, float], min_val: Union[int, float], max_val: Union[int, float]
    ) -> bool:
        """
        Validate number is within range.

        Args:
            value: Number to validate
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)

        Returns:
            True if value is within range, False otherwise

        Raises:
            ValueError: If min_val > max_val

        Example:
            >>> ValidationUtils.is_in_range(5, 1, 10)
            True
            >>> ValidationUtils.is_in_range(0, 1, 10)
            False
            >>> ValidationUtils.is_in_range(15, 1, 10)
            False
            >>> ValidationUtils.is_in_range(5.5, 1.0, 10.0)
            True
        """
        if min_val > max_val:
            raise ValueError("min_val must be <= max_val")

        if not isinstance(value, (int, float)):
            return False

        return min_val <= value <= max_val

    @staticmethod
    def is_valid_url_format(url: str) -> bool:
        """
        Basic URL format validation (scheme and domain).

        Validates that URL has a valid scheme (http, https) and a netloc (domain).

        Args:
            url: URL string to validate

        Returns:
            True if URL has valid format, False otherwise

        Example:
            >>> ValidationUtils.is_valid_url_format("https://example.com")
            True
            >>> ValidationUtils.is_valid_url_format("http://example.com/path")
            True
            >>> ValidationUtils.is_valid_url_format("not-a-url")
            False
            >>> ValidationUtils.is_valid_url_format("ftp://example.com")
            False
        """
        if not isinstance(url, str) or not url.strip():
            return False

        try:
            parsed = urlparse(url)
            # Check for valid scheme (http or https)
            if parsed.scheme not in ("http", "https"):
                return False
            # Check for netloc (domain)
            if not parsed.netloc:
                return False
            return True
        except Exception:
            return False


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

    @staticmethod
    def get_current_timestamp() -> float:
        """
        Get the current Unix timestamp (seconds since epoch).

        Returns:
            Current timestamp as float (seconds since epoch)

        Example:
            >>> timestamp = DateTimeUtils.get_current_timestamp()
            >>> isinstance(timestamp, float)
            True
            >>> timestamp > 0
            True
        """
        return datetime.now(timezone.utc).timestamp()

    @staticmethod
    def get_current_timestamp_ms() -> int:
        """
        Get the current Unix timestamp in milliseconds.

        Returns:
            Current timestamp as int (milliseconds since epoch)

        Example:
            >>> timestamp_ms = DateTimeUtils.get_current_timestamp_ms()
            >>> isinstance(timestamp_ms, int)
            True
            >>> timestamp_ms > 0
            True
        """
        dt = datetime.now(timezone.utc)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def format_timestamp_iso8601(dt: datetime) -> str:
        """
        Format a datetime object as ISO 8601 string.

        Args:
            dt: Datetime object to format

        Returns:
            ISO 8601 formatted timestamp string (e.g., '2024-01-01T12:00:00+00:00')

        Example:
            >>> dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            >>> DateTimeUtils.format_timestamp_iso8601(dt)
            '2024-01-01T12:00:00+00:00'
        """
        return dt.isoformat()

    @staticmethod
    def parse_timestamp(timestamp: float) -> datetime:
        """
        Convert Unix timestamp to UTC datetime object.

        Args:
            timestamp: Unix timestamp (seconds since epoch)

        Returns:
            Datetime object in UTC timezone

        Example:
            >>> ts = 1704110400.0  # 2024-01-01 12:00:00 UTC
            >>> dt = DateTimeUtils.parse_timestamp(ts)
            >>> dt.year == 2024
            True
        """
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    @staticmethod
    def is_valid_timestamp(timestamp: float) -> bool:
        """
        Validate if timestamp is within reasonable range.

        Checks if timestamp is between 1970-01-01 and 2100-01-01.

        Args:
            timestamp: Unix timestamp (seconds since epoch)

        Returns:
            True if timestamp is within valid range, False otherwise

        Example:
            >>> DateTimeUtils.is_valid_timestamp(1704110400.0)  # 2024
            True
            >>> DateTimeUtils.is_valid_timestamp(0)  # 1970
            True
            >>> DateTimeUtils.is_valid_timestamp(4102444800.0)  # 2100
            True
            >>> DateTimeUtils.is_valid_timestamp(-1)  # Before epoch
            False
        """
        # Epoch start: 1970-01-01 00:00:00 UTC
        min_timestamp = 0.0
        # Year 2100: 4102444800 seconds since epoch
        max_timestamp = 4102444800.0
        return min_timestamp <= timestamp <= max_timestamp


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


class LanguageUtils:
    """Language code conversion utility functions."""

    # Mapping from OpenSubtitles 3-letter language codes to ISO 639-1 2-letter codes
    OPENTITLES_TO_ISO: Dict[str, str] = {
        "eng": "en",
        "heb": "he",
        "spa": "es",
        "fre": "fr",
        "ger": "de",
        "ita": "it",
        "por": "pt",
        "rus": "ru",
        "jpn": "ja",
        "kor": "ko",
        "chi": "zh",
        "ara": "ar",
        "dut": "nl",
        "pol": "pl",
        "tur": "tr",
        "swe": "sv",
        "nor": "no",
        "dan": "da",
        "fin": "fi",
        "cze": "cs",
        "hun": "hu",
        "rum": "ro",
        "gre": "el",
        "bul": "bg",
        "hrv": "hr",
        "srp": "sr",
        "slv": "sl",
        "est": "et",
        "lav": "lv",
        "lit": "lt",
        "ukr": "uk",
        "bel": "be",
        "tha": "th",
        "vie": "vi",
        "ind": "id",
        "msa": "ms",
        "hin": "hi",
        "ben": "bn",
        "tam": "ta",
        "tel": "te",
        "kan": "kn",
        "mal": "ml",
        "guj": "gu",
        "pan": "pa",
        "urd": "ur",
    }

    @staticmethod
    def opensubtitles_to_iso(opensubtitles_code: str) -> str:
        """
        Convert OpenSubtitles 3-letter language code to ISO 639-1 2-letter code.

        Args:
            opensubtitles_code: OpenSubtitles language code (e.g., 'eng', 'heb')

        Returns:
            ISO 639-1 2-letter code (e.g., 'en', 'he'), or first 2 letters for unknown codes

        Note:
            For unknown 3-letter codes, returns first 2 letters which may not be a valid ISO code.
            A warning is logged for unknown codes.

        Example:
            >>> LanguageUtils.opensubtitles_to_iso('eng')
            'en'
            >>> LanguageUtils.opensubtitles_to_iso('heb')
            'he'
            >>> LanguageUtils.opensubtitles_to_iso('en')  # Already ISO
            'en'
        """
        if not opensubtitles_code:
            return opensubtitles_code

        # If already 2-letter, return as-is
        if len(opensubtitles_code) == 2:
            return opensubtitles_code.lower()

        # Convert 3-letter to 2-letter
        normalized = opensubtitles_code.lower()
        iso_code = LanguageUtils.OPENTITLES_TO_ISO.get(normalized, normalized[:2])

        # Log warning for unknown codes
        if normalized not in LanguageUtils.OPENTITLES_TO_ISO:
            logger.warning(
                f"Unknown OpenSubtitles language code '{opensubtitles_code}' - "
                f"using '{iso_code}' (may not be a valid ISO 639-1 code)"
            )

        return iso_code

    # Mapping from ISO 639-1 2-letter codes to language names for OpenAI
    ISO_TO_LANGUAGE_NAME: Dict[str, str] = {
        "en": "English",
        "he": "Hebrew",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "ar": "Arabic",
        "nl": "Dutch",
        "pl": "Polish",
        "tr": "Turkish",
        "sv": "Swedish",
        "no": "Norwegian",
        "da": "Danish",
        "fi": "Finnish",
        "cs": "Czech",
        "hu": "Hungarian",
        "ro": "Romanian",
        "el": "Greek",
        "bg": "Bulgarian",
        "hr": "Croatian",
        "sr": "Serbian",
        "sl": "Slovenian",
        "et": "Estonian",
        "lv": "Latvian",
        "lt": "Lithuanian",
        "uk": "Ukrainian",
        "be": "Belarusian",
        "th": "Thai",
        "vi": "Vietnamese",
        "id": "Indonesian",
        "ms": "Malay",
        "hi": "Hindi",
        "bn": "Bengali",
        "ta": "Tamil",
        "te": "Telugu",
        "kn": "Kannada",
        "ml": "Malayalam",
        "gu": "Gujarati",
        "pa": "Punjabi",
        "ur": "Urdu",
    }

    @staticmethod
    def iso_to_language_name(iso_code: str) -> str:
        """
        Convert ISO 639-1 2-letter code to language name for OpenAI API.

        Args:
            iso_code: ISO 639-1 2-letter code (e.g., 'en', 'he')

        Returns:
            Language name (e.g., 'English', 'Hebrew'), or the code itself if not found

        Example:
            >>> LanguageUtils.iso_to_language_name('en')
            'English'
            >>> LanguageUtils.iso_to_language_name('he')
            'Hebrew'
        """
        if not iso_code:
            return iso_code

        normalized = iso_code.lower()
        return LanguageUtils.ISO_TO_LANGUAGE_NAME.get(normalized, iso_code)


class URLUtils:
    """URL generation utility functions."""

    @staticmethod
    def generate_download_url(request_id: UUID, target_language: str, base_url: str) -> str:
        """
        Generate download URL for translated subtitle file.

        Args:
            request_id: Unique identifier for the translation request
            target_language: Target language code (e.g., 'en', 'es')
            base_url: Base URL for download links (from settings)

        Returns:
            Full download URL string

        Example:
            >>> from uuid import uuid4
            >>> request_id = uuid4()
            >>> URLUtils.generate_download_url(request_id, 'es', 'https://example.com/subtitles')
            'https://example.com/subtitles/{request_id}.es.srt'
        """
        return f"{base_url}/{request_id}.{target_language}.srt"


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

    @staticmethod
    def generate_subtitle_path_from_source(
        source_subtitle_path: str, target_language: str
    ) -> Path:
        """
        Generate subtitle file path by replacing language code in source path.

        Args:
            source_subtitle_path: Path to source subtitle file (e.g., '/path/video.en.srt')
            target_language: Target language code (e.g., 'he') - must be a valid 2-letter ISO code

        Returns:
            Path with target language code (e.g., '/path/video.he.srt')

        Raises:
            ValueError: If target_language is invalid (not 2-letter alphabetic)
            ValueError: If source_subtitle_path is empty or invalid

        Example:
            >>> PathUtils.generate_subtitle_path_from_source('/path/video.en.srt', 'he')
            Path('/path/video.he.srt')
        """
        # Validate inputs
        if not source_subtitle_path:
            raise ValueError("source_subtitle_path cannot be empty")

        if (
            not target_language
            or len(target_language) != 2
            or not target_language.isalpha()
        ):
            raise ValueError(
                f"Invalid target language code: '{target_language}'. "
                "Must be a 2-letter alphabetic ISO 639-1 code."
            )

        source_path = Path(source_subtitle_path)

        # Resolve path to handle relative paths and normalize
        if not source_path.is_absolute():
            source_path = source_path.resolve()

        stem = source_path.stem  # e.g., 'video.en'

        # Try to detect and replace language code
        # Check if the last segment before .srt is a known ISO language code
        if "." in stem:
            parts = stem.rsplit(".", 1)
            if len(parts) == 2:
                potential_lang = parts[1].lower()
                # Check if it's a known ISO code (more reliable than just checking length)
                if (
                    len(potential_lang) == 2
                    and potential_lang in LanguageUtils.OPENTITLES_TO_ISO.values()
                ):
                    base_name = parts[0]
                else:
                    # Not a recognized language code, keep the full stem
                    base_name = stem
            else:
                base_name = stem
        else:
            base_name = stem

        # Create new filename with target language
        new_filename = f"{base_name}.{target_language.lower()}.srt"
        return source_path.parent / new_filename
