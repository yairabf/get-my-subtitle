"""SRT subtitle parser and formatter for translation workflows."""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Constants for error message display
MAX_MISSING_SEGMENTS_TO_DISPLAY = 10


class TranslationCountMismatchError(ValueError):
    """
    Exception raised when the number of translated segments doesn't match the expected count.

    This is typically a transient error that can occur due to:
    - API response formatting issues
    - Parsing failures due to unexpected response format
    - Truncated responses

    This error should be retried as it may succeed on subsequent attempts.
    """

    def __init__(
        self,
        expected_count: int,
        actual_count: int,
        chunk_index: int = None,
        total_chunks: int = None,
        parsed_segment_numbers: List[int] = None,
        response_sample: str = None,
    ):
        """
        Initialize the error with detailed context.

        Args:
            expected_count: Expected number of translations
            actual_count: Actual number of translations received
            chunk_index: Index of the chunk being translated (if available)
            total_chunks: Total number of chunks (if available)
            parsed_segment_numbers: List of segment numbers that were successfully parsed
            response_sample: Sample of the API response for debugging
        """
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks
        self.parsed_segment_numbers = parsed_segment_numbers or []
        self.response_sample = response_sample

        # Build detailed error message
        message = (
            f"Translation count mismatch: expected {expected_count} translations, "
            f"but got {actual_count} (missing {expected_count - actual_count})"
        )

        if chunk_index is not None and total_chunks is not None:
            message += f" in chunk {chunk_index + 1}/{total_chunks}"

        if parsed_segment_numbers:
            missing = set(range(1, expected_count + 1)) - set(parsed_segment_numbers)
            if missing:
                missing_list = sorted(list(missing))[:MAX_MISSING_SEGMENTS_TO_DISPLAY]
                message += f". Missing segment numbers: {missing_list}"
                if len(missing) > MAX_MISSING_SEGMENTS_TO_DISPLAY:
                    message += (
                        f" (and {len(missing) - MAX_MISSING_SEGMENTS_TO_DISPLAY} more)"
                    )

        super().__init__(message)


# Maximum number of subtitle segments to process in a single batch
# This limit helps prevent API timeouts and memory issues with large subtitle files
DEFAULT_MAX_SEGMENTS_PER_CHUNK = 50


@dataclass
class SubtitleSegment:
    """Represents a single subtitle segment with timing and text."""

    index: int
    start_time: str
    end_time: str
    text: str

    def __str__(self) -> str:
        """Format segment as SRT entry."""
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}\n"


class SRTParser:
    """Parser for SRT subtitle files."""

    # SRT timestamp format: HH:MM:SS,mmm
    TIMESTAMP_PATTERN = re.compile(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    )

    @staticmethod
    def parse(content: str) -> List[SubtitleSegment]:
        """
        Parse SRT content into subtitle segments.

        Args:
            content: Raw SRT file content

        Returns:
            List of SubtitleSegment objects
        """
        # Remove BOM (Byte Order Mark) if present (common in UTF-8 files)
        if content.startswith("\ufeff"):
            content = content[1:]

        segments = []
        lines = content.strip().split("\n")

        i = 0
        while i < len(lines):
            # Skip empty lines
            if not lines[i].strip():
                i += 1
                continue

            try:
                # Parse index
                index = int(lines[i].strip())
                i += 1

                if i >= len(lines):
                    break

                # Parse timestamps
                timestamp_match = SRTParser.TIMESTAMP_PATTERN.match(lines[i])
                if not timestamp_match:
                    logger.warning(f"Invalid timestamp format at line {i}: {lines[i]}")
                    i += 1
                    continue

                start_time = (
                    f"{timestamp_match.group(1)}:{timestamp_match.group(2)}:"
                    f"{timestamp_match.group(3)},{timestamp_match.group(4)}"
                )
                end_time = (
                    f"{timestamp_match.group(5)}:{timestamp_match.group(6)}:"
                    f"{timestamp_match.group(7)},{timestamp_match.group(8)}"
                )
                i += 1

                # Parse text (may be multiple lines)
                text_lines = []
                while i < len(lines) and lines[i].strip():
                    text_lines.append(lines[i].strip())
                    i += 1

                if text_lines:
                    text = "\n".join(text_lines)
                    segments.append(
                        SubtitleSegment(
                            index=index,
                            start_time=start_time,
                            end_time=end_time,
                            text=text,
                        )
                    )

            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing segment at line {i}: {e}")
                i += 1
                continue

        logger.info(f"Parsed {len(segments)} subtitle segments")
        return segments

    @staticmethod
    def format(segments: List[SubtitleSegment]) -> str:
        """
        Format subtitle segments back to SRT format with proper spacing.

        Ensures:
        - One blank line between subtitle entries
        - No trailing blank lines at end of file
        - Proper newline handling

        Args:
            segments: List of SubtitleSegment objects

        Returns:
            Formatted SRT content string
        """
        if not segments:
            return ""

        # Join segments with double newline for proper spacing
        # Each segment's __str__ ends with a newline, so joining with \n\n
        # gives us: segment1\n\nsegment2\n\nsegment3
        formatted = "\n\n".join(str(segment).rstrip() for segment in segments)

        # Add final newline (but not double newline)
        return formatted + "\n"


