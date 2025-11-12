"""Tests for duplicate prevention in Jellyfin webhook handler."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from common.duplicate_prevention import DuplicateCheckResult
from manager.schemas import JellyfinWebhookPayload
from scanner.webhook_handler import JellyfinWebhookHandler


@pytest.fixture
def webhook_handler():
    """Create JellyfinWebhookHandler instance."""
    return JellyfinWebhookHandler()


@pytest.fixture
def mock_duplicate_prevention():
    """Create mock duplicate prevention service."""
    with patch("scanner.webhook_handler.duplicate_prevention") as mock:
        yield mock


@pytest.mark.asyncio
class TestWebhookHandlerDuplicatePrevention:
    """Test suite for duplicate prevention in webhook handler."""

    @pytest.mark.parametrize(
        "item_name,item_type,event,video_url,description",
        [
            (
                "Movie Title",
                "Movie",
                "library.item.added",
                "/media/movie.mp4",
                "new movie",
            ),
            (
                "Episode S01E01",
                "Episode",
                "library.item.added",
                "/media/show/ep1.mkv",
                "new episode",
            ),
            (
                "Film",
                "Movie",
                "library.item.updated",
                "/media/film.avi",
                "updated movie",
            ),
        ],
    )
    async def test_process_webhook_first_request(
        self,
        webhook_handler,
        mock_duplicate_prevention,
        item_name,
        item_type,
        event,
        video_url,
        description,
    ):
        """Test that first webhook request for an item is processed normally."""
        # Mock duplicate prevention to indicate not a duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        )

        # Create webhook payload
        payload = JellyfinWebhookPayload(
            event=event,
            item_name=item_name,
            item_type=item_type,
            item_path=video_url,
            video_url=video_url,
        )

        # Mock Redis and event publisher
        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ), patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ):
            # Process webhook
            result = await webhook_handler.process_webhook(payload)

            # Verify response
            assert result.status == "received"
            assert result.job_id is not None

            # Verify duplicate check was called
            mock_duplicate_prevention.check_and_register.assert_called_once()

    @pytest.mark.parametrize(
        "item_name,item_type,video_url,existing_job_id,description",
        [
            ("Movie Title", "Movie", "/media/movie.mp4", uuid4(), "duplicate movie"),
            (
                "Episode S01E01",
                "Episode",
                "/media/show/ep1.mkv",
                uuid4(),
                "duplicate episode",
            ),
            ("Film", "Movie", "/media/film.avi", uuid4(), "duplicate film"),
        ],
    )
    async def test_process_webhook_duplicate_request(
        self,
        webhook_handler,
        mock_duplicate_prevention,
        item_name,
        item_type,
        video_url,
        existing_job_id,
        description,
    ):
        """Test that duplicate webhook request is detected and returns existing job_id."""
        # Mock duplicate prevention to indicate duplicate
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=True,
                existing_job_id=existing_job_id,
                message=f"Already being processed as job {existing_job_id}",
            )
        )

        # Create webhook payload
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name=item_name,
            item_type=item_type,
            item_path=video_url,
            video_url=video_url,
        )

        # Mock Redis and event publisher - should NOT be called for duplicates
        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ) as mock_save_job, patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ) as mock_publish:
            # Process webhook
            result = await webhook_handler.process_webhook(payload)

            # Verify response indicates duplicate
            assert result.status == "duplicate"
            assert result.job_id == existing_job_id
            assert "already being processed" in result.message.lower()

            # Verify duplicate check was called
            mock_duplicate_prevention.check_and_register.assert_called_once()

            # Verify job was NOT created (duplicate detected)
            mock_save_job.assert_not_called()
            mock_publish.assert_not_called()

    async def test_process_webhook_different_languages_allowed(
        self, webhook_handler, mock_duplicate_prevention
    ):
        """Test that same item with different languages creates separate jobs."""
        video_url = "/media/movie.mp4"
        job_id_en = uuid4()
        job_id_es = uuid4()

        # Mock to return not duplicate for both languages
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

        # Create webhook payloads
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Movie",
            item_type="Movie",
            item_path=video_url,
            video_url=video_url,
        )

        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ), patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ):
            # Process webhook twice (simulating different language requests)
            result1 = await webhook_handler.process_webhook(payload)
            result2 = await webhook_handler.process_webhook(payload)

            # Both should succeed
            assert result1.status == "received"
            assert result2.status == "received"

            # Should have called duplicate check twice
            assert mock_duplicate_prevention.check_and_register.call_count == 2

    @pytest.mark.parametrize(
        "event_type,item_type,should_process",
        [
            ("library.item.added", "Movie", True),
            ("library.item.updated", "Episode", True),
            ("library.item.removed", "Movie", False),  # Ignored event
            ("playback.start", "Movie", False),  # Ignored event
            ("library.item.added", "Audio", False),  # Ignored type
            ("library.item.added", "Book", False),  # Ignored type
        ],
    )
    async def test_process_webhook_event_filtering(
        self,
        webhook_handler,
        mock_duplicate_prevention,
        event_type,
        item_type,
        should_process,
    ):
        """Test that only appropriate events and item types are processed."""
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        )

        payload = JellyfinWebhookPayload(
            event=event_type,
            item_name="Test Item",
            item_type=item_type,
            item_path="/media/test.mp4",
            video_url="/media/test.mp4",
        )

        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ), patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ):
            result = await webhook_handler.process_webhook(payload)

            if should_process:
                # Should have called duplicate check
                mock_duplicate_prevention.check_and_register.assert_called_once()
                assert result.status in ["received", "duplicate"]
            else:
                # Should not have called duplicate check
                mock_duplicate_prevention.check_and_register.assert_not_called()
                assert result.status == "ignored"

    async def test_process_webhook_duplicate_prevention_disabled(
        self, webhook_handler, mock_duplicate_prevention
    ):
        """Test webhook processing when duplicate prevention is disabled."""
        # Mock as disabled
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Duplicate prevention disabled",
            )
        )

        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Movie",
            item_type="Movie",
            item_path="/media/movie.mp4",
            video_url="/media/movie.mp4",
        )

        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ), patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ):
            # Process same webhook multiple times
            result1 = await webhook_handler.process_webhook(payload)
            result2 = await webhook_handler.process_webhook(payload)

            # Both should succeed
            assert result1.status == "received"
            assert result2.status == "received"

            # Should have called duplicate check both times
            assert mock_duplicate_prevention.check_and_register.call_count == 2

    async def test_process_webhook_redis_unavailable_graceful_degradation(
        self, webhook_handler, mock_duplicate_prevention
    ):
        """Test graceful degradation when Redis is unavailable."""
        # Mock Redis unavailable scenario
        mock_duplicate_prevention.check_and_register = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Redis unavailable - duplicate prevention bypassed",
            )
        )

        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Movie",
            item_type="Movie",
            item_path="/media/movie.mp4",
            video_url="/media/movie.mp4",
        )

        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ), patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ):
            # Should allow request through despite Redis being unavailable
            result = await webhook_handler.process_webhook(payload)

            assert result.status == "received"
            # Verify duplicate check was attempted
            mock_duplicate_prevention.check_and_register.assert_called_once()

    async def test_process_webhook_no_video_url(
        self, webhook_handler, mock_duplicate_prevention
    ):
        """Test webhook processing when no video URL is provided."""
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Movie",
            item_type="Movie",
            item_path="",
            video_url=None,
        )

        # Should return error before checking for duplicates
        result = await webhook_handler.process_webhook(payload)

        assert result.status == "error"
        # Duplicate check should not be called if no video URL
        mock_duplicate_prevention.check_and_register.assert_not_called()

    @pytest.mark.parametrize(
        "num_webhooks,expected_duplicates",
        [
            (2, 1),  # 1 original + 1 duplicate
            (3, 2),  # 1 original + 2 duplicates
            (5, 4),  # 1 original + 4 duplicates
        ],
    )
    async def test_process_webhook_rapid_duplicate_webhooks(
        self,
        webhook_handler,
        mock_duplicate_prevention,
        num_webhooks,
        expected_duplicates,
    ):
        """Test handling of rapid duplicate webhooks."""
        job_id = uuid4()

        # First webhook succeeds, rest are duplicates
        mock_results = [
            DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Request registered",
            )
        ] + [
            DuplicateCheckResult(
                is_duplicate=True,
                existing_job_id=job_id,
                message=f"Already being processed as job {job_id}",
            )
            for _ in range(expected_duplicates)
        ]

        mock_duplicate_prevention.check_and_register = AsyncMock(
            side_effect=mock_results
        )

        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Movie",
            item_type="Movie",
            item_path="/media/movie.mp4",
            video_url="/media/movie.mp4",
        )

        with patch(
            "scanner.webhook_handler.redis_client.save_job", new_callable=AsyncMock
        ), patch(
            "scanner.webhook_handler.event_publisher.publish_event",
            new_callable=AsyncMock,
        ):
            results = []
            for _ in range(num_webhooks):
                result = await webhook_handler.process_webhook(payload)
                results.append(result)

            # Count duplicates
            received_count = sum(1 for r in results if r.status == "received")
            duplicate_count = sum(1 for r in results if r.status == "duplicate")

            assert received_count == 1
            assert duplicate_count == expected_duplicates

    async def test_process_webhook_exception_handling(
        self, webhook_handler, mock_duplicate_prevention
    ):
        """Test that exceptions during duplicate check are handled gracefully."""
        # Mock duplicate check to raise exception
        mock_duplicate_prevention.check_and_register = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Movie",
            item_type="Movie",
            item_path="/media/movie.mp4",
            video_url="/media/movie.mp4",
        )

        # Should return error status
        result = await webhook_handler.process_webhook(payload)

        assert result.status == "error"
        assert "error" in result.message.lower()
