"""File storage service for subtitle files."""

import logging
from pathlib import Path
from uuid import UUID

from common.config import settings

logger = logging.getLogger(__name__)


def ensure_storage_directory() -> None:
    """
    Ensure the subtitle storage directory exists.

    Creates the directory and any necessary parent directories if they don't exist.
    This function is idempotent and safe to call multiple times.
    """
    storage_path = Path(settings.subtitle_storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured storage directory exists: {storage_path}")


def get_subtitle_file_path(job_id: UUID, language: str) -> Path:
    """
    Generate the file path for a subtitle file.

    Args:
        job_id: Unique identifier for the job
        language: Language code (e.g., 'en', 'es')

    Returns:
        Path object representing the subtitle file location

    Example:
        >>> job_id = UUID('123e4567-e89b-12d3-a456-426614174000')
        >>> get_subtitle_file_path(job_id, 'en')
        Path('.../storage/subtitles/123e4567-e89b-12d3-a456-426614174000.en.srt')
    """
    storage_path = Path(settings.subtitle_storage_path)
    filename = f"{job_id}.{language}.srt"
    file_path = storage_path / filename
    return file_path


def save_subtitle_file(job_id: UUID, content: str, language: str) -> str:
    """
    Save subtitle content to a file.

    Creates the storage directory if it doesn't exist, then writes the content
    to a file named {job_id}.{language}.srt.

    Args:
        job_id: Unique identifier for the job
        content: Subtitle file content to save
        language: Language code (e.g., 'en', 'es')

    Returns:
        String path to the saved file

    Example:
        >>> job_id = uuid4()
        >>> content = "1\\n00:00:01,000 --> 00:00:04,000\\nHello world\\n"
        >>> save_subtitle_file(job_id, content, 'en')
        '/path/to/storage/subtitles/abc-123.en.srt'
    """
    ensure_storage_directory()

    file_path = get_subtitle_file_path(job_id, language)

    file_path.write_text(content, encoding="utf-8")

    logger.info(f"Saved subtitle file: {file_path}")
    return str(file_path)


def read_subtitle_file(job_id: UUID, language: str) -> str:
    """
    Read subtitle content from storage.

    Args:
        job_id: Unique identifier for the job
        language: Language code (e.g., 'en', 'es')

    Returns:
        Subtitle file content as string

    Raises:
        FileNotFoundError: If the subtitle file doesn't exist for the given job_id and language
        IOError: If the file exists but cannot be read

    Example:
        >>> job_id = UUID('123e4567-e89b-12d3-a456-426614174000')
        >>> content = read_subtitle_file(job_id, 'en')
        '1\\n00:00:01,000 --> 00:00:04,000\\nHello world\\n'
    """
    file_path = get_subtitle_file_path(job_id, language)

    if not file_path.exists():
        error_message = (
            f"Subtitle file not found for job {job_id} with language '{language}'. "
            f"Expected path: {file_path}. "
            f"The file may not have been downloaded yet, or the job may have failed."
        )
        logger.error(error_message)
        raise FileNotFoundError(error_message)

    try:
        content = file_path.read_text(encoding="utf-8")
        logger.debug(
            f"Successfully read subtitle file: {file_path} ({len(content)} bytes)"
        )
        return content
    except Exception as e:
        error_message = (
            f"Failed to read subtitle file for job {job_id} with language '{language}'. "
            f"Path: {file_path}. Error: {e}"
        )
        logger.error(error_message, exc_info=True)
        raise IOError(error_message) from e