def extract_text_for_translation(segments: List[SubtitleSegment]) -> List[str]:
    """
    Extract text from segments for batch translation.

    Args:
        segments: List of subtitle segments

    Returns:
        List of text strings to translate

    Raises:
        ValueError: If segments list is None
    """
    if segments is None:
        raise ValueError("Segments list cannot be None")

    return [segment.text for segment in segments]


def _format_chunk_info(
    chunk_index: Optional[int] = None, total_chunks: Optional[int] = None
) -> str:
    """
    Format chunk information for logging messages.

    Args:
        chunk_index: Optional chunk index (0-based)
        total_chunks: Optional total number of chunks

    Returns:
        Formatted string like " Chunk 2/5" or empty string if info not provided
    """
    if chunk_index is not None and total_chunks is not None:
        return f" Chunk {chunk_index + 1}/{total_chunks}"
    return ""


def _calculate_missing_segment_numbers(
    segment_count: int, parsed_segment_numbers: List[int]
) -> Set[int]:
    """
    Calculate which segment numbers are missing from parsed results.

    Args:
        segment_count: Total number of segments expected (1-based count)
        parsed_segment_numbers: List of successfully parsed segment numbers (1-based)

    Returns:
        Set of missing segment numbers (1-based)
    """
    expected_numbers = set(range(1, segment_count + 1))
    parsed_numbers_set = set(parsed_segment_numbers)
    return expected_numbers - parsed_numbers_set


def _identify_missing_segment_index(
    segment_count: int, parsed_segment_numbers: Optional[List[int]] = None
) -> int:
    """
    Identify the 0-based index of the missing segment.

    Args:
        segment_count: Total number of segments (1-based count)
        parsed_segment_numbers: List of successfully parsed segment numbers (1-based)

    Returns:
        0-based index of the missing segment.
        If parsed_segment_numbers is not provided or invalid, returns last segment index.
    """
    if not parsed_segment_numbers:
        # Fallback: assume last segment is missing
        return segment_count - 1

    missing_numbers = _calculate_missing_segment_numbers(
        segment_count, parsed_segment_numbers
    )

    if missing_numbers:
        missing_number = missing_numbers.pop()

        # Validate missing_number is within valid range
        if missing_number < 1 or missing_number > segment_count:
            logger.warning(
                f"Invalid missing segment number {missing_number} "
                f"(expected 1-{segment_count}), falling back to last segment"
            )
            return segment_count - 1

        # Convert 1-based segment number to 0-based index
        return missing_number - 1

    # Fallback: if no missing numbers found, assume last segment
    return segment_count - 1


