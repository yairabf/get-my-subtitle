"""SRT subtitle parser and formatter for translation workflows."""

import logging
import re
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

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


def merge_translations(
    segments: List[SubtitleSegment], translations: List[str]
) -> List[SubtitleSegment]:
    """
    Merge translated text back into subtitle segments.

    Args:
        segments: Original subtitle segments
        translations: Translated text strings

    Returns:
        New list of segments with translated text

    Raises:
        ValueError: If segment and translation counts don't match, or if inputs are None
    """
    if segments is None or translations is None:
        raise ValueError("Segments and translations cannot be None")

    if len(segments) != len(translations):
        raise ValueError(
            f"Segment count ({len(segments)}) doesn't match translation count ({len(translations)})"
        )

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
        would_exceed_limit = (
            current_token_count + segment_tokens > effective_limit
            and len(current_chunk) > 0
        )

        if would_exceed_limit:
            # Start new chunk
            chunks.append(current_chunk)
            logger.debug(
                f"Created chunk with {len(current_chunk)} segments, "
                f"~{current_token_count} tokens"
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
