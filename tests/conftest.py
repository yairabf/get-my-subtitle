"""Pytest configuration and shared fixtures."""

import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=False)
    mock.expire = AsyncMock(return_value=True)
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()

    # Mock scan_iter for listing jobs
    async def mock_scan_iter(match):
        return
        yield  # Make it a generator

    mock.scan_iter = mock_scan_iter

    return mock


@pytest.fixture
async def mock_rabbitmq():
    """Mock RabbitMQ connection for testing."""
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_queue = AsyncMock()
    mock_channel.consume = AsyncMock()
    return mock_connection


@pytest.fixture
def sample_subtitle_request():
    """Sample subtitle request data for testing."""
    return {
        "video_url": "https://example.com/video.mp4",
        "video_title": "Sample Video",
        "language": "en",
        "target_language": "es",
        "preferred_sources": ["opensubtitles"],
    }


@pytest.fixture
def sample_subtitle_data():
    """Sample subtitle data for testing."""
    return {
        "id": "test-subtitle-123",
        "video_url": "https://example.com/video.mp4",
        "video_title": "Sample Video",
        "language": "en",
        "target_language": "es",
        "status": "processing",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