def _create_translation_map(
    translations: List[str], parsed_segment_numbers: Optional[List[int]] = None
) -> Dict[int, str]:
    """
    Create a mapping from segment number (1-based) to translation text.

    Args:
        translations: List of translated text strings
        parsed_segment_numbers: Optional list of segment numbers corresponding to translations

    Returns:
        Dictionary mapping segment number (1-based) to translation text
    """
    translation_map: Dict[int, str] = {}

    if parsed_segment_numbers:
        # Validate lengths match
        if len(parsed_segment_numbers) != len(translations):
            logger.warning(
                f"Mismatch: {len(parsed_segment_numbers)} parsed segment numbers "
                f"but {len(translations)} translations. Using fallback sequential mapping."
            )
            # Fall back to sequential mapping
            for i, translation in enumerate(translations):
                translation_map[i + 1] = translation.strip()
        else:
            # Map parsed segment numbers to their translations
            for seg_num, translation in zip(parsed_segment_numbers, translations):
                translation_map[seg_num] = translation.strip()
    else:
        # Fallback: assume translations are in sequential order (for segments 1, 2, 3, ...)
        for i, translation in enumerate(translations):
            translation_map[i + 1] = translation.strip()

    return translation_map


def _build_translated_segments_with_missing(
    segments: List[SubtitleSegment],
    translation_map: Dict[int, str],
    missing_index: int,
) -> List[SubtitleSegment]:
    """
    Build translated segments using translation map, with original text for missing segment.

    Args:
        segments: Original subtitle segments
        translation_map: Mapping from segment number (1-based) to translation text
        missing_index: 0-based index of the segment that's missing a translation

    Returns:
        List of SubtitleSegment with translations applied
    """
    translated_segments = []

    for i, segment in enumerate(segments):
        segment_number = segment.index  # Segment numbers are 1-based

        if i == missing_index:
            # Use original text for the missing translation
            logger.info(
                f"Using original text for segment {segment_number} "
                f"(translation missing)"
            )
            translated_segments.append(
                SubtitleSegment(
                    index=segment.index,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    text=segment.text,  # Keep original text
                )
            )
        else:
            # Use translated text from the map
            translated_text = translation_map.get(segment_number)
            if translated_text is None:
                # Fallback: if mapping fails, use original text
                logger.warning(
                    f"Could not find translation for segment {segment_number}, "
                    f"using original text"
                )
                translated_text = segment.text

            translated_segments.append(
                SubtitleSegment(
                    index=segment.index,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    text=translated_text,
                )
            )

    return translated_segments


def _merge_translations_with_one_missing(
    segments: List[SubtitleSegment],
    translations: List[str],
    chunk_index: Optional[int] = None,
    total_chunks: Optional[int] = None,
    parsed_segment_numbers: Optional[List[int]] = None,
) -> List[SubtitleSegment]:
    """
    Handle merging when exactly 1 translation is missing.

    This is a tolerance for minor parsing issues. The missing segment will use its original text.

    Args:
        segments: Original subtitle segments
        translations: Translated text strings (count is 1 less than segments)
        chunk_index: Optional chunk index for better error messages
        total_chunks: Optional total chunks count for better error messages
        parsed_segment_numbers: Optional list of parsed segment numbers for accurate identification

    Returns:
        List of translated segments with original text for the missing segment
    """
    segment_count = len(segments)
    translation_count = len(translations)
    chunk_info = _format_chunk_info(chunk_index, total_chunks)

    # Identify which segment is actually missing
    missing_index = _identify_missing_segment_index(
        segment_count, parsed_segment_numbers
    )

    # Log appropriate warning message
    if parsed_segment_numbers:
        missing_numbers = _calculate_missing_segment_numbers(
            segment_count, parsed_segment_numbers
        )
        if missing_numbers:
            missing_number = list(missing_numbers)[0]
            logger.warning(
                f"⚠️  Translation count mismatch: expected {segment_count} translations, "
                f"but got {translation_count} (missing 1). "
                f"Using original text for segment {missing_number} (index {missing_index + 1}).{chunk_info}"
            )
        else:
            # Shouldn't happen, but handle gracefully
            logger.warning(
                f"⚠️  Translation count mismatch: expected {segment_count} translations, "
                f"but got {translation_count} (missing 1). "
                f"Using original text for last segment (segment {segments[missing_index].index}).{chunk_info}"
            )
    else:
        logger.warning(
            f"⚠️  Translation count mismatch: expected {segment_count} translations, "
            f"but got {translation_count} (missing 1). "
            f"Using original text for last segment (segment {segments[missing_index].index}).{chunk_info}"
        )

    # Create translation map and build segments
    translation_map = _create_translation_map(translations, parsed_segment_numbers)
    return _build_translated_segments_with_missing(
        segments, translation_map, missing_index
    )


