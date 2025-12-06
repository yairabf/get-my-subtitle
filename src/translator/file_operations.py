"""File I/O operations for subtitle files."""

import logging
from pathlib import Path
from typing import List

from common.subtitle_parser import SRTParser, SubtitleSegment

logger = logging.getLogger(__name__)


async def read_and_parse_subtitle_file(
    subtitle_file_path: str,
) -> List[SubtitleSegment]:
    """
    Read and parse subtitle file from disk.

    Args:
        subtitle_file_path: Path to subtitle file

    Returns:
        List of SubtitleSegment objects

    Raises:
        FileNotFoundError: If subtitle file doesn't exist
        ValueError: If file contains no subtitle segments
    """
    logger.info(f"Reading subtitle file: {subtitle_file_path}")

    subtitle_path = Path(subtitle_file_path)
    if not subtitle_path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_file_path}")

    srt_content = subtitle_path.read_text(encoding="utf-8")
    logger.info(f"Read {len(srt_content)} characters from subtitle file")

    # Parse SRT content
    logger.info("Parsing SRT content...")
    segments = SRTParser.parse(srt_content)

    if not segments:
        raise ValueError("No subtitle segments found in file")

    logger.info(f"Parsed {len(segments)} subtitle segments")
    return segments


async def save_translated_file(
    translated_segments: List[SubtitleSegment],
    subtitle_file_path: str,
    target_language: str,
) -> Path:
    """
    Save translated segments to file.

    Args:
        translated_segments: List of translated subtitle segments
        subtitle_file_path: Path to source subtitle file
        target_language: Target language code

    Returns:
        Path to saved translated file
    """
    # Format back to SRT
    translated_srt = SRTParser.format(translated_segments)

    # Save translated file - generate path by replacing language code
    from common.utils import PathUtils

    output_path = PathUtils.generate_subtitle_path_from_source(
        subtitle_file_path, target_language
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write translated content to file
    output_path.write_text(translated_srt, encoding="utf-8")
    logger.info(f"✅ Saved translated subtitle to: {output_path}")
    logger.info(f"   File size: {output_path.stat().st_size} bytes")

    return output_path
