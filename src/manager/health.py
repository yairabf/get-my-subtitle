"""Health check endpoint for Manager service."""

import logging
from typing import Any, Dict, Tuple

from common.event_publisher import event_publisher
from common.redis_client import redis_client
from manager.event_consumer import event_consumer
from manager.orchestrator import orchestrator

logger = logging.getLogger(__name__)


async def check_orchestrator_health() -> Dict[str, Any]:
    """
    Check orchestrator connection health.

    Returns dict with connection status and details.
    """
    orchestrator_healthy = await orchestrator.is_healthy()
    return {
        "is_healthy": orchestrator_healthy,
        "has_connection": orchestrator.connection is not None,
        "connection_open": (
            orchestrator.connection is not None
            and not orchestrator.connection.is_closed
        ),
        "has_channel": orchestrator.channel is not None,
        "download_queue": orchestrator.download_queue_name,
        "translation_queue": orchestrator.translation_queue_name,
    }


async def check_event_consumer_health() -> Dict[str, Any]:
    """
    Check event consumer health and consumption status.

    Returns dict with connection and consumption status.
    """
    event_consumer_healthy = await event_consumer.is_healthy()
    return {
        "is_healthy": event_consumer_healthy,
        "is_consuming": event_consumer.is_consuming,
        "has_connection": event_consumer.connection is not None,
        "connection_open": (
            event_consumer.connection is not None
            and not event_consumer.connection.is_closed
        ),
        "has_channel": event_consumer.channel is not None,
        "has_exchange": event_consumer.exchange is not None,
        "has_queue": event_consumer.queue is not None,
        "queue_name": event_consumer.queue_name,
        "routing_key": event_consumer.routing_key,
    }


async def check_event_publisher_health() -> Dict[str, Any]:
    """
    Check event publisher connection health.

    Returns dict with connection status and details.
    """
    event_publisher_healthy = await event_publisher.is_healthy()
    return {
        "is_healthy": event_publisher_healthy,
        "has_connection": event_publisher.connection is not None,
        "connection_open": (
            event_publisher.connection is not None
            and not event_publisher.connection.is_closed
        ),
        "has_channel": event_publisher.channel is not None,
        "has_exchange": event_publisher.exchange is not None,
        "exchange_name": event_publisher.exchange_name,
    }


async def check_redis_connection_health() -> Tuple[bool, Dict[str, Any]]:
    """
    Check Redis connection and ping responsiveness.

    Returns tuple of (is_healthy, details_dict).
    """
    try:
        redis_healthy = await redis_client.ensure_connected()

        if redis_healthy and redis_client.client:
            try:
                await redis_client.client.ping()
                return True, {"status": "connected"}
            except Exception as ping_error:
                return False, {
                    "status": "error",
                    "error": f"Ping failed: {ping_error}",
                }
        else:
            return False, {"status": "not_connected"}
    except Exception as e:
        return False, {"status": "error", "error": str(e)}


async def check_health() -> Dict[str, Any]:
    """
    Perform comprehensive health check of Manager service.

    Checks all external dependencies and returns aggregated status.

    Returns:
        Dictionary with overall status and individual component details
    """
    try:
        orchestrator_details = await check_orchestrator_health()
        event_consumer_details = await check_event_consumer_health()
        event_publisher_details = await check_event_publisher_health()
        redis_healthy, redis_details = await check_redis_connection_health()

        health_status = {
            "status": "healthy",
            "checks": {
                "orchestrator_connected": orchestrator_details["is_healthy"],
                "event_consumer_connected": (
                    event_consumer_details["has_connection"]
                    and event_consumer_details["connection_open"]
                ),
                "event_consumer_consuming": event_consumer_details["is_consuming"],
                "event_publisher_connected": event_publisher_details["is_healthy"],
                "redis_connected": redis_healthy,
            },
            "details": {
                "orchestrator": orchestrator_details,
                "event_consumer": event_consumer_details,
                "event_publisher": event_publisher_details,
                "redis": redis_details,
            },
        }

        # Determine overall status
        if not all(health_status["checks"].values()):
            health_status["status"] = "unhealthy"

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "checks": {},
            "details": {},
        }
