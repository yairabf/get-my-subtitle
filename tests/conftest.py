"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import aio_pika
import fakeredis.aioredis
import pytest
import pytest_asyncio

# Add src directory to Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from common.redis_client import RedisJobClient
from common.schemas import SubtitleRequest, SubtitleResponse, SubtitleStatus


@pytest_asyncio.fixture
async def fake_redis_client():
    """
    Fake Redis client using fakeredis for realistic Redis behavior.

    This provides a real Redis-like interface without requiring a Redis server.
    Perfect for unit tests that need Redis functionality without Docker.
    """
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True, encoding="utf-8")
    yield fake_redis
    await fake_redis.flushall()
    await fake_redis.aclose()


@pytest_asyncio.fixture
async def fake_redis_job_client(fake_redis_client):
    """
    RedisJobClient instance using fakeredis for testing.

    This provides a fully functional RedisJobClient with realistic Redis behavior
    for unit testing without external dependencies.
    """
    client = RedisJobClient()
    # Replace the client's Redis connection with our fake one
    client.client = fake_redis_client
    client.connected = True
    yield client
    # Cleanup
    await fake_redis_client.flushall()
    client.connected = False


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis client for testing (simple AsyncMock)."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.exists = AsyncMock(return_value=False)
    mock.expire = AsyncMock(return_value=True)
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    mock.flushall = AsyncMock()
    mock.aclose = AsyncMock()

    # Mock scan_iter for listing jobs
    async def mock_scan_iter(match):
        return
        yield  # Make it a generator

    mock.scan_iter = mock_scan_iter

    return mock


@pytest.fixture
def mock_rabbitmq_connection():
    """Mock RabbitMQ connection for testing."""
    mock_connection = AsyncMock(spec=aio_pika.abc.AbstractConnection)
    mock_connection.is_closed = False
    mock_connection.close = AsyncMock()
    return mock_connection


@pytest.fixture
def mock_rabbitmq_channel():
    """Mock RabbitMQ channel for testing."""
    mock_channel = AsyncMock(spec=aio_pika.abc.AbstractChannel)

    # Mock queue declaration
    mock_queue = AsyncMock(spec=aio_pika.abc.AbstractQueue)
    mock_queue.declaration_result = MagicMock()
    mock_queue.declaration_result.message_count = 0
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

    # Mock exchange declaration
    mock_exchange = AsyncMock(spec=aio_pika.abc.AbstractExchange)
    mock_exchange.publish = AsyncMock()
    mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

    # Mock default exchange
    mock_channel.default_exchange = mock_exchange

    mock_channel.close = AsyncMock()

    return mock_channel


@pytest.fixture
def mock_rabbitmq_exchange():
    """Mock RabbitMQ exchange for testing."""
    mock_exchange = AsyncMock(spec=aio_pika.abc.AbstractExchange)
    mock_exchange.publish = AsyncMock()
    return mock_exchange


@pytest_asyncio.fixture
async def mock_rabbitmq(mock_rabbitmq_connection, mock_rabbitmq_channel):
    """Complete mock RabbitMQ setup for testing."""
    mock_rabbitmq_connection.channel = AsyncMock(return_value=mock_rabbitmq_channel)
    return mock_rabbitmq_connection


@pytest.fixture
def mock_event_publisher():
    """Mock EventPublisher for testing."""
    mock_publisher = AsyncMock()
    mock_publisher.connect = AsyncMock()
    mock_publisher.disconnect = AsyncMock()
    mock_publisher.publish_event = AsyncMock(return_value=True)
    mock_publisher.connection = None
    mock_publisher.channel = None
    mock_publisher.exchange = None
    return mock_publisher


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
def sample_subtitle_request_obj():
    """Sample SubtitleRequest object for testing."""
    return SubtitleRequest(
        video_url="https://example.com/video.mp4",
        video_title="Sample Video",
        language="en",
        target_language="es",
        preferred_sources=["opensubtitles"],
    )


@pytest.fixture
def sample_subtitle_response():
    """Sample SubtitleResponse object for testing."""
    return SubtitleResponse(
        id=uuid4(),
        video_url="https://example.com/video.mp4",
        video_title="Sample Video",
        language="en",
        target_language="es",
        status=SubtitleStatus.PENDING,
    )


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


@pytest.fixture
def sample_job_id():
    """Generate a sample UUID for testing."""
    return uuid4()
