"""Tests for the downloader worker."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from downloader.worker import process_message
from common.schemas import SubtitleStatus


class TestDownloaderWorker:
    """Test downloader worker functionality."""
    
    @pytest.mark.asyncio
    async def test_process_message_success(self):
        """Test processing a message successfully."""
        request_id = uuid4()
        
        # Create mock message
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "request_id": str(request_id),
            "video_url": "https://example.com/video.mp4",
            "video_title": "Test Video",
            "language": "en"
        }).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None
        
        with patch('downloader.worker.redis_client') as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=True)
            
            await process_message(mock_message)
            
            # Verify job status was updated to COMPLETED
            mock_redis.update_job_status.assert_called_once()
            call_args = mock_redis.update_job_status.call_args
            assert call_args[0][0] == request_id
            assert call_args[0][1] == SubtitleStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_process_message_json_decode_error(self):
        """Test processing a message with invalid JSON."""
        # Create mock message with invalid JSON
        mock_message = MagicMock()
        mock_message.body = b"invalid json"
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None
        
        with patch('downloader.worker.redis_client') as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=True)
            
            # Should not raise exception
            await process_message(mock_message)
            
            # Redis update should not be called (no request_id)
            mock_redis.update_job_status.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_message_redis_unavailable(self):
        """Test processing when Redis is unavailable."""
        request_id = uuid4()
        
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "request_id": str(request_id),
            "video_url": "https://example.com/video.mp4"
        }).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None
        
        with patch('downloader.worker.redis_client') as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=False)
            
            # Should not raise exception even if Redis update fails
            await process_message(mock_message)
            
            mock_redis.update_job_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_processing_error(self):
        """Test handling of processing errors."""
        request_id = uuid4()
        
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "request_id": str(request_id)
        }).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None
        
        with patch('downloader.worker.redis_client') as mock_redis:
            # Simulate an error during processing
            mock_redis.update_job_status = AsyncMock(side_effect=Exception("Processing error"))
            
            # Should handle exception gracefully
            await process_message(mock_message)


class TestWorkerIntegration:
    """Test worker integration with Redis."""
    
    @pytest.mark.asyncio
    async def test_worker_updates_job_status(self):
        """Test that worker updates job status in Redis."""
        request_id = uuid4()
        
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "request_id": str(request_id),
            "video_url": "https://example.com/video.mp4",
            "video_title": "Test Video",
            "language": "en",
            "preferred_sources": ["opensubtitles"]
        }).encode()
        mock_message.routing_key = "subtitle.download"
        mock_message.exchange = ""
        mock_message.message_id = "test-message-id"
        mock_message.timestamp = None
        
        with patch('downloader.worker.redis_client') as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=True)
            
            await process_message(mock_message)
            
            # Verify the update was called with correct parameters
            assert mock_redis.update_job_status.called
            call_args = mock_redis.update_job_status.call_args
            assert call_args[0][1] == SubtitleStatus.COMPLETED
            assert call_args[1].get('download_url') is not None
