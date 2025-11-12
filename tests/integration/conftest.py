"""Pytest fixtures for integration tests using pytest-docker."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

import aio_pika
import pytest
import pytest_asyncio

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


def is_rabbitmq_responsive(url: str) -> bool:
    """Check if RabbitMQ is responsive by attempting a connection."""
    try:
        import socket
        from urllib.parse import urlparse

        # Parse URL to get host and port
        parsed = urlparse(url.replace("amqp://", "http://"))
        host = parsed.hostname or "localhost"
        port = parsed.port or 5672

        # Try to connect to the AMQP port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def is_redis_responsive(url: str) -> bool:
    """Check if Redis is responsive by attempting a ping."""
    try:
        import redis

        # Parse URL to get host and port
        if url.startswith("redis://"):
            url = url[8:]
        if "@" in url:
            url = url.split("@")[1]
        if "/" in url:
            url = url.split("/")[0]
        if ":" in url:
            host, port = url.split(":")
            port = int(port)
        else:
            host = url
            port = 6379

        r = redis.Redis(host=host, port=port, socket_connect_timeout=1)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Specify docker-compose file for tests."""
    return os.path.join(
        str(pytestconfig.rootdir), "tests", "integration", "docker-compose.yml"
    )


@pytest.fixture(scope="session")
def docker_compose_project_name():
    """Use a consistent project name for Docker Compose."""
    return "get-my-subtitle-integration-tests"


@pytest.fixture(scope="session")
def rabbitmq_service(docker_ip, docker_services):
    """Ensure RabbitMQ is up and responsive."""
    port = docker_services.port_for("rabbitmq", 5672)
    url = f"amqp://guest:guest@{docker_ip}:{port}/"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_rabbitmq_responsive(url)
    )
    return url


@pytest.fixture(scope="session")
def redis_service(docker_ip, docker_services):
    """Ensure Redis is up and responsive."""
    port = docker_services.port_for("redis", 6379)
    url = f"redis://{docker_ip}:{port}"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_redis_responsive(url)
    )
    return url


@pytest.fixture(scope="session", autouse=True)
def setup_environment_variables(rabbitmq_service, redis_service):
    """Set environment variables for service URLs before importing modules."""
    os.environ["RABBITMQ_URL"] = rabbitmq_service
    os.environ["REDIS_URL"] = redis_service

    # Force reload of modules that use these environment variables
    for module in modules_to_reload:
        if module in sys.modules:
            del sys.modules[module]

    yield

    # Cleanup (optional - pytest-docker handles container cleanup)
    if "RABBITMQ_URL" in os.environ:
        del os.environ["RABBITMQ_URL"]
    if "REDIS_URL" in os.environ:
        del os.environ["REDIS_URL"]


@pytest.fixture(scope="session")
def rabbitmq_container(rabbitmq_service):
    """Backward compatibility fixture - returns connection info dict."""
    # Parse URL to extract components
    url = rabbitmq_service
    if url.startswith("amqp://"):
        url = url[7:]
    if "@" in url:
        auth, rest = url.split("@")
        user, password = auth.split(":")
        host_port = rest.split("/")[0]
    else:
        host_port = url.split("/")[0]
    host, port = host_port.split(":")

    return {
        "host": host,
        "port": int(port),
        "url": rabbitmq_service,
    }


@pytest_asyncio.fixture
async def rabbitmq_connection(rabbitmq_service):
    """Create a RabbitMQ connection for testing."""
    connection = await aio_pika.connect_robust(rabbitmq_service)
    yield connection
    await connection.close()


@pytest_asyncio.fixture
async def rabbitmq_channel(rabbitmq_connection):
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
async def test_orchestrator(rabbitmq_service, clean_queues, fake_redis_job_client):
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
    rabbitmq_service, clean_queues, mock_redis_client
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
async def test_event_publisher(rabbitmq_service, clean_exchange):
    """Create EventPublisher instance for testing."""
    publisher = EventPublisher()

    # Connect to RabbitMQ (using env var set at module level)
    await publisher.connect()

    yield publisher

    # Disconnect
    await publisher.disconnect()