def merge_translations(
    segments: List[SubtitleSegment],
    translations: List[str],
    chunk_index: Optional[int] = None,
    total_chunks: Optional[int] = None,
    parsed_segment_numbers: Optional[List[int]] = None,
) -> List[SubtitleSegment]:
    """
    Merge translated text back into subtitle segments.

    Args:
        segments: Original subtitle segments
        translations: Translated text strings
        chunk_index: Optional chunk index for better error messages
        total_chunks: Optional total chunks count for better error messages
        parsed_segment_numbers: Optional list of segment numbers that were successfully parsed.
            When provided and there's exactly 1 missing translation, this is used to identify
            which segment is actually missing (instead of assuming it's the last one).

    Returns:
        New list of segments with translated text

    Raises:
        TranslationCountMismatchError: If segment and translation counts don't match
        ValueError: If inputs are None
    """
    if segments is None or translations is None:
        raise ValueError("Segments and translations cannot be None")

    segment_count = len(segments)
    translation_count = len(translations)
    missing_count = segment_count - translation_count

    # Allow 1 missing translation as tolerance for minor parsing issues
    if missing_count == 1:
        return _merge_translations_with_one_missing(
            segments, translations, chunk_index, total_chunks, parsed_segment_numbers
        )

    # For mismatches other than exactly 1 missing, raise error
    if segment_count != translation_count:
        raise TranslationCountMismatchError(
            expected_count=segment_count,
            actual_count=translation_count,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
        )

    # Normal case: counts match exactly
    translated_segments = []
    for segment, translation in zip(segments, translations):
        translated_segments.append(
            SubtitleSegment(
                index=segment.index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=translation.strip(),
            )
        )

    return translated_segments


def merge_translated_chunks(
    translated_segments: List[SubtitleSegment],
) -> List[SubtitleSegment]:
    """
    Merge translated segments from multiple chunks into a single list.

    Ensures:
    - Segments are sorted by original index (chronological order)
    - Sequential numbering starting from 1
    - All timestamps and text preserved

    Args:
        translated_segments: List of translated SubtitleSegment objects

    Returns:
        List of SubtitleSegment objects with sequential numbering

    Raises:
        ValueError: If translated_segments is None
    """
    if translated_segments is None:
        raise ValueError("Translated segments list cannot be None")

    if not translated_segments:
        return []

    # Sort segments by original index to ensure chronological order
    sorted_segments = sorted(translated_segments, key=lambda seg: seg.index)

    # Renumber segments sequentially starting from 1
    merged_segments = []
    for new_index, segment in enumerate(sorted_segments, start=1):
        merged_segments.append(
            SubtitleSegment(
                index=new_index,
                start_time=segment.start_time,
                end_time=segment.end_time,
                text=segment.text,
            )
        )

    return merged_segments


