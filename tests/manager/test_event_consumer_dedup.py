"""Tests for duplicate prevention in manager event consumer."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from common.duplicate_prevention import DuplicateCheckResult
from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils
from manager.event_consumer import SubtitleEventConsumer


@pytest.fixture
def event_consumer():
    """Create SubtitleEventConsumer instance."""
    return SubtitleEventConsumer()


@pytest.fixture
def mock_duplicate_prevention():
    """Create mock duplicate prevention service."""
    with patch("manager.event_consumer.duplicate_prevention") as mock:
        yield mock


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    with patch("manager.event_consumer.orchestrator") as mock:
        yield mock


@pytest.fixture
def mock_redis_client():
    """Create mock redis client."""
    with patch("manager.event_consumer.redis_client") as mock:
        yield mock


@pytest.mark.asyncio
class TestEventConsumerDuplicatePrevention:
    """Test suite for duplicate prevention in event consumer."""

    @pytest.mark.parametrize(
        "video_url,video_title,language,target_language,description",
        [
            ("/media/movie.mp4", "Movie", "en", "es", "basic movie"),
            (
                "/media/show/episode.mkv",
                "Episode",
                "en",
                None,
                "episode no translation",
            ),
            ("/media/film.avi", "Film", "fr", "en", "french to english"),
        ],
    )
    async def test_process_subtitle_request_first_request(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
        video_url,
        video_title,
        language,
        target_language,
        description,
    ):
        """Test that first subtitle request is processed normally."""
        job_id = uuid4()

        # Mock duplicate prevention to indicate not a duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        )

        # Mock orchestrator to succeed
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

        # Create event
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": video_title,
                "language": language,
                "target_language": target_language,
                "preferred_sources": ["opensubtitles"],
            },
        )

        # Process event
        await event_consumer._process_subtitle_request(event)

        # Verify duplicate check was called
        mock_duplicate_prevention.check_and_register.assert_called_once()

        # Verify download task was enqueued
        mock_orchestrator.enqueue_download_task.assert_called_once()

    @pytest.mark.parametrize(
        "video_url,language,existing_job_id,description",
        [
            ("/media/movie.mp4", "en", uuid4(), "duplicate movie"),
            ("/media/show.mkv", "es", uuid4(), "duplicate show spanish"),
            ("/media/film.avi", "fr", uuid4(), "duplicate film french"),
        ],
    )
    async def test_process_subtitle_request_duplicate_request(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
        video_url,
        language,
        existing_job_id,
        description,
    ):
        """Test that duplicate subtitle request is detected and skips enqueue."""
        job_id = uuid4()

        # Mock duplicate prevention to indicate duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=True,
                existing_job_id=existing_job_id,
                message=f"Already being processed as job {existing_job_id}",
            )
        )

        # Mock orchestrator - should NOT be called
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

        # Create event
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": "Test Video",
                "language": language,
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        # Process event
        await event_consumer._process_subtitle_request(event)

        # Verify duplicate check was called
        mock_duplicate_prevention.check_and_register.assert_called_once()

        # Verify download task was NOT enqueued (duplicate detected)
        mock_orchestrator.enqueue_download_task.assert_not_called()

    async def test_process_subtitle_request_different_languages_allowed(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
    ):
        """Test that same video with different languages creates separate jobs."""
        video_url = "/media/movie.mp4"
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # Mock to return not duplicate for both
        mock_duplicate_prevention.check_and_register = AsyncMock(
            side_effect=[
                DuplicateCheckResult(
                    is_duplicate=False,
                    existing_job_id=None,
                    message="Request registered",
                ),
                DuplicateCheckResult(
                    is_duplicate=False,
                    existing_job_id=None,
                    message="Request registered",
                ),
            ]
        )

        # Mock orchestrator
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

        # Create events for different languages
        event_en = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id_1,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": "Movie",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        event_es = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id_2,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": "Movie",
                "language": "es",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        # Process both events
        await event_consumer._process_subtitle_request(event_en)
        await event_consumer._process_subtitle_request(event_es)

        # Both should have been processed
        assert mock_duplicate_prevention.check_and_register.call_count == 2
        assert mock_orchestrator.enqueue_download_task.call_count == 2

    async def test_process_subtitle_request_duplicate_prevention_disabled(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
    ):
        """Test processing when duplicate prevention is disabled."""
        video_url = "/media/movie.mp4"
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # Mock as disabled
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Duplicate prevention disabled",
            )
        )

        # Mock orchestrator
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

        # Create identical events
        event1 = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id_1,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": "Movie",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        event2 = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id_2,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": "Movie",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        # Process both
        await event_consumer._process_subtitle_request(event1)
        await event_consumer._process_subtitle_request(event2)

        # Both should have been processed
        assert mock_duplicate_prevention.check_and_register.call_count == 2
        assert mock_orchestrator.enqueue_download_task.call_count == 2

    async def test_process_subtitle_request_redis_unavailable_graceful_degradation(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
    ):
        """Test graceful degradation when Redis is unavailable."""
        job_id = uuid4()

        # Mock Redis unavailable scenario
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Redis unavailable - duplicate prevention bypassed",
            )
        )

        # Mock orchestrator
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

        # Create event
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": "/media/movie.mp4",
                "video_title": "Movie",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        # Should allow request through despite Redis being unavailable
        await event_consumer._process_subtitle_request(event)

        # Verify duplicate check was attempted
        mock_duplicate_prevention.check_and_register.assert_called_once()

        # Verify download task was enqueued
        mock_orchestrator.enqueue_download_task.assert_called_once()

    async def test_process_subtitle_request_missing_required_fields(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
    ):
        """Test handling of events with missing required fields."""
        job_id = uuid4()

        # Create event with missing video_url
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": None,  # Missing required field
                "video_title": "Movie",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        with patch("manager.event_consumer.event_publisher") as mock_publisher:
            mock_publisher.publish_event = AsyncMock()

            # Process event - should handle gracefully
            await event_consumer._process_subtitle_request(event)

            # Duplicate check should not be called (validation fails first)
            mock_duplicate_prevention.check_and_register.assert_not_called()

            # Orchestrator should not be called
            mock_orchestrator.enqueue_download_task.assert_not_called()

            # Should publish JOB_FAILED event (event-driven, not direct Redis update)
            mock_publisher.publish_event.assert_called_once()
            event_call = mock_publisher.publish_event.call_args[0][0]
            assert event_call.event_type == EventType.JOB_FAILED
            assert event_call.job_id == job_id
            assert "error_message" in event_call.payload
            assert "Missing required fields" in event_call.payload["error_message"]

    async def test_process_subtitle_request_enqueue_failure_with_duplicate(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
    ):
        """Test that enqueue failure is handled properly even with duplicate detection."""
        job_id = uuid4()
        existing_job_id = uuid4()

        # Mock as duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=True,
                existing_job_id=existing_job_id,
                message=f"Already being processed as job {existing_job_id}",
            )
        )

        # Mock orchestrator to fail (but shouldn't be called)
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=False)

        # Mock Redis client
        mock_redis_client.update_phase = AsyncMock()

        # Create event
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": "/media/movie.mp4",
                "video_title": "Movie",
                "language": "en",
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        # Process event
        await event_consumer._process_subtitle_request(event)

        # Verify duplicate check was called
        mock_duplicate_prevention.check_and_register.assert_called_once()

        # Enqueue should NOT be called (duplicate detected)
        mock_orchestrator.enqueue_download_task.assert_not_called()

        # Redis update should NOT be called (no failure occurred)
        mock_redis_client.update_phase.assert_not_called()

    @pytest.mark.parametrize(
        "num_events,expected_duplicates",
        [
            (2, 1),  # 1 original + 1 duplicate
            (3, 2),  # 1 original + 2 duplicates
            (5, 4),  # 1 original + 4 duplicates
        ],
    )
    async def test_process_subtitle_request_concurrent_duplicates(
        self,
        event_consumer,
        mock_duplicate_prevention,
        mock_orchestrator,
        mock_redis_client,
        num_events,
        expected_duplicates,
    ):
        """Test handling of concurrent duplicate events."""
        video_url = "/media/movie.mp4"
        original_job_id = uuid4()

        # First event succeeds, rest are duplicates
        mock_results = [
            DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        ] + [
            DuplicateCheckResult(
                is_duplicate=True,
                existing_job_id=original_job_id,
                message=f"Already being processed as job {original_job_id}",
            )
            for _ in range(expected_duplicates)
        ]

        mock_duplicate_prevention.check_and_register = AsyncMock(
            side_effect=mock_results
        )

        # Mock orchestrator
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=True)

        # Create events
        events = []
        for i in range(num_events):
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_REQUESTED,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="scanner",
                payload={
                    "video_url": video_url,
                    "video_title": "Movie",
                    "language": "en",
                    "target_language": None,
                    "preferred_sources": ["opensubtitles"],
                },
            )
            events.append(event)

        # Process all events
        for event in events:
            await event_consumer._process_subtitle_request(event)

        # Verify duplicate check was called for all
        assert mock_duplicate_prevention.check_and_register.call_count == num_events

        # Only one should have been enqueued
        assert mock_orchestrator.enqueue_download_task.call_count == 1
