"""SRT subtitle parser and formatter for translation workflows."""

import re
from dataclasses import dataclass
from typing import List
import logging

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

                start_time = f"{timestamp_match.group(1)}:{timestamp_match.group(2)}:{timestamp_match.group(3)},{timestamp_match.group(4)}"
                end_time = f"{timestamp_match.group(5)}:{timestamp_match.group(6)}:{timestamp_match.group(7)},{timestamp_match.group(8)}"
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
        Format subtitle segments back to SRT format.

        Args:
            segments: List of SubtitleSegment objects

        Returns:
            Formatted SRT content
        """
        return "\n".join(str(segment) for segment in segments)


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
