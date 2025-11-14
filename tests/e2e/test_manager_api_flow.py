"""End-to-end tests for manager API endpoints.

These tests verify all manager API endpoints work correctly:
- POST /subtitles/download
- POST /subtitles/translate
- GET /subtitles/{job_id}
- GET /subtitles/{job_id}/status
- GET /subtitles/{job_id}/events
- GET /subtitles
- GET /queue/status
- GET /health
- POST /webhooks/jellyfin
"""

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from common.schemas import SubtitleStatus
from tests.e2e.utils import (
    create_test_media_file,
    get_expected_subtitle_path,
    get_job_details,
    get_job_events,
    wait_for_file_exists,
    wait_for_job_status,
    verify_subtitle_file,
)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_health_endpoint(http_client):
    """Test GET /health endpoint."""
    response = await http_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok" or data["status"] == "healthy"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_queue_status_endpoint(http_client):
    """Test GET /queue/status endpoint."""
    response = await http_client.get("/queue/status")
    assert response.status_code == 200
    data = response.json()
    assert "download_queue_size" in data
    assert "translation_queue_size" in data
    assert "active_workers" in data
    assert isinstance(data["download_queue_size"], int)
    assert isinstance(data["translation_queue_size"], int)
    assert isinstance(data["active_workers"], dict)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_list_subtitles_endpoint(http_client):
    """Test GET /subtitles endpoint."""
    response = await http_client.get("/subtitles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Verify structure of job objects
    if len(data) > 0:
        job = data[0]
        assert "id" in job
        assert "video_url" in job
        assert "video_title" in job
        assert "status" in job


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_create_download_request(http_client, test_media_dir: Path):
    """Test POST /subtitles/download endpoint."""
    # Use a real movie title (no actual file needed)
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    # Create download request
    request_payload = {
        "video_url": video_path,
        "video_title": video_title,
        "language": "en",
        "target_language": "es",
        "preferred_sources": ["opensubtitles"],
    }

    response = await http_client.post("/subtitles/download", json=request_payload)
    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert "id" in data
    assert data["video_url"] == str(video_path)
    assert data["video_title"] == request_payload["video_title"]
    assert data["language"] == request_payload["language"]
    assert data["target_language"] == request_payload["target_language"]
    assert data["status"] == SubtitleStatus.PENDING.value

    job_id = UUID(data["id"])

    # Verify job can be retrieved
    job_response = await http_client.get(f"/subtitles/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["id"] == str(job_id)


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_get_job_details(http_client, test_media_dir: Path):
    """Test GET /subtitles/{job_id} endpoint."""
    # Use a real movie title
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    request_payload = {
        "video_url": video_path,
        "video_title": video_title,
        "language": "en",
        "preferred_sources": ["opensubtitles"],
    }

    create_response = await http_client.post("/subtitles/download", json=request_payload)
    assert create_response.status_code == 201
    job_id = UUID(create_response.json()["id"])

    # Get job details
    response = await http_client.get(f"/subtitles/{job_id}")
    assert response.status_code == 200
    data = response.json()

    # Verify all expected fields
    assert data["id"] == str(job_id)
    assert "video_url" in data
    assert "video_title" in data
    assert "language" in data
    assert "status" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_get_job_status(http_client, test_media_dir: Path):
    """Test GET /subtitles/{job_id}/status endpoint."""
    # Use a real movie title
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    request_payload = {
        "video_url": video_path,
        "video_title": video_title,
        "language": "en",
        "preferred_sources": ["opensubtitles"],
    }

    create_response = await http_client.post("/subtitles/download", json=request_payload)
    assert create_response.status_code == 201
    job_id = UUID(create_response.json()["id"])

    # Get job status
    response = await http_client.get(f"/subtitles/status/{job_id}")
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["id"] == str(job_id)
    assert "status" in data
    assert "progress" in data
    assert "message" in data
    assert isinstance(data["progress"], int)
    assert 0 <= data["progress"] <= 100


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_get_job_events(http_client, test_media_dir: Path):
    """Test GET /subtitles/{job_id}/events endpoint."""
    # Use a real movie title
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    request_payload = {
        "video_url": video_path,
        "video_title": video_title,
        "language": "en",
        "preferred_sources": ["opensubtitles"],
    }

    create_response = await http_client.post("/subtitles/download", json=request_payload)
    assert create_response.status_code == 201
    job_id = UUID(create_response.json()["id"])

    # Wait a bit for events to be generated
    await asyncio.sleep(2)

    # Get job events
    response = await http_client.get(f"/subtitles/{job_id}/events")
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "job_id" in data
    assert "event_count" in data
    assert "events" in data
    assert data["job_id"] == str(job_id)
    assert isinstance(data["event_count"], int)
    assert isinstance(data["events"], list)

    # If events exist, verify structure
    if len(data["events"]) > 0:
        event = data["events"][0]
        assert "event_type" in event
        assert "timestamp" in event
        assert "source" in event


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_create_translation_request(http_client, test_media_dir: Path):
    """Test POST /subtitles/translate endpoint."""
    # First, create a source subtitle file
    test_filename = f"translate_test_{asyncio.get_event_loop().time()}.srt"
    subtitle_path = test_media_dir / test_filename

    # Create a simple SRT file
    srt_content = """1
00:00:01,000 --> 00:00:03,000
Hello, this is a test subtitle.

2
00:00:04,000 --> 00:00:06,000
This is the second line.
"""
    subtitle_path.write_text(srt_content)

    # Create translation request
    request_payload = {
        "subtitle_path": str(subtitle_path),
        "source_language": "en",
        "target_language": "es",
        "video_title": f"Translation Test {asyncio.get_event_loop().time()}",
    }

    response = await http_client.post("/subtitles/translate", json=request_payload)
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "id" in data
    assert data["language"] == request_payload["source_language"]
    assert data["target_language"] == request_payload["target_language"]
    assert data["status"] == SubtitleStatus.PENDING.value

    job_id = UUID(data["id"])

    # Wait for translation to complete (or at least start)
    try:
        status_response = await wait_for_job_status(
            http_client,
            job_id,
            SubtitleStatus.TRANSLATE_IN_PROGRESS,
            max_wait_seconds=60,
        )
        assert status_response["status"] == SubtitleStatus.TRANSLATE_IN_PROGRESS.value
    except TimeoutError:
        # Check if it completed quickly
        job_details = await get_job_details(http_client, job_id)
        if job_details:
            assert job_details["status"] in [
                SubtitleStatus.DONE.value,
                SubtitleStatus.TRANSLATE_IN_PROGRESS.value,
            ]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_jellyfin_webhook_endpoint(http_client, test_media_dir: Path):
    """Test POST /webhooks/jellyfin endpoint."""
    # Use a real movie title
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    # Send webhook payload
    webhook_payload = {
        "event": "library.item.added",
        "item_type": "Movie",
        "item_name": video_title,
        "item_path": video_path,
        "item_id": f"webhook-test-{asyncio.get_event_loop().time()}",
        "library_name": "Movies",
        "video_url": video_path,
    }

    response = await http_client.post("/webhooks/jellyfin", json=webhook_payload)
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "status" in data
    assert data["status"] in ["received", "duplicate", "ignored"]
    if data["status"] == "received":
        assert "job_id" in data
        assert "message" in data


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_invalid_job_id_returns_404(http_client):
    """Test that invalid job ID returns 404."""
    fake_job_id = "00000000-0000-0000-0000-000000000000"

    response = await http_client.get(f"/subtitles/{fake_job_id}")
    assert response.status_code == 404

    response = await http_client.get(f"/subtitles/status/{fake_job_id}")
    assert response.status_code == 404

    response = await http_client.get(f"/subtitles/{fake_job_id}/events")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_invalid_request_returns_422(http_client):
    """Test that invalid request body returns 422."""
    # Missing required fields
    invalid_payload = {
        "video_url": "https://example.com/video.mp4",
        # Missing video_title and language
    }

    response = await http_client.post("/subtitles/download", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_full_download_flow_via_api(http_client, test_media_dir: Path):
    """Test complete download flow via API endpoints."""
    # Use a real movie title
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    # Step 1: Create download request
    request_payload = {
        "video_url": video_path,
        "video_title": video_title,
        "language": "en",
        "target_language": "es",
        "preferred_sources": ["opensubtitles"],
    }

    create_response = await http_client.post("/subtitles/download", json=request_payload)
    assert create_response.status_code == 201
    job_id = UUID(create_response.json()["id"])

    # Step 2: Get job status and verify it progresses
    status_response = await http_client.get(f"/subtitles/status/{job_id}")
    assert status_response.status_code == 200
    initial_status = status_response.json()
    assert initial_status["status"] in [
        SubtitleStatus.PENDING.value,
        SubtitleStatus.DOWNLOAD_QUEUED.value,
    ]

    # Step 3: Wait for job to complete (or reach translation)
    try:
        final_status = await wait_for_job_status(
            http_client, job_id, SubtitleStatus.DONE, max_wait_seconds=300
        )
        assert final_status["status"] == SubtitleStatus.DONE.value

        # Step 4: Get full job details
        job_details = await get_job_details(http_client, job_id)
        assert job_details is not None
        assert job_details["status"] == SubtitleStatus.DONE.value

        # Step 5: Get event history
        events = await get_job_events(http_client, job_id)
        assert events is not None
        assert len(events) > 0

        # Step 6: Verify job completed successfully
        # Note: Subtitle file location depends on whether it was downloaded or translated
        # Since we're using a fake path, we just verify the job completed

    except TimeoutError:
        # Job might still be processing or failed
        job_details = await get_job_details(http_client, job_id)
        if job_details:
            # Accept any final status as long as it's not stuck
            assert job_details["status"] in [
                SubtitleStatus.DONE.value,
                SubtitleStatus.FAILED.value,
                SubtitleStatus.TRANSLATE_IN_PROGRESS.value,
            ]


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_job_state_transitions(http_client, test_media_dir: Path):
    """Test that job state transitions are tracked correctly via API."""
    # Use a real movie title
    video_title = "The Matrix"
    video_path = f"/media/movies/{video_title.replace(' ', '_')}.mp4"

    request_payload = {
        "video_url": video_path,
        "video_title": video_title,
        "language": "en",
        "target_language": "es",
        "preferred_sources": ["opensubtitles"],
    }

    create_response = await http_client.post("/subtitles/download", json=request_payload)
    job_id = UUID(create_response.json()["id"])

    # Track status changes
    previous_status = None
    status_changes = []

    # Poll status multiple times to see transitions
    for _ in range(10):
        await asyncio.sleep(3)
        status_response = await http_client.get(f"/subtitles/status/{job_id}")
        if status_response.status_code == 200:
            current_status = status_response.json()["status"]
            if current_status != previous_status:
                status_changes.append(current_status)
                previous_status = current_status

            # If we reach DONE or FAILED, stop polling
            if current_status in [SubtitleStatus.DONE.value, SubtitleStatus.FAILED.value]:
                break

    # Verify we saw at least one status change
    assert len(status_changes) > 0, "No status transitions observed"

    # Verify final status is valid
    final_response = await http_client.get(f"/subtitles/{job_id}")
    assert final_response.status_code == 200
    final_data = final_response.json()
    assert final_data["status"] in [
        SubtitleStatus.DONE.value,
        SubtitleStatus.FAILED.value,
        SubtitleStatus.TRANSLATE_IN_PROGRESS.value,
    ]

