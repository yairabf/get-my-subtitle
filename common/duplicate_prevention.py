"""Duplicate prevention service using Redis for distributed deduplication."""

import hashlib
import logging
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from redis.exceptions import RedisError

from common.config import settings

logger = logging.getLogger(__name__)


class DuplicateCheckResult(BaseModel):
    """Result of duplicate check operation."""

    is_duplicate: bool
    existing_job_id: Optional[UUID] = None
    message: str


class DuplicatePreventionService:
    """Service for preventing duplicate subtitle requests using Redis."""

    # Lua script for atomic check-and-register operation
    CHECK_AND_REGISTER_SCRIPT = """
    local dedup_key = KEYS[1]
    local job_id = ARGV[1]
    local ttl = tonumber(ARGV[2])

    -- Check if key exists
    local existing_job_id = redis.call('GET', dedup_key)

    if existing_job_id then
        -- Duplicate detected, return existing job_id
        return existing_job_id
    end

    -- Not a duplicate, register this request
    redis.call('SET', dedup_key, job_id, 'EX', ttl)
    return nil
    """

    def __init__(self, redis_client):
        """
        Initialize duplicate prevention service.

        Args:
            redis_client: RedisJobClient instance for Redis operations
        """
        self.redis_client = redis_client
        self.enabled = settings.duplicate_prevention_enabled
        self.window_seconds = settings.duplicate_prevention_window_seconds
        self.check_and_register_script = None

    async def _ensure_script_loaded(self) -> None:
        """Ensure Lua script is loaded into Redis."""
        if self.check_and_register_script is None and self.redis_client.client:
            try:
                self.check_and_register_script = (
                    self.redis_client.client.register_script(
                        self.CHECK_AND_REGISTER_SCRIPT
                    )
                )
                logger.debug("Duplicate prevention Lua script registered")
            except Exception as e:
                logger.warning(f"Failed to register Lua script: {e}")

    def generate_dedup_key(self, video_url: str, language: str) -> str:
        """
        Generate Redis key for deduplication.

        Uses SHA256 hash of video_url to create fixed-length keys.
        Format: dedup:{url_hash}:{language}

        Args:
            video_url: URL or path to video file
            language: Source language code

        Returns:
            Redis key string for deduplication
        """
        # Hash the video URL to create fixed-length key
        url_hash = hashlib.sha256(video_url.encode()).hexdigest()
        return f"dedup:{url_hash}:{language}"

    async def check_and_register(
        self, video_url: str, language: str, job_id: UUID
    ) -> DuplicateCheckResult:
        """
        Check if request is duplicate and register if not.

        This operation is atomic using a Lua script to prevent race conditions.

        Args:
            video_url: URL or path to video file
            language: Source language code
            job_id: Job ID for this request

        Returns:
            DuplicateCheckResult with duplicate status and existing job_id if applicable
        """
        # If duplicate prevention is disabled, always allow
        if not self.enabled:
            logger.debug("Duplicate prevention is disabled")
            return DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Duplicate prevention disabled",
            )

        # If Redis is not connected, allow request through with warning
        if not self.redis_client.connected or not self.redis_client.client:
            logger.warning(
                "Redis unavailable - allowing request through "
                "(duplicate prevention bypassed)"
            )
            return DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message="Redis unavailable - duplicate prevention bypassed",
            )

        try:
            # Ensure Lua script is loaded
            await self._ensure_script_loaded()

            # Generate deduplication key
            dedup_key = self.generate_dedup_key(video_url, language)

            # Execute atomic check-and-register via Lua script
            if self.check_and_register_script:
                existing_job_id_str = (
                    await self.check_and_register_script(
                        keys=[dedup_key],
                        args=[str(job_id), self.window_seconds],
                    )
                )
            else:
                # Fallback to non-atomic operations if script not loaded
                logger.warning(
                    "Lua script not loaded, using fallback method"
                )
                existing_job_id_str = (
                    await self._fallback_check_and_register(
                        dedup_key, job_id
                    )
                )

            if existing_job_id_str:
                # Duplicate detected
                try:
                    existing_job_id = UUID(existing_job_id_str)
                    logger.info(
                        f"Duplicate request detected for {video_url} "
                        f"({language}) - already being processed as job "
                        f"{existing_job_id}"
                    )
                    return DuplicateCheckResult(
                        is_duplicate=True,
                        existing_job_id=existing_job_id,
                        message=(
                            f"Request already being processed as job "
                            f"{existing_job_id}"
                        ),
                    )
                except ValueError as e:
                    logger.error(
                        f"Invalid UUID in Redis: {existing_job_id_str}: {e}"
                    )
                    # Treat as non-duplicate and overwrite bad data
                    await self.redis_client.client.set(
                        dedup_key, str(job_id), ex=self.window_seconds
                    )
                    return DuplicateCheckResult(
                        is_duplicate=False,
                        existing_job_id=None,
                        message="Request registered (corrected invalid data)",
                    )

            # Not a duplicate
            logger.debug(
                f"New request registered for {video_url} ({language}) "
                f"as job {job_id}"
            )
            return DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message=(
                    f"Request registered with {self.window_seconds}s "
                    f"deduplication window"
                ),
            )

        except RedisError as e:
            logger.error(f"Redis error during duplicate check: {e}")
            # Allow request through on error (graceful degradation)
            return DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message=f"Redis error - allowing request through: {str(e)}",
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during duplicate check: {e}",
                exc_info=True,
            )
            # Allow request through on error (graceful degradation)
            return DuplicateCheckResult(
                is_duplicate=False,
                existing_job_id=None,
                message=(
                    f"Error during duplicate check - allowing request "
                    f"through: {str(e)}"
                ),
            )

    async def _fallback_check_and_register(
        self, dedup_key: str, job_id: UUID
    ) -> Optional[str]:
        """
        Fallback non-atomic check-and-register when Lua script unavailable.

        Args:
            dedup_key: Redis key for deduplication
            job_id: Job ID to register

        Returns:
            Existing job_id string if duplicate, None if new
        """
        # Check if key exists
        existing_job_id_str = await self.redis_client.client.get(dedup_key)

        if existing_job_id_str:
            return existing_job_id_str

        # Register new request
        await self.redis_client.client.set(
            dedup_key, str(job_id), ex=self.window_seconds
        )
        return None

    async def get_existing_job_id(
        self, video_url: str, language: str
    ) -> Optional[UUID]:
        """
        Retrieve existing job ID for a video/language combination.

        Args:
            video_url: URL or path to video file
            language: Source language code

        Returns:
            Existing job UUID if found, None otherwise
        """
        if not self.redis_client.connected or not self.redis_client.client:
            logger.warning("Redis unavailable - cannot retrieve existing job ID")
            return None

        try:
            dedup_key = self.generate_dedup_key(video_url, language)
            job_id_str = await self.redis_client.client.get(dedup_key)

            if job_id_str:
                try:
                    return UUID(job_id_str)
                except ValueError as e:
                    logger.error(f"Invalid UUID in Redis: {job_id_str}: {e}")
                    return None

            return None

        except RedisError as e:
            logger.error(f"Redis error retrieving existing job ID: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error retrieving existing job ID: {e}", exc_info=True
            )
            return None

    async def health_check(self) -> dict:
        """
        Check health of duplicate prevention service.

        Returns:
            Dictionary with health status information
        """
        if not self.enabled:
            return {
                "connected": False,
                "status": "disabled",
                "message": "Duplicate prevention is disabled",
            }

        if not self.redis_client.client:
            return {
                "connected": False,
                "status": "disconnected",
                "error": "Redis client not initialized",
            }

        try:
            await self.redis_client.client.ping()
            return {
                "connected": True,
                "status": "healthy",
                "window_seconds": self.window_seconds,
            }
        except RedisError as e:
            return {"connected": False, "status": "unhealthy", "error": str(e)}
