"""Health check endpoint for Manager service."""

import logging
from typing import Any, Dict

from common.event_publisher import event_publisher
from common.redis_client import redis_client
from manager.event_consumer import event_consumer
from manager.orchestrator import orchestrator

logger = logging.getLogger(__name__)


async def check_health() -> Dict[str, Any]:
    """
    Perform comprehensive health check of Manager service.

    Returns:
        Dictionary with health status and details
    """
    health_status = {
        "status": "healthy",
        "checks": {
            "orchestrator_connected": False,
            "event_consumer_connected": False,
            "event_consumer_consuming": False,
            "event_publisher_connected": False,
            "redis_connected": False,
        },
        "details": {},
    }

    try:
        # Check Orchestrator
        orchestrator_healthy = await orchestrator.is_healthy()
        health_status["checks"]["orchestrator_connected"] = orchestrator_healthy
        health_status["details"]["orchestrator"] = {
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

        # Check Event Consumer
        event_consumer_healthy = await event_consumer.is_healthy()
        health_status["checks"]["event_consumer_connected"] = (
            event_consumer.connection is not None
            and not event_consumer.connection.is_closed
        )
        health_status["checks"]["event_consumer_consuming"] = (
            event_consumer.is_consuming and event_consumer_healthy
        )
        health_status["details"]["event_consumer"] = {
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

        # Check Event Publisher
        event_publisher_healthy = await event_publisher.is_healthy()
        health_status["checks"]["event_publisher_connected"] = event_publisher_healthy
        health_status["details"]["event_publisher"] = {
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

        # Check Redis connection
        try:
            redis_healthy = await redis_client.ensure_connected()
            health_status["checks"]["redis_connected"] = redis_healthy
            
            if redis_healthy and redis_client.client:
                await redis_client.client.ping()
                health_status["details"]["redis"] = {"status": "connected"}
            else:
                health_status["details"]["redis"] = {"status": "not_connected"}
        except Exception as e:
            health_status["details"]["redis"] = {"status": "error", "error": str(e)}

        # Determine overall status
        all_checks_passed = all(health_status["checks"].values())
        if not all_checks_passed:
            health_status["status"] = "unhealthy"

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        health_status["status"] = "error"
        health_status["error"] = str(e)
        return health_status

