"""Pytest fixtures for integration tests."""

import asyncio
import os
import subprocess
import sys
import time
from unittest.mock import AsyncMock, patch

import aio_pika
import pytest
import pytest_asyncio

# Set environment variables BEFORE importing modules
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"
os.environ["REDIS_URL"] = "redis://localhost:6379"

# Remove cached modules to force reload with new env vars
modules_to_reload = [
    "common.config",
    "common.event_publisher",
    "manager.orchestrator",
]
for module in modules_to_reload:
    if module in sys.modules:
        del sys.modules[module]

from common.event_publisher import EventPublisher
from manager.orchestrator import SubtitleOrchestrator


@pytest.fixture(scope="session")
def rabbitmq_container():
    """Start RabbitMQ container for integration tests."""
    # Check if RabbitMQ is already running via docker-compose
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=rabbitmq", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )

    rabbitmq_already_running = "rabbitmq" in result.stdout

    if not rabbitmq_already_running:
        # Start RabbitMQ using docker-compose
        subprocess.run(
            ["docker-compose", "up", "-d", "rabbitmq"],
            check=True,
            cwd="/Users/yairabramovitch/Documents/workspace/get-my-subtitle",
        )

        # Wait for RabbitMQ to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "get-my-subtitle-rabbitmq-1",
                        "rabbitmq-diagnostics",
                        "ping",
                    ],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    print("\n✓ RabbitMQ is ready")
                    break
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                pass

            if i < max_retries - 1:
                time.sleep(1)
        else:
            raise RuntimeError("RabbitMQ failed to start within timeout")
    else:
        print("\n✓ RabbitMQ already running")

    yield {
        "host": "localhost",
        "port": 5672,
        "url": "amqp://guest:guest@localhost:5672/",
    }

    # Cleanup: Only stop if we started it
    if not rabbitmq_already_running:
        subprocess.run(
            ["docker-compose", "down", "rabbitmq"],
            cwd="/Users/yairabramovitch/Documents/workspace/get-my-subtitle",
        )


@pytest_asyncio.fixture
async def rabbitmq_connection(
    rabbitmq_container,
):
    """Create a RabbitMQ connection for testing."""
    connection = await aio_pika.connect_robust(rabbitmq_container["url"])
    yield connection
    await connection.close()


@pytest_asyncio.fixture
async def rabbitmq_channel(
    rabbitmq_connection,
):
    """Create a RabbitMQ channel for testing."""
    channel = await rabbitmq_connection.channel()
    yield channel
    await channel.close()


@pytest_asyncio.fixture
async def clean_queues(rabbitmq_channel):
    """Clean all test queues before and after tests."""
    queue_names = ["subtitle.download", "subtitle.translation"]

    # Purge queues before test
    for queue_name in queue_names:
        try:
            queue = await rabbitmq_channel.declare_queue(queue_name, durable=True)
            await queue.purge()
        except Exception:
            pass  # Queue might not exist yet

    yield

    # Purge queues after test
    for queue_name in queue_names:
        try:
            queue = await rabbitmq_channel.declare_queue(queue_name, durable=True)
            await queue.purge()
        except Exception:
            pass


@pytest_asyncio.fixture
async def clean_exchange(rabbitmq_channel):
    """Clean test exchange before and after tests."""
    exchange_name = "subtitle.events"

    # Delete and recreate exchange before test
    try:
        await rabbitmq_channel.exchange_delete(exchange_name)
    except Exception:
        pass  # Exchange might not exist

    yield

    # Delete exchange after test
    try:
        await rabbitmq_channel.exchange_delete(exchange_name)
    except Exception:
        pass


@pytest_asyncio.fixture
async def fake_redis_client():
    """
    Fake Redis client using fakeredis for realistic behavior in integration tests.

    This provides a real Redis-like interface without requiring a separate Redis server,
    making integration tests more realistic while still being isolated.
    """
    import fakeredis.aioredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True, encoding="utf-8")
    yield fake_redis
    await fake_redis.flushall()
    await fake_redis.aclose()


@pytest_asyncio.fixture
async def fake_redis_job_client(fake_redis_client):
    """
    RedisJobClient instance using fakeredis for integration testing.

    This provides realistic Redis behavior for integration tests without
    requiring a real Redis instance, allowing tests to focus on RabbitMQ integration.
    """
    from common.redis_client import RedisJobClient

    client = RedisJobClient()
    # Replace the client's Redis connection with our fake one
    client.client = fake_redis_client
    client.connected = True
    yield client
    # Cleanup
    await fake_redis_client.flushall()
    client.connected = False


@pytest.fixture
def mock_redis_client():
    """
    Simple mock Redis client for backward compatibility.

    Use fake_redis_job_client for more realistic testing.
    """
    mock_redis = AsyncMock()
    mock_redis.connect = AsyncMock()
    mock_redis.disconnect = AsyncMock()
    mock_redis.save_job = AsyncMock(return_value=True)
    mock_redis.update_phase = AsyncMock(return_value=True)
    mock_redis.get_job = AsyncMock(return_value=None)
    mock_redis.health_check = AsyncMock(return_value={"status": "healthy"})
    return mock_redis


@pytest_asyncio.fixture
async def test_orchestrator(rabbitmq_container, clean_queues, fake_redis_job_client):
    """
    Create SubtitleOrchestrator instance for testing with realistic Redis behavior.

    Uses fakeredis for more realistic Redis behavior while keeping RabbitMQ integration focus.
    """
    orchestrator = SubtitleOrchestrator()

    # Patch Redis client with fakeredis for realistic behavior
    with patch("manager.orchestrator.redis_client", fake_redis_job_client):
        # Connect to RabbitMQ
        await orchestrator.connect()

        yield orchestrator

        # Disconnect
        await orchestrator.disconnect()


@pytest_asyncio.fixture
async def test_orchestrator_with_mock_redis(
    rabbitmq_container, clean_queues, mock_redis_client
):
    """
    Create SubtitleOrchestrator instance with simple mock Redis (backward compatibility).

    Use test_orchestrator for more realistic testing.
    """
    orchestrator = SubtitleOrchestrator()

    # Patch Redis client with simple mock
    with patch("manager.orchestrator.redis_client", mock_redis_client):
        # Connect to RabbitMQ
        await orchestrator.connect()

        yield orchestrator

        # Disconnect
        await orchestrator.disconnect()


@pytest_asyncio.fixture
async def test_event_publisher(rabbitmq_container, clean_exchange):
    """Create EventPublisher instance for testing."""
    publisher = EventPublisher()

    # Connect to RabbitMQ (using env var set at module level)
    await publisher.connect()

    yield publisher

    # Disconnect
    await publisher.disconnect()
