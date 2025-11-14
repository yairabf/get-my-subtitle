"""Redis client for job tracking across all services."""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from common.config import settings
from common.schemas import SubtitleResponse, SubtitleStatus
from common.utils import DateTimeUtils, StringUtils

logger = logging.getLogger(__name__)


class RedisJobClient:
    """Async Redis client for managing subtitle processing jobs."""

    def __init__(self):
        """Initialize the Redis client."""
        self.client: Optional[Redis] = None
        self.connected: bool = False

    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )
            # Test connection
            await self.client.ping()
            self.connected = True
            logger.info("Connected to Redis successfully")
        except RedisError as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            logger.warning("Jobs will not be persisted - Redis unavailable")
            self.connected = False

    async def disconnect(self) -> None:
        """Close connection to Redis."""
        if self.client:
            await self.client.close()
            self.connected = False
            logger.info("Disconnected from Redis")

    def _get_job_key(self, job_id: UUID) -> str:
        """
        Generate Redis key for a job.

        Args:
            job_id: UUID of the job

        Returns:
            Redis key string in format 'job:uuid'
        """
        return StringUtils.generate_job_key(str(job_id))

    def _get_job_events_key(self, job_id: UUID) -> str:
        """
        Generate Redis key for job event history.

        Args:
            job_id: UUID of the job

        Returns:
            Redis key string in format 'job:events:uuid'
        """
        return f"job:events:{str(job_id)}"

    def _get_ttl_for_status(self, status: SubtitleStatus) -> int:
        """
        Get TTL (time-to-live) in seconds based on job status.

        Returns:
            TTL in seconds, or 0 for no expiration
        """
        if status == SubtitleStatus.COMPLETED:
            return settings.redis_job_ttl_completed
        elif status == SubtitleStatus.FAILED:
            return settings.redis_job_ttl_failed
        else:
            # PENDING, DOWNLOADING, TRANSLATING - no expiration
            return settings.redis_job_ttl_active

    async def save_job(self, job: SubtitleResponse) -> bool:
        """
        Save a job to Redis with appropriate TTL.

        Args:
            job: SubtitleResponse object to store

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot save job {job.id}")
            return False

        try:
            job_key = self._get_job_key(job.id)
            job_data = job.model_dump(mode="json")

            # Convert to JSON string for storage
            job_json = json.dumps(job_data)

            # Store in Redis
            await self.client.set(job_key, job_json)

            # Set TTL based on status
            ttl = self._get_ttl_for_status(job.status)
            if ttl > 0:
                await self.client.expire(job_key, ttl)

            logger.debug(f"Saved job {job.id} with status {job.status.value}")
            return True

        except RedisError as e:
            logger.error(f"Failed to save job {job.id} to Redis: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving job {job.id}: {e}")
            return False

    async def get_job(self, job_id: UUID) -> Optional[SubtitleResponse]:
        """
        Retrieve a job from Redis by ID.

        Args:
            job_id: UUID of the job to retrieve

        Returns:
            SubtitleResponse object if found, None otherwise
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot get job {job_id}")
            return None

        try:
            job_key = self._get_job_key(job_id)
            job_json = await self.client.get(job_key)

            if not job_json:
                logger.debug(f"Job {job_id} not found in Redis")
                return None

            # Deserialize from JSON
            job_data = json.loads(job_json)
            job = SubtitleResponse.model_validate(job_data)

            logger.debug(f"Retrieved job {job_id} with status {job.status.value}")
            return job

        except RedisError as e:
            logger.error(f"Failed to get job {job_id} from Redis: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting job {job_id}: {e}")
            return None

    async def update_job_status(
        self,
        job_id: UUID,
        status: SubtitleStatus,
        error_message: Optional[str] = None,
        download_url: Optional[str] = None,
    ) -> bool:
        """
        Update job status and optionally error message or download URL.

        Args:
            job_id: UUID of the job to update
            status: New status
            error_message: Optional error message (for FAILED status)
            download_url: Optional download URL (for COMPLETED status)

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot update job {job_id}")
            return False

        try:
            # Get existing job
            job = await self.get_job(job_id)
            if not job:
                logger.warning(f"Cannot update non-existent job {job_id}")
                return False

            # Update fields
            job.status = status
            if error_message is not None:
                job.error_message = error_message
            if download_url is not None:
                job.download_url = download_url

            # Update timestamp using utility function
            job.updated_at = DateTimeUtils.get_current_utc_datetime()

            # Save updated job
            success = await self.save_job(job)

            if success:
                logger.info(f"Updated job {job_id} status to {status.value}")

            return success

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False

    async def list_jobs(
        self, status_filter: Optional[SubtitleStatus] = None
    ) -> List[SubtitleResponse]:
        """
        List all jobs, optionally filtered by status.

        Args:
            status_filter: Optional status to filter by

        Returns:
            List of SubtitleResponse objects
        """
        if not self.connected or not self.client:
            logger.warning("Redis unavailable - cannot list jobs")
            return []

        try:
            # Get all job keys
            job_keys = []
            async for key in self.client.scan_iter(match="job:*"):
                job_keys.append(key)

            if not job_keys:
                return []

            # Retrieve all jobs
            jobs = []
            for key in job_keys:
                job_json = await self.client.get(key)
                if job_json:
                    try:
                        job_data = json.loads(job_json)
                        job = SubtitleResponse.model_validate(job_data)

                        # Apply status filter if provided
                        if status_filter is None or job.status == status_filter:
                            jobs.append(job)
                    except Exception as e:
                        logger.error(f"Failed to deserialize job from key {key}: {e}")
                        continue

            logger.debug(f"Retrieved {len(jobs)} jobs from Redis")
            return jobs

        except RedisError as e:
            logger.error(f"Failed to list jobs from Redis: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing jobs: {e}")
            return []

    async def delete_job(self, job_id: UUID) -> bool:
        """
        Delete a job from Redis.

        Args:
            job_id: UUID of the job to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot delete job {job_id}")
            return False

        try:
            job_key = self._get_job_key(job_id)
            deleted = await self.client.delete(job_key)

            if deleted:
                logger.info(f"Deleted job {job_id} from Redis")
                return True
            else:
                logger.warning(f"Job {job_id} not found for deletion")
                return False

        except RedisError as e:
            logger.error(f"Failed to delete job {job_id} from Redis: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting job {job_id}: {e}")
            return False

    async def update_phase(
        self,
        job_id: UUID,
        status: SubtitleStatus,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update job status with source tracking.

        Args:
            job_id: UUID of the job to update
            status: New status
            source: Source service making the update
            metadata: Optional metadata to merge into job

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot update phase for job {job_id}")
            return False

        try:
            # Get existing job
            job = await self.get_job(job_id)
            if not job:
                logger.warning(f"Cannot update phase for non-existent job {job_id}")
                return False

            # Update fields
            job.status = status
            job.updated_at = DateTimeUtils.get_current_utc_datetime()

            # Merge metadata if provided
            if metadata:
                if metadata.get("error_message"):
                    job.error_message = metadata["error_message"]
                if metadata.get("download_url"):
                    job.download_url = metadata["download_url"]

            # Save updated job
            success = await self.save_job(job)

            if success:
                logger.info(
                    f"Updated job {job_id} phase to {status.value} (source: {source})"
                )

            return success

        except Exception as e:
            logger.error(f"Failed to update job {job_id} phase: {e}")
            return False

    async def record_event(
        self,
        job_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
        source: str,
    ) -> bool:
        """
        Record event history for a job in Redis list.

        Args:
            job_id: UUID of the job
            event_type: Type of event
            payload: Event payload data
            source: Source service that generated the event

        Returns:
            True if successful, False otherwise
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot record event for job {job_id}")
            return False

        try:
            events_key = self._get_job_events_key(job_id)

            # Create event record
            event_record = {
                "event_type": event_type,
                "timestamp": DateTimeUtils.get_current_utc_datetime().isoformat(),
                "source": source,
                "payload": payload,
            }

            # Store as JSON string in Redis list
            event_json = json.dumps(event_record)
            await self.client.lpush(events_key, event_json)

            # Set TTL for event history (same as completed jobs)
            ttl = settings.redis_job_ttl_completed
            if ttl > 0:
                await self.client.expire(events_key, ttl)

            logger.debug(
                f"Recorded event {event_type} for job {job_id} (source: {source})"
            )
            return True

        except RedisError as e:
            logger.error(f"Failed to record event for job {job_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error recording event for job {job_id}: {e}")
            return False

    async def get_job_events(
        self, job_id: UUID, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Retrieve event history for a job.

        Args:
            job_id: UUID of the job
            limit: Maximum number of events to retrieve (default: 50)

        Returns:
            List of event records (most recent first)
        """
        if not self.connected or not self.client:
            logger.warning(f"Redis unavailable - cannot get events for job {job_id}")
            return []

        try:
            events_key = self._get_job_events_key(job_id)

            # Get events from Redis list (most recent first)
            event_jsons = await self.client.lrange(events_key, 0, limit - 1)

            if not event_jsons:
                logger.debug(f"No events found for job {job_id}")
                return []

            # Deserialize events
            events = []
            for event_json in event_jsons:
                try:
                    event = json.loads(event_json)
                    events.append(event)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to deserialize event: {e}")
                    continue

            logger.debug(f"Retrieved {len(events)} events for job {job_id}")
            return events

        except RedisError as e:
            logger.error(f"Failed to get events for job {job_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting events for job {job_id}: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Redis connection health.

        Returns:
            Dictionary with health status information
        """
        if not self.client:
            return {
                "connected": False,
                "status": "disconnected",
                "error": "Client not initialized",
            }

        try:
            await self.client.ping()
            return {"connected": True, "status": "healthy"}
        except RedisError as e:
            return {"connected": False, "status": "unhealthy", "error": str(e)}


# Global Redis client instance
redis_client = RedisJobClient()