def chunk_segments(
    segments: List[SubtitleSegment], max_segments: int = DEFAULT_MAX_SEGMENTS_PER_CHUNK
) -> List[List[SubtitleSegment]]:
    """
    Split segments into chunks for batch processing.

    Args:
        segments: List of all subtitle segments
        max_segments: Maximum segments per chunk (must be positive)

    Returns:
        List of segment chunks

    Raises:
        ValueError: If max_segments is less than 1 or segments is None
    """
    if segments is None:
        raise ValueError("Segments list cannot be None")

    if max_segments < 1:
        raise ValueError(f"max_segments must be at least 1, got {max_segments}")

    if not segments:
        return []

    chunks = []
    for i in range(0, len(segments), max_segments):
        chunks.append(segments[i : i + max_segments])

    logger.info(f"Split {len(segments)} segments into {len(chunks)} chunks")
    return chunks


def split_subtitle_content(
    segments: List[SubtitleSegment],
    max_tokens: int,
    model: str = "gpt-4",
    safety_margin: float = 0.8,
    max_segments_per_chunk: int = 200,
) -> List[List[SubtitleSegment]]:
    """
    Split subtitle segments into token-safe chunks.

    This function splits segments based on token count rather than segment count,
    ensuring that translation requests stay within model token limits. Individual
    subtitle segments are never split across chunks.

    Args:
        segments: List of subtitle segments to split
        max_tokens: Maximum tokens per chunk
        model: Model name for token counting (default: 'gpt-4')
        safety_margin: Safety margin as fraction of max_tokens (default: 0.8)
                      Example: 0.8 means use 80% of token limit
        max_segments_per_chunk: Maximum number of segments per chunk (default: 200)
                               This prevents API timeouts with very large chunks

    Returns:
        List of segment chunks, each respecting token limits

    Raises:
        ValueError: If segments is None, max_tokens <= 0, or safety_margin invalid
    """
    from common.token_counter import count_tokens

    # Validate inputs
    if segments is None:
        raise ValueError("Segments list cannot be None")

    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be positive, got {max_tokens}")

    if not (0.0 < safety_margin <= 1.0):
        raise ValueError(
            f"safety_margin must be between 0.0 and 1.0, got {safety_margin}"
        )

    if not segments:
        return []

    # Calculate effective token limit with safety margin
    effective_limit = int(max_tokens * safety_margin)

    chunks = []
    current_chunk = []
    current_token_count = 0

    for segment in segments:
        # Count tokens for this segment
        segment_tokens = count_tokens(segment.text, model)

        # Check if adding this segment would exceed limit
        would_exceed_token_limit = (
            current_token_count + segment_tokens > effective_limit
            and len(current_chunk) > 0
        )

        # Also check segment count limit to prevent API timeouts
        would_exceed_segment_limit = len(current_chunk) >= max_segments_per_chunk

        if would_exceed_token_limit or would_exceed_segment_limit:
            # Start new chunk
            chunks.append(current_chunk)
            logger.debug(
                f"Created chunk with {len(current_chunk)} segments, "
                f"~{current_token_count} tokens"
            )
            if would_exceed_segment_limit:
                logger.info(
                    f"Chunk reached max_segments_per_chunk limit ({max_segments_per_chunk}), "
                    f"starting new chunk"
                )
            current_chunk = [segment]
            current_token_count = segment_tokens
        else:
            # Add to current chunk
            current_chunk.append(segment)
            current_token_count += segment_tokens

        # Warn if single segment exceeds limit
        if segment_tokens > effective_limit:
            logger.warning(
                f"Segment {segment.index} has {segment_tokens} tokens, "
                f"exceeds limit of {effective_limit}. Including anyway."
            )

    # Add final chunk
    if current_chunk:
        chunks.append(current_chunk)
        logger.debug(
            f"Created final chunk with {len(current_chunk)} segments, "
            f"~{current_token_count} tokens"
        )

    logger.info(
        f"Split {len(segments)} segments into {len(chunks)} token-aware chunks "
        f"(limit: {effective_limit} tokens)"
    )

    return chunks
