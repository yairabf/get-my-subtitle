"""End-to-end integration tests for duplicate prevention."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.duplicate_prevention import DuplicatePreventionService
from common.redis_client import redis_client
from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils
from manager.event_consumer import SubtitleEventConsumer
from manager.schemas import JellyfinWebhookPayload
from scanner.event_handler import MediaFileEventHandler
from scanner.scanner import MediaScanner
from scanner.webhook_handler import JellyfinWebhookHandler


@pytest.fixture
async def duplicate_prevention_service(fake_redis_job_client):
    """Create duplicate prevention service instance with connected Redis client."""
    service = DuplicatePreventionService(fake_redis_job_client)
    yield service
    # Cleanup: Remove all test keys
    if fake_redis_job_client.connected and fake_redis_job_client.client:
        async for key in fake_redis_job_client.client.scan_iter(match="dedup:*"):
            await fake_redis_job_client.client.delete(key)


@pytest.mark.asyncio
@pytest.mark.integration
class TestEndToEndDuplicatePrevention:
    """End-to-end integration tests for duplicate prevention across all layers."""

    async def test_scanner_to_manager_duplicate_prevention(
        self, duplicate_prevention_service
    ):
        """Test duplicate prevention from scanner through to manager."""
        video_url = "/media/test_movie.mp4"
        language = "en"
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # First request at scanner level
        result1 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_1
        )
        assert result1.is_duplicate is False

        # Second request at scanner level (should be duplicate)
        result2 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_2
        )
        assert result2.is_duplicate is True
        assert result2.existing_job_id == job_id_1

        # If duplicate somehow reaches manager (defense in depth)
        result3 = await duplicate_prevention_service.check_and_register(
            video_url, language, uuid4()
        )
        assert result3.is_duplicate is True
        assert result3.existing_job_id == job_id_1

    async def test_webhook_duplicate_prevention_flow(
        self, duplicate_prevention_service
    ):
        """Test complete webhook duplicate prevention flow."""
        webhook_handler = JellyfinWebhookHandler()
        video_url = "/media/webhook_test.mp4"

        # Create webhook payload
        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Test Movie",
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
            # First webhook
            result1 = await webhook_handler.process_webhook(payload)
            assert result1.status == "received"
            first_job_id = result1.job_id

            # Second webhook (duplicate)
            result2 = await webhook_handler.process_webhook(payload)
            assert result2.status == "duplicate"
            assert result2.job_id == first_job_id

            # Third webhook (still duplicate)
            result3 = await webhook_handler.process_webhook(payload)
            assert result3.status == "duplicate"
            assert result3.job_id == first_job_id

    async def test_file_scanner_duplicate_prevention_flow(
        self, duplicate_prevention_service
    ):
        """Test complete file scanner duplicate prevention flow."""
        mock_scanner = MagicMock(spec=MediaScanner)
        event_handler = MediaFileEventHandler(mock_scanner)
        file_path = "/media/scanner_test.mp4"

        with patch("scanner.event_handler.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.is_file.return_value = True
            mock_file.stat.return_value.st_size = 1000000
            mock_file.stem = "scanner_test"
            mock_file.suffix = ".mp4"
            mock_path.return_value = mock_file

            with patch.object(
                redis_client, "save_job", new_callable=AsyncMock
            ) as mock_save_job, patch(
                "scanner.event_handler.event_publisher.publish_event",
                new_callable=AsyncMock,
            ):
                # First file detection
                await event_handler._process_media_file(file_path)
                assert mock_save_job.call_count == 1

                # Second file detection (duplicate)
                await event_handler._process_media_file(file_path)
                # Should still be 1 (duplicate prevented)
                assert mock_save_job.call_count == 1

    async def test_manager_layer_catches_scanner_bypass(
        self, duplicate_prevention_service
    ):
        """Test that manager layer catches duplicates that bypass scanner."""
        event_consumer = SubtitleEventConsumer()
        video_url = "/media/bypass_test.mp4"
        language = "en"

        # Simulate scanner processing first request
        job_id_1 = uuid4()
        scanner_result = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_1
        )
        assert scanner_result.is_duplicate is False

        # Simulate duplicate event reaching manager (bypass scenario)
        job_id_2 = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id_2,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": video_url,
                "video_title": "Bypass Test",
                "language": language,
                "target_language": None,
                "preferred_sources": ["opensubtitles"],
            },
        )

        with patch(
            "manager.event_consumer.orchestrator.enqueue_download_task",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            # Manager should detect and prevent duplicate
            await event_consumer._process_subtitle_request(event)

            # Enqueue should NOT be called (duplicate caught at manager level)
            mock_enqueue.assert_not_called()

    async def test_multi_language_requests_allowed(self, duplicate_prevention_service):
        """Test that same video with different languages is allowed."""
        video_url = "/media/multilang_test.mp4"
        job_id_en = uuid4()
        job_id_es = uuid4()
        job_id_fr = uuid4()

        # English request
        result_en = await duplicate_prevention_service.check_and_register(
            video_url, "en", job_id_en
        )
        assert result_en.is_duplicate is False

        # Spanish request (should be allowed)
        result_es = await duplicate_prevention_service.check_and_register(
            video_url, "es", job_id_es
        )
        assert result_es.is_duplicate is False

        # French request (should be allowed)
        result_fr = await duplicate_prevention_service.check_and_register(
            video_url, "fr", job_id_fr
        )
        assert result_fr.is_duplicate is False

        # Duplicate English request (should be blocked)
        result_en_dup = await duplicate_prevention_service.check_and_register(
            video_url, "en", uuid4()
        )
        assert result_en_dup.is_duplicate is True
        assert result_en_dup.existing_job_id == job_id_en

    async def test_window_expiration_allows_reprocessing(
        self, duplicate_prevention_service
    ):
        """Test that duplicate detection expires after window."""
        video_url = "/media/expiration_test.mp4"
        language = "en"
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # Set short TTL for testing
        duplicate_prevention_service.window_seconds = 1

        # First request
        result1 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_1
        )
        assert result1.is_duplicate is False

        # Immediate duplicate (should be blocked)
        result2 = await duplicate_prevention_service.check_and_register(
            video_url, language, uuid4()
        )
        assert result2.is_duplicate is True

        # Wait for expiration
        await asyncio.sleep(1.2)

        # After expiration (should be allowed)
        result3 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_2
        )
        assert result3.is_duplicate is False

    async def test_disabled_duplicate_prevention_allows_all(
        self, duplicate_prevention_service
    ):
        """Test that disabling duplicate prevention allows all requests."""
        duplicate_prevention_service.enabled = False

        video_url = "/media/disabled_test.mp4"
        language = "en"

        # Multiple requests should all succeed when disabled
        for i in range(5):
            result = await duplicate_prevention_service.check_and_register(
                video_url, language, uuid4()
            )
            assert result.is_duplicate is False

    async def test_redis_unavailable_graceful_degradation(
        self, duplicate_prevention_service, fake_redis_job_client, monkeypatch
    ):
        """Test graceful degradation when Redis is unavailable."""

        async def mock_execute_raises(*args, **kwargs):
            from redis.exceptions import RedisError

            raise RedisError("Connection failed")

        # Mock Redis to raise error
        if fake_redis_job_client.client:
            monkeypatch.setattr(
                fake_redis_job_client.client, "execute_command", mock_execute_raises
            )

        video_url = "/media/redis_unavailable.mp4"
        language = "en"

        # Should allow requests through when Redis is unavailable
        for i in range(3):
            result = await duplicate_prevention_service.check_and_register(
                video_url, language, uuid4()
            )
            assert result.is_duplicate is False
            assert (
                "unavailable" in result.message.lower()
                or "warning" in result.message.lower()
            )

    async def test_concurrent_requests_atomic_deduplication(
        self, duplicate_prevention_service
    ):
        """Test that concurrent requests are handled atomically."""
        video_url = "/media/concurrent_test.mp4"
        language = "en"
        num_concurrent = 10

        # Create concurrent requests
        job_ids = [uuid4() for _ in range(num_concurrent)]
        tasks = []

        for job_id in job_ids:
            task = duplicate_prevention_service.check_and_register(
                video_url, language, job_id
            )
            tasks.append(task)

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Count originals and duplicates
        originals = [r for r in results if not r.is_duplicate]
        duplicates = [r for r in results if r.is_duplicate]

        # Should have exactly 1 original
        assert len(originals) == 1

        # All duplicates should reference the same original job_id
        original_job_id = originals[0]
        for duplicate_result in duplicates:
            assert (
                duplicate_result.existing_job_id == job_ids[results.index(originals[0])]
            )

    async def test_different_paths_same_name_no_collision(
        self, duplicate_prevention_service
    ):
        """Test that files with same name in different paths are not duplicates."""
        job_id_1 = uuid4()
        job_id_2 = uuid4()
        language = "en"

        # Same filename, different paths
        path1 = "/media/movies/video.mp4"
        path2 = "/media/shows/video.mp4"

        # Both should be allowed (different paths)
        result1 = await duplicate_prevention_service.check_and_register(
            path1, language, job_id_1
        )
        assert result1.is_duplicate is False

        result2 = await duplicate_prevention_service.check_and_register(
            path2, language, job_id_2
        )
        assert result2.is_duplicate is False

    async def test_health_check_integration(self, duplicate_prevention_service):
        """Test health check reports correct status."""
        health = await duplicate_prevention_service.health_check()

        if duplicate_prevention_service.enabled and redis_client.connected:
            assert health["connected"] is True
            assert health["status"] == "healthy"
            assert (
                health["window_seconds"] == duplicate_prevention_service.window_seconds
            )
        else:
            assert health["connected"] is False

    @pytest.mark.parametrize(
        "num_videos,num_languages,expected_unique_jobs",
        [
            (1, 1, 1),  # Single video, single language
            (1, 3, 3),  # Single video, three languages
            (3, 1, 3),  # Three videos, single language
            (3, 2, 6),  # Three videos, two languages each
        ],
    )
    async def test_complex_multi_video_multi_language_scenario(
        self,
        duplicate_prevention_service,
        num_videos,
        num_languages,
        expected_unique_jobs,
    ):
        """Test complex scenarios with multiple videos and languages."""
        videos = [f"/media/video_{i}.mp4" for i in range(num_videos)]
        languages = ["en", "es", "fr"][:num_languages]

        results = []
        for video in videos:
            for language in languages:
                result = await duplicate_prevention_service.check_and_register(
                    video, language, uuid4()
                )
                results.append(result)

        # Count unique jobs (non-duplicates)
        unique_jobs = sum(1 for r in results if not r.is_duplicate)
        assert unique_jobs == expected_unique_jobs

        # Now send duplicates for all combinations
        duplicate_results = []
        for video in videos:
            for language in languages:
                result = await duplicate_prevention_service.check_and_register(
                    video, language, uuid4()
                )
                duplicate_results.append(result)

        # All should be duplicates
        assert all(r.is_duplicate for r in duplicate_results)

    async def test_rapid_webhook_events_deduplicated_end_to_end(
        self, duplicate_prevention_service
    ):
        """Test that rapid webhook events are properly deduplicated end-to-end."""
        webhook_handler = JellyfinWebhookHandler()
        video_url = "/media/rapid_webhook.mp4"

        payload = JellyfinWebhookPayload(
            event="library.item.added",
            item_name="Rapid Test",
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
            # Simulate rapid webhooks
            results = []
            for _ in range(5):
                result = await webhook_handler.process_webhook(payload)
                results.append(result)

            # First should be received
            assert results[0].status == "received"
            first_job_id = results[0].job_id

            # Rest should be duplicates
            for result in results[1:]:
                assert result.status == "duplicate"
                assert result.job_id == first_job_id
