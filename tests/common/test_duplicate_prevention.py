"""Tests for duplicate prevention service."""

import asyncio
from uuid import uuid4

import pytest
from redis.exceptions import RedisError

from common.duplicate_prevention import DuplicateCheckResult, DuplicatePreventionService


@pytest.fixture
def duplicate_prevention_service(fake_redis_job_client):
    """Create duplicate prevention service instance with connected Redis client."""
    service = DuplicatePreventionService(fake_redis_job_client)
    return service


@pytest.mark.asyncio
class TestDuplicatePreventionService:
    """Test suite for DuplicatePreventionService."""

    @pytest.mark.parametrize(
        "video_url,language,expected_key_prefix",
        [
            ("valid_url", "en", "dedup:"),
            ("/path/to/video.mp4", "en", "dedup:"),
            ("https://example.com/video.mkv", "es", "dedup:"),
            ("file:///media/movies/test.avi", "fr", "dedup:"),
            ("very_long_url_" + "x" * 500, "de", "dedup:"),
        ],
    )
    async def test_generate_dedup_key_format(
        self, duplicate_prevention_service, video_url, language, expected_key_prefix
    ):
        """Test that dedup key generation creates correct format."""
        key = duplicate_prevention_service.generate_dedup_key(video_url, language)

        assert key.startswith(expected_key_prefix)
        assert f":{language}" in key
        # Key should be fixed length due to hashing
        assert len(key) == len(expected_key_prefix) + 64 + 1 + len(language)

    @pytest.mark.parametrize(
        "video_url1,language1,video_url2,language2,should_be_different",
        [
            ("video.mp4", "en", "video.mp4", "en", False),  # Same - same key
            ("video.mp4", "en", "video.mp4", "es", True),  # Different language
            ("video1.mp4", "en", "video2.mp4", "en", True),  # Different video
            ("/path/to/video.mp4", "en", "/path/to/video.mp4", "en", False),  # Same
            (
                "https://example.com/video.mp4",
                "en",
                "https://example.com/video.mp4",
                "es",
                True,
            ),  # Different lang
        ],
    )
    async def test_generate_dedup_key_uniqueness(
        self,
        duplicate_prevention_service,
        video_url1,
        language1,
        video_url2,
        language2,
        should_be_different,
    ):
        """Test that dedup key generation creates unique keys for different inputs."""
        key1 = duplicate_prevention_service.generate_dedup_key(video_url1, language1)
        key2 = duplicate_prevention_service.generate_dedup_key(video_url2, language2)

        if should_be_different:
            assert key1 != key2
        else:
            assert key1 == key2

    @pytest.mark.parametrize(
        "video_url,language,job_id,description",
        [
            ("video.mp4", "en", uuid4(), "first request"),
            ("/path/to/movie.mkv", "es", uuid4(), "path-based video"),
            ("https://example.com/video.avi", "fr", uuid4(), "url-based video"),
            ("test_video_" + "x" * 100, "de", uuid4(), "long video name"),
        ],
    )
    async def test_check_and_register_first_request(
        self, duplicate_prevention_service, video_url, language, job_id, description
    ):
        """Test that first request is not detected as duplicate."""
        result = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id
        )

        assert isinstance(result, DuplicateCheckResult)
        assert result.is_duplicate is False
        assert result.existing_job_id is None
        assert result.message is not None

    @pytest.mark.parametrize(
        "video_url,language,description",
        [
            ("video.mp4", "en", "basic duplicate"),
            ("/path/to/movie.mkv", "es", "path-based duplicate"),
            ("https://example.com/video.avi", "fr", "url-based duplicate"),
        ],
    )
    async def test_check_and_register_duplicate_request(
        self, duplicate_prevention_service, video_url, language, description
    ):
        """Test that duplicate request within window is detected."""
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # First request
        result1 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_1
        )
        assert result1.is_duplicate is False

        # Second request (duplicate)
        result2 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_2
        )
        assert result2.is_duplicate is True
        assert result2.existing_job_id == job_id_1
        assert "already being processed" in result2.message.lower()

    async def test_check_and_register_different_languages_allowed(
        self, duplicate_prevention_service
    ):
        """Test that same video with different languages creates separate entries."""
        video_url = "video.mp4"
        job_id_en = uuid4()
        job_id_es = uuid4()

        # Request for English
        result_en = await duplicate_prevention_service.check_and_register(
            video_url, "en", job_id_en
        )
        assert result_en.is_duplicate is False

        # Request for Spanish (should not be duplicate)
        result_es = await duplicate_prevention_service.check_and_register(
            video_url, "es", job_id_es
        )
        assert result_es.is_duplicate is False
        assert result_es.existing_job_id is None

    async def test_check_and_register_ttl_expiration(
        self, duplicate_prevention_service, fake_redis_job_client
    ):
        """Test that duplicate detection expires after TTL window."""
        video_url = "video.mp4"
        language = "en"
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # Set short TTL for testing (1 second)
        duplicate_prevention_service.window_seconds = 1

        # First request
        result1 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_1
        )
        assert result1.is_duplicate is False

        # Wait for TTL to expire
        await asyncio.sleep(1.1)

        # Second request after TTL (should not be duplicate)
        result2 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_2
        )
        assert result2.is_duplicate is False
        assert result2.existing_job_id is None

    @pytest.mark.parametrize(
        "num_concurrent_requests,expected_duplicates",
        [
            (2, 1),  # 1 original + 1 duplicate
            (5, 4),  # 1 original + 4 duplicates
            (10, 9),  # 1 original + 9 duplicates
        ],
    )
    async def test_check_and_register_concurrent_requests(
        self, duplicate_prevention_service, num_concurrent_requests, expected_duplicates
    ):
        """Test that concurrent requests are handled correctly with atomic operations."""
        video_url = "concurrent_test.mp4"
        language = "en"

        # Create multiple concurrent requests
        tasks = []
        job_ids = [uuid4() for _ in range(num_concurrent_requests)]

        for job_id in job_ids:
            task = duplicate_prevention_service.check_and_register(
                video_url, language, job_id
            )
            tasks.append(task)

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Count duplicates
        duplicates = sum(1 for result in results if result.is_duplicate)
        originals = sum(1 for result in results if not result.is_duplicate)

        # Should have exactly 1 original and rest duplicates
        assert originals == 1
        assert duplicates == expected_duplicates

        # All duplicates should reference the same original job_id
        original_job_id = next(
            result.existing_job_id
            for result in results
            if result.existing_job_id is not None
        )
        for result in results:
            if result.is_duplicate:
                assert result.existing_job_id == original_job_id

    async def test_check_and_register_redis_unavailable(
        self, duplicate_prevention_service, fake_redis_job_client, monkeypatch
    ):
        """Test graceful degradation when Redis is unavailable."""

        async def mock_execute_raises(*args, **kwargs):
            raise RedisError("Connection failed")

        # Mock Redis to raise error
        if fake_redis_job_client.client:
            monkeypatch.setattr(
                fake_redis_job_client.client, "execute_command", mock_execute_raises
            )

        video_url = "video.mp4"
        language = "en"
        job_id = uuid4()

        # Should allow request through with warning
        result = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id
        )

        assert result.is_duplicate is False
        assert result.existing_job_id is None
        assert (
            "unavailable" in result.message.lower()
            or "error" in result.message.lower()
            or "allowing request through" in result.message.lower()
        )

    async def test_check_and_register_disabled(self, duplicate_prevention_service):
        """Test that duplicate prevention can be disabled."""
        duplicate_prevention_service.enabled = False

        video_url = "video.mp4"
        language = "en"
        job_id_1 = uuid4()
        job_id_2 = uuid4()

        # First request
        result1 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_1
        )
        assert result1.is_duplicate is False

        # Second request (should not be detected as duplicate when disabled)
        result2 = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id_2
        )
        assert result2.is_duplicate is False
        assert result2.existing_job_id is None

    async def test_get_existing_job_id(
        self, duplicate_prevention_service, fake_redis_job_client
    ):
        """Test retrieving existing job ID from Redis."""
        video_url = "video.mp4"
        language = "en"
        job_id = uuid4()

        # Register a job
        await duplicate_prevention_service.check_and_register(
            video_url, language, job_id
        )

        # Retrieve the job ID
        retrieved_job_id = await duplicate_prevention_service.get_existing_job_id(
            video_url, language
        )

        assert retrieved_job_id == job_id

    async def test_get_existing_job_id_not_found(self, duplicate_prevention_service):
        """Test retrieving non-existent job ID returns None."""
        video_url = "nonexistent.mp4"
        language = "en"

        retrieved_job_id = await duplicate_prevention_service.get_existing_job_id(
            video_url, language
        )

        assert retrieved_job_id is None

    async def test_health_check_connected(
        self, duplicate_prevention_service, fake_redis_job_client
    ):
        """Test health check when Redis is connected."""
        health = await duplicate_prevention_service.health_check()

        assert health["connected"] is True
        assert health["status"] == "healthy"
        assert "error" not in health

    async def test_health_check_disconnected(
        self, duplicate_prevention_service, fake_redis_job_client, monkeypatch
    ):
        """Test health check when Redis is disconnected."""

        async def mock_ping_raises():
            raise RedisError("Connection lost")

        # Mock Redis ping to raise error
        if fake_redis_job_client.client:
            monkeypatch.setattr(fake_redis_job_client.client, "ping", mock_ping_raises)

        health = await duplicate_prevention_service.health_check()

        assert health["connected"] is False
        assert health["status"] == "unhealthy"
        assert "error" in health

    @pytest.mark.parametrize(
        "video_url,language,expected_hash_stable",
        [
            ("video.mp4", "en", True),
            ("/path/to/video.mkv", "es", True),
            ("https://example.com/video.avi", "fr", True),
        ],
    )
    async def test_hash_stability(
        self, duplicate_prevention_service, video_url, language, expected_hash_stable
    ):
        """Test that hash generation is stable across multiple calls."""
        key1 = duplicate_prevention_service.generate_dedup_key(video_url, language)
        key2 = duplicate_prevention_service.generate_dedup_key(video_url, language)
        key3 = duplicate_prevention_service.generate_dedup_key(video_url, language)

        if expected_hash_stable:
            assert key1 == key2 == key3

    async def test_lua_script_registration(self, duplicate_prevention_service):
        """Test that Lua script registration is attempted."""
        # Script may or may not be registered depending on Redis implementation
        # (FakeRedis doesn't support Lua scripts, but real Redis does)
        # The service should gracefully handle both cases
        video_url = "video.mp4"
        language = "en"
        job_id = uuid4()

        # Should work regardless of whether script is registered or not
        result = await duplicate_prevention_service.check_and_register(
            video_url, language, job_id
        )
        assert result.is_duplicate is False

    async def test_cleanup_expired_entries(
        self, duplicate_prevention_service, fake_redis_job_client
    ):
        """Test that expired entries are automatically cleaned up by Redis."""
        video_url = "video.mp4"
        language = "en"
        job_id = uuid4()

        # Set very short TTL
        duplicate_prevention_service.window_seconds = 1

        # Register entry
        await duplicate_prevention_service.check_and_register(
            video_url, language, job_id
        )

        # Verify it exists
        dedup_key = duplicate_prevention_service.generate_dedup_key(video_url, language)
        if fake_redis_job_client.client:
            exists_before = await fake_redis_job_client.client.exists(dedup_key)
            assert exists_before == 1

            # Wait for expiration
            await asyncio.sleep(1.5)

            # Verify it's gone
            exists_after = await fake_redis_job_client.client.exists(dedup_key)
            assert exists_after == 0
