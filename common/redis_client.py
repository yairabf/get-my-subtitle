"""Redis client for job tracking across all services."""

import json
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from common.config import settings
from common.schemas import SubtitleResponse, SubtitleStatus

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
                max_connections=10
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
        """Generate Redis key for a job."""
        return f"job:{str(job_id)}"
    
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
            job_data = job.model_dump(mode='json')
            
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
        download_url: Optional[str] = None
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
            
            # Import datetime for updated_at
            from datetime import datetime
            job.updated_at = datetime.utcnow()
            
            # Save updated job
            success = await self.save_job(job)
            
            if success:
                logger.info(f"Updated job {job_id} status to {status.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False
    
    async def list_jobs(self, status_filter: Optional[SubtitleStatus] = None) -> List[SubtitleResponse]:
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
                "error": "Client not initialized"
            }
        
        try:
            await self.client.ping()
            return {
                "connected": True,
                "status": "healthy"
            }
        except RedisError as e:
            return {
                "connected": False,
                "status": "unhealthy",
                "error": str(e)
            }


# Global Redis client instance
redis_client = RedisJobClient()

