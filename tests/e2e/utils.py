"""Utility functions for e2e tests."""

import asyncio
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

import httpx

from common.schemas import SubtitleStatus
from common.utils import PathUtils


def create_test_media_file(
    media_dir: Path, filename: str, size_bytes: int = 1024 * 1024
) -> Path:
    """
    Create a dummy video file for testing.

    Args:
        media_dir: Directory where the file should be created
        filename: Name of the file (should have video extension like .mp4, .mkv)
        size_bytes: Size of the file in bytes (default: 1MB)

    Returns:
        Path to the created file

    Example:
        >>> file_path = create_test_media_file(Path("/media"), "test_movie.mp4")
        >>> file_path.exists()
        True
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    file_path = media_dir / filename

    # Create a dummy file with random data
    with open(file_path, "wb") as f:
        f.write(b"\x00" * size_bytes)

    return file_path


def cleanup_test_media(media_dir: Path, pattern: str = "*") -> None:
    """
    Remove test media files matching a pattern.

    Args:
        media_dir: Directory to clean
        pattern: Glob pattern for files to remove (default: "*")

    Example:
        >>> cleanup_test_media(Path("/media"), "test_*.mp4")
    """
    if not media_dir.exists():
        return

    for file in media_dir.glob(pattern):
        try:
            if file.is_file():
                file.unlink()
        except Exception:
            pass  # Ignore errors during cleanup


async def wait_for_job_status(
    http_client: httpx.AsyncClient,
    job_id: UUID,
    target_status: SubtitleStatus,
    max_wait_seconds: int = 300,
    poll_interval: float = 2.0,
) -> Optional[dict]:
    """
    Poll job status until it reaches target status or timeout.

    Args:
        http_client: HTTP client for API requests
        job_id: Job ID to check
        target_status: Target status to wait for
        max_wait_seconds: Maximum time to wait in seconds (default: 300)
        poll_interval: Time between polls in seconds (default: 2.0)

    Returns:
        Job status response dict if target status reached, None if timeout

    Example:
        >>> status = await wait_for_job_status(client, job_id, SubtitleStatus.DONE)
        >>> assert status["status"] == "done"
    """
    start_time = time.time()
    last_status = None
    last_print_time = 0

    while time.time() - start_time < max_wait_seconds:
        try:
            response = await http_client.get(f"/subtitles/status/{job_id}")
            if response.status_code == 200:
                data = response.json()
                current_status = data.get("status")

                # Print status changes
                if current_status != last_status:
                    elapsed = int(time.time() - start_time)
                    print(f"  ⏱️  [{elapsed}s] Job status: {current_status}")
                    last_status = current_status
                elif time.time() - last_print_time > 10:  # Print every 10 seconds
                    elapsed = int(time.time() - start_time)
                    print(
                        f"  ⏱️  [{elapsed}s] Still waiting... (current: {current_status}, target: {target_status.value})"
                    )
                    last_print_time = time.time()

                if current_status == target_status.value:
                    return data

                # Check if job failed
                if current_status == SubtitleStatus.FAILED.value:
                    # Get full job details to see error message
                    full_response = await http_client.get(f"/subtitles/{job_id}")
                    if full_response.status_code == 200:
                        full_data = full_response.json()
                        error_msg = full_data.get("error_message", "Unknown error")
                        raise AssertionError(
                            f"Job {job_id} failed with status {current_status}: {error_msg}"
                        )
                    raise AssertionError(
                        f"Job {job_id} failed with status {current_status}"
                    )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Job not found yet, keep waiting
                pass
            else:
                raise

        await asyncio.sleep(poll_interval)

    raise TimeoutError(
        f"Job {job_id} did not reach status {target_status.value} within {max_wait_seconds} seconds"
    )


async def wait_for_file_exists(
    file_path: Path, max_wait_seconds: int = 60, poll_interval: float = 1.0
) -> bool:
    """
    Wait for a file to exist.

    Args:
        file_path: Path to the file
        max_wait_seconds: Maximum time to wait in seconds (default: 60)
        poll_interval: Time between polls in seconds (default: 1.0)

    Returns:
        True if file exists, False if timeout

    Example:
        >>> exists = await wait_for_file_exists(Path("/media/movie.en.srt"))
        >>> assert exists
    """
    start_time = time.time()

    while time.time() - start_time < max_wait_seconds:
        if file_path.exists() and file_path.is_file():
            return True
        await asyncio.sleep(poll_interval)

    return False


def verify_subtitle_file(file_path: Path) -> bool:
    """
    Verify that a subtitle file is valid SRT format.

    Args:
        file_path: Path to the subtitle file

    Returns:
        True if file appears to be valid SRT, False otherwise

    Example:
        >>> is_valid = verify_subtitle_file(Path("/media/movie.en.srt"))
        >>> assert is_valid
    """
    if not file_path.exists() or not file_path.is_file():
        return False

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Basic SRT validation: should contain subtitle blocks
        # Each block typically has: sequence number, timestamp, text
        lines = content.strip().split("\n")

        if len(lines) < 3:
            return False  # Too short to be valid SRT

        # Check for at least one sequence number (should be "1" or similar)
        has_sequence = any(line.strip().isdigit() for line in lines[:10])

        # Check for timestamp pattern (HH:MM:SS,mmm --> HH:MM:SS,mmm)
        has_timestamp = any("-->" in line for line in lines)

        return has_sequence and has_timestamp

    except Exception:
        return False


def get_expected_subtitle_path(video_path: str, language: str) -> Optional[Path]:
    """
    Get the expected subtitle file path for a video file.

    Args:
        video_path: Path to the video file
        language: Language code (e.g., 'en', 'es')

    Returns:
        Expected subtitle file path, or None if video path is invalid

    Example:
        >>> path = get_expected_subtitle_path("/media/movie.mp4", "en")
        >>> assert path == Path("/media/movie.en.srt")
    """
    return PathUtils.generate_subtitle_path_from_video(video_path, language)


async def get_job_details(
    http_client: httpx.AsyncClient, job_id: UUID
) -> Optional[dict]:
    """
    Get full job details from API.

    Args:
        http_client: HTTP client for API requests
        job_id: Job ID to retrieve

    Returns:
        Job details dict, or None if not found

    Example:
        >>> job = await get_job_details(client, job_id)
        >>> assert job["status"] == "done"
    """
    try:
        response = await http_client.get(f"/subtitles/{job_id}")
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


async def get_job_events(
    http_client: httpx.AsyncClient, job_id: UUID
) -> Optional[list]:
    """
    Get event history for a job.

    Args:
        http_client: HTTP client for API requests
        job_id: Job ID to retrieve events for

    Returns:
        List of events, or None if not found

    Example:
        >>> events = await get_job_events(client, job_id)
        >>> assert len(events) > 0
    """
    try:
        response = await http_client.get(f"/subtitles/{job_id}/events")
        if response.status_code == 200:
            data = response.json()
            return data.get("events", [])
        return None
    except Exception:
        return None
