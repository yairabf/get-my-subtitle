"""Tests for Manager health check functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manager.health import (
    check_event_consumer_health,
    check_event_publisher_health,
    check_health,
    check_orchestrator_health,
    check_redis_connection_health,
)


@pytest.mark.unit
class TestCheckOrchestratorHealth:
    """Test check_orchestrator_health function."""

    @pytest.mark.asyncio
    async def test_returns_health_details_when_healthy(self):
        """Test that function returns health details when orchestrator is healthy."""
        with patch("manager.health.orchestrator") as mock_orchestrator:
            mock_orchestrator.is_healthy = AsyncMock(return_value=True)
            mock_orchestrator.connection = MagicMock()
            mock_orchestrator.connection.is_closed = False
            mock_orchestrator.channel = MagicMock()
            mock_orchestrator.download_queue_name = "subtitle.download"
            mock_orchestrator.translation_queue_name = "subtitle.translation"

            result = await check_orchestrator_health()

            assert result["is_healthy"] is True
            assert result["has_connection"] is True
            assert result["connection_open"] is True
            assert result["has_channel"] is True
            assert result["download_queue"] == "subtitle.download"
            assert result["translation_queue"] == "subtitle.translation"

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_connection_closed(self):
        """Test that function returns unhealthy when connection is closed."""
        with patch("manager.health.orchestrator") as mock_orchestrator:
            mock_orchestrator.is_healthy = AsyncMock(return_value=False)
            mock_orchestrator.connection = MagicMock()
            mock_orchestrator.connection.is_closed = True
            mock_orchestrator.channel = None
            mock_orchestrator.download_queue_name = "subtitle.download"
            mock_orchestrator.translation_queue_name = "subtitle.translation"

            result = await check_orchestrator_health()

            assert result["is_healthy"] is False
            assert result["connection_open"] is False


@pytest.mark.unit
class TestCheckEventConsumerHealth:
    """Test check_event_consumer_health function."""

    @pytest.mark.asyncio
    async def test_returns_health_details_when_healthy_and_consuming(self):
        """Test that function returns health details when consumer is healthy."""
        with patch("manager.health.event_consumer") as mock_consumer:
            mock_consumer.is_healthy = AsyncMock(return_value=True)
            mock_consumer.is_consuming = True
            mock_consumer.connection = MagicMock()
            mock_consumer.connection.is_closed = False
            mock_consumer.channel = MagicMock()
            mock_consumer.exchange = MagicMock()
            mock_consumer.queue = MagicMock()
            mock_consumer.queue_name = "manager.subtitle.requests"
            mock_consumer.routing_key = "subtitle.requested"

            result = await check_event_consumer_health()

            assert result["is_healthy"] is True
            assert result["is_consuming"] is True
            assert result["has_connection"] is True
            assert result["connection_open"] is True
            assert result["has_channel"] is True
            assert result["has_exchange"] is True
            assert result["has_queue"] is True
            assert result["queue_name"] == "manager.subtitle.requests"
            assert result["routing_key"] == "subtitle.requested"

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_not_consuming(self):
        """Test that function returns unhealthy when not consuming."""
        with patch("manager.health.event_consumer") as mock_consumer:
            mock_consumer.is_healthy = AsyncMock(return_value=False)
            mock_consumer.is_consuming = False
            mock_consumer.connection = None

            result = await check_event_consumer_health()

            assert result["is_healthy"] is False
            assert result["is_consuming"] is False


@pytest.mark.unit
class TestCheckEventPublisherHealth:
    """Test check_event_publisher_health function."""

    @pytest.mark.asyncio
    async def test_returns_health_details_when_healthy(self):
        """Test that function returns health details when publisher is healthy."""
        with patch("manager.health.event_publisher") as mock_publisher:
            mock_publisher.is_healthy = AsyncMock(return_value=True)
            mock_publisher.connection = MagicMock()
            mock_publisher.connection.is_closed = False
            mock_publisher.channel = MagicMock()
            mock_publisher.exchange = MagicMock()
            mock_publisher.exchange_name = "subtitle.events"

            result = await check_event_publisher_health()

            assert result["is_healthy"] is True
            assert result["has_connection"] is True
            assert result["connection_open"] is True
            assert result["has_channel"] is True
            assert result["has_exchange"] is True
            assert result["exchange_name"] == "subtitle.events"


@pytest.mark.unit
class TestCheckRedisConnectionHealth:
    """Test check_redis_connection_health function."""

    @pytest.mark.asyncio
    async def test_returns_healthy_when_connected_and_ping_succeeds(self):
        """Test that function returns healthy when Redis is connected and ping succeeds."""
        with patch("manager.health.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.client = MagicMock()
            mock_redis.client.ping = AsyncMock()

            is_healthy, details = await check_redis_connection_health()

            assert is_healthy is True
            assert details["status"] == "connected"

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_ping_fails(self):
        """Test that function returns unhealthy when ping fails."""
        with patch("manager.health.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=True)
            mock_redis.client = MagicMock()
            mock_redis.client.ping = AsyncMock(side_effect=Exception("Connection error"))

            is_healthy, details = await check_redis_connection_health()

            assert is_healthy is False
            assert details["status"] == "error"
            assert "error" in details

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_not_connected(self):
        """Test that function returns unhealthy when Redis is not connected."""
        with patch("manager.health.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(return_value=False)
            mock_redis.client = None

            is_healthy, details = await check_redis_connection_health()

            assert is_healthy is False
            assert details["status"] == "not_connected"

    @pytest.mark.asyncio
    async def test_handles_exception_during_health_check(self):
        """Test that function handles exceptions during health check."""
        with patch("manager.health.redis_client") as mock_redis:
            mock_redis.ensure_connected = AsyncMock(side_effect=Exception("Unexpected error"))

            is_healthy, details = await check_redis_connection_health()

            assert is_healthy is False
            assert details["status"] == "error"
            assert "error" in details


@pytest.mark.unit
class TestCheckHealth:
    """Test comprehensive check_health function."""

    @pytest.mark.asyncio
    async def test_returns_healthy_when_all_components_healthy(self):
        """Test that function returns healthy status when all components are healthy."""
        with patch("manager.health.check_orchestrator_health") as mock_orch, patch(
            "manager.health.check_event_consumer_health"
        ) as mock_consumer, patch(
            "manager.health.check_event_publisher_health"
        ) as mock_publisher, patch(
            "manager.health.check_redis_connection_health"
        ) as mock_redis:
            mock_orch.return_value = {"is_healthy": True}
            mock_consumer.return_value = {
                "is_healthy": True,
                "has_connection": True,
                "connection_open": True,
                "is_consuming": True,
            }
            mock_publisher.return_value = {"is_healthy": True}
            mock_redis.return_value = (True, {"status": "connected"})

            result = await check_health()

            assert result["status"] == "healthy"
            assert all(result["checks"].values())

    @pytest.mark.asyncio
    async def test_returns_unhealthy_when_some_components_unhealthy(self):
        """Test that function returns unhealthy status when some components are unhealthy."""
        with patch("manager.health.check_orchestrator_health") as mock_orch, patch(
            "manager.health.check_event_consumer_health"
        ) as mock_consumer, patch(
            "manager.health.check_event_publisher_health"
        ) as mock_publisher, patch(
            "manager.health.check_redis_connection_health"
        ) as mock_redis:
            mock_orch.return_value = {"is_healthy": True}
            mock_consumer.return_value = {
                "is_healthy": True,
                "has_connection": True,
                "connection_open": True,
                "is_consuming": True,
            }
            mock_publisher.return_value = {"is_healthy": True}
            mock_redis.return_value = (False, {"status": "not_connected"})

            result = await check_health()

            assert result["status"] == "unhealthy"
            assert not result["checks"]["redis_connected"]

    @pytest.mark.asyncio
    async def test_returns_error_status_on_exception(self):
        """Test that function returns error status when exception occurs."""
        with patch("manager.health.check_orchestrator_health") as mock_orch:
            mock_orch.side_effect = Exception("Unexpected error")

            result = await check_health()

            assert result["status"] == "error"
            assert "error" in result
            assert result["checks"] == {}
            assert result["details"] == {}

    @pytest.mark.asyncio
    async def test_includes_all_component_details(self):
        """Test that function includes details for all components."""
        with patch("manager.health.check_orchestrator_health") as mock_orch, patch(
            "manager.health.check_event_consumer_health"
        ) as mock_consumer, patch(
            "manager.health.check_event_publisher_health"
        ) as mock_publisher, patch(
            "manager.health.check_redis_connection_health"
        ) as mock_redis:
            mock_orch.return_value = {"is_healthy": True, "test": "orchestrator"}
            mock_consumer.return_value = {
                "is_healthy": True,
                "has_connection": True,
                "connection_open": True,
                "is_consuming": True,
                "test": "consumer",
            }
            mock_publisher.return_value = {"is_healthy": True, "test": "publisher"}
            mock_redis.return_value = (True, {"status": "connected", "test": "redis"})

            result = await check_health()

            assert "orchestrator" in result["details"]
            assert "event_consumer" in result["details"]
            assert "event_publisher" in result["details"]
            assert "redis" in result["details"]

