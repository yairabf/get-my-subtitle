"""Tests for Redis job tracking client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from common.redis_client import RedisJobClient, redis_client
from common.schemas import SubtitleResponse, SubtitleStatus


class TestRedisJobClient:
    """Test RedisJobClient functionality."""
    
    @pytest.fixture
    def client(self):
        """Create a test Redis client."""
        client = RedisJobClient()
        return client
    
    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return SubtitleResponse(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            status=SubtitleStatus.PENDING
        )
    
    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful Redis connection."""
        with patch('common.redis_client.redis.from_url', new_callable=AsyncMock) as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_from_url.return_value = mock_redis
            
            await client.connect()
            
            assert client.connected is True
            assert client.client is not None
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, client):
        """Test Redis connection failure."""
        with patch('common.redis_client.redis.from_url', new_callable=AsyncMock) as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")
            
            await client.connect()
            
            assert client.connected is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test Redis disconnection."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        await client.disconnect()
        
        mock_redis.close.assert_called_once()
        assert client.connected is False
    
    def test_get_job_key(self, client):
        """Test job key generation."""
        job_id = uuid4()
        key = client._get_job_key(job_id)
        
        assert key == f"job:{str(job_id)}"
    
    def test_get_ttl_for_status_completed(self, client):
        """Test TTL for completed jobs."""
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_completed = 604800
            ttl = client._get_ttl_for_status(SubtitleStatus.COMPLETED)
            assert ttl == 604800
    
    def test_get_ttl_for_status_failed(self, client):
        """Test TTL for failed jobs."""
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_failed = 259200
            ttl = client._get_ttl_for_status(SubtitleStatus.FAILED)
            assert ttl == 259200
    
    def test_get_ttl_for_status_active(self, client):
        """Test TTL for active jobs."""
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_active = 0
            for status in [SubtitleStatus.PENDING, SubtitleStatus.DOWNLOADING, SubtitleStatus.TRANSLATING]:
                ttl = client._get_ttl_for_status(status)
                assert ttl == 0
    
    @pytest.mark.asyncio
    async def test_save_job_success(self, client, sample_job):
        """Test saving a job to Redis."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_active = 0
            
            result = await client.save_job(sample_job)
            
            assert result is True
            mock_redis.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_job_disconnected(self, client, sample_job):
        """Test saving a job when Redis is disconnected."""
        client.connected = False
        
        result = await client.save_job(sample_job)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_save_job_with_ttl(self, client, sample_job):
        """Test saving a completed job with TTL."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        sample_job.status = SubtitleStatus.COMPLETED
        
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_completed = 604800
            
            result = await client.save_job(sample_job)
            
            assert result is True
            mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_job_success(self, client, sample_job):
        """Test retrieving a job from Redis."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        # Mock Redis get to return serialized job
        job_json = sample_job.model_dump_json()
        mock_redis.get.return_value = job_json
        
        result = await client.get_job(sample_job.id)
        
        assert result is not None
        assert result.id == sample_job.id
        assert result.video_url == sample_job.video_url
    
    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client):
        """Test retrieving a non-existent job."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        mock_redis.get.return_value = None
        
        result = await client.get_job(uuid4())
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_job_disconnected(self, client):
        """Test retrieving a job when Redis is disconnected."""
        client.connected = False
        
        result = await client.get_job(uuid4())
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_job_status_success(self, client, sample_job):
        """Test updating job status."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        # Mock get_job to return the sample job
        job_json = sample_job.model_dump_json()
        mock_redis.get.return_value = job_json
        
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_active = 0
            
            result = await client.update_job_status(
                sample_job.id,
                SubtitleStatus.DOWNLOADING
            )
            
            assert result is True
            mock_redis.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_job_status_with_error_message(self, client, sample_job):
        """Test updating job status with error message."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        job_json = sample_job.model_dump_json()
        mock_redis.get.return_value = job_json
        
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_failed = 259200
            
            result = await client.update_job_status(
                sample_job.id,
                SubtitleStatus.FAILED,
                error_message="Test error"
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_job_status_with_download_url(self, client, sample_job):
        """Test updating job status with download URL."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        job_json = sample_job.model_dump_json()
        mock_redis.get.return_value = job_json
        
        with patch('common.redis_client.settings') as mock_settings:
            mock_settings.redis_job_ttl_completed = 604800
            
            result = await client.update_job_status(
                sample_job.id,
                SubtitleStatus.COMPLETED,
                download_url="https://example.com/subtitle.srt"
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_job_status_nonexistent_job(self, client):
        """Test updating status of non-existent job."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        mock_redis.get.return_value = None
        
        result = await client.update_job_status(
            uuid4(),
            SubtitleStatus.DOWNLOADING
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_jobs_success(self, client, sample_job):
        """Test listing all jobs."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        # Mock scan_iter to return job keys
        async def mock_scan_iter(match):
            yield f"job:{sample_job.id}"
        
        mock_redis.scan_iter = mock_scan_iter
        
        # Mock get to return job data
        job_json = sample_job.model_dump_json()
        mock_redis.get.return_value = job_json
        
        result = await client.list_jobs()
        
        assert len(result) == 1
        assert result[0].id == sample_job.id
    
    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, client, sample_job):
        """Test listing jobs filtered by status."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        sample_job.status = SubtitleStatus.COMPLETED
        
        async def mock_scan_iter(match):
            yield f"job:{sample_job.id}"
        
        mock_redis.scan_iter = mock_scan_iter
        job_json = sample_job.model_dump_json()
        mock_redis.get.return_value = job_json
        
        result = await client.list_jobs(status_filter=SubtitleStatus.COMPLETED)
        
        assert len(result) == 1
        assert result[0].status == SubtitleStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, client):
        """Test listing jobs when none exist."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        
        async def mock_scan_iter(match):
            return
            yield  # Make it a generator
        
        mock_redis.scan_iter = mock_scan_iter
        
        result = await client.list_jobs()
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_list_jobs_disconnected(self, client):
        """Test listing jobs when Redis is disconnected."""
        client.connected = False
        
        result = await client.list_jobs()
        
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_delete_job_success(self, client):
        """Test deleting a job."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        mock_redis.delete.return_value = 1
        
        result = await client.delete_job(uuid4())
        
        assert result is True
        mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_job_not_found(self, client):
        """Test deleting a non-existent job."""
        mock_redis = AsyncMock()
        client.client = mock_redis
        client.connected = True
        mock_redis.delete.return_value = 0
        
        result = await client.delete_job(uuid4())
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_job_disconnected(self, client):
        """Test deleting a job when Redis is disconnected."""
        client.connected = False
        
        result = await client.delete_job(uuid4())
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client):
        """Test health check when Redis is healthy."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        client.client = mock_redis
        
        result = await client.health_check()
        
        assert result["connected"] is True
        assert result["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client):
        """Test health check when Redis is unhealthy."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection lost"))
        client.client = mock_redis
        
        result = await client.health_check()
        
        assert result["connected"] is False
        assert result["status"] == "unhealthy"
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_health_check_no_client(self, client):
        """Test health check when client is not initialized."""
        client.client = None
        
        result = await client.health_check()
        
        assert result["connected"] is False
        assert result["status"] == "disconnected"

