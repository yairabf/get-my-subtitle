"""Health check endpoint for Consumer service."""

import asyncio
from typing import Any, Dict

from common.logging_config import setup_service_logging
from consumer.worker import EventConsumer

# Configure logging
service_logger = setup_service_logging("consumer", enable_file_logging=True)
logger = service_logger.logger

# Global consumer instance (set by worker.py)
_consumer_instance: EventConsumer = None


def set_consumer_instance(consumer: EventConsumer) -> None:
    """Set the global consumer instance for health checks."""
    global _consumer_instance
    _consumer_instance = consumer


async def check_health() -> Dict[str, Any]:
    """
    Perform comprehensive health check of Consumer service.

    Returns:
        Dictionary with health status and details
    """
    health_status = {
        "status": "healthy",
        "checks": {
            "consumer_connected": False,
            "consumer_consuming": False,
            "redis_connected": False,
            "rabbitmq_connected": False,
        },
        "details": {},
    }

    try:
        # Check Consumer instance
        if _consumer_instance:
            # Check if consumer is healthy
            is_healthy = await _consumer_instance.is_healthy()
            health_status["checks"]["consumer_connected"] = (
                _consumer_instance.connection is not None
                and not _consumer_instance.connection.is_closed
            )
            health_status["checks"]["consumer_consuming"] = (
                _consumer_instance.is_consuming and is_healthy
            )

            health_status["details"]["consumer"] = {
                "is_consuming": _consumer_instance.is_consuming,
                "has_connection": _consumer_instance.connection is not None,
                "connection_open": (
                    _consumer_instance.connection is not None
                    and not _consumer_instance.connection.is_closed
                ),
                "has_channel": _consumer_instance.channel is not None,
                "has_queue": _consumer_instance.queue is not None,
                "queue_name": _consumer_instance.queue_name,
            }
        else:
            health_status["details"]["consumer"] = {
                "error": "Consumer instance not set"
            }

        # Check Redis connection
        try:
            from common.redis_client import redis_client

            if redis_client.client:
                await redis_client.client.ping()
                health_status["checks"]["redis_connected"] = True
                health_status["details"]["redis"] = {"status": "connected"}
            else:
                health_status["details"]["redis"] = {"status": "not_connected"}
        except Exception as e:
            health_status["details"]["redis"] = {"status": "error", "error": str(e)}

        # Check RabbitMQ connection (via Consumer)
        if _consumer_instance and _consumer_instance.connection:
            try:
                if not _consumer_instance.connection.is_closed:
                    health_status["checks"]["rabbitmq_connected"] = True
                    health_status["details"]["rabbitmq"] = {"status": "connected"}
                else:
                    health_status["details"]["rabbitmq"] = {
                        "status": "connection_closed"
                    }
            except Exception as e:
                health_status["details"]["rabbitmq"] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            health_status["details"]["rabbitmq"] = {"status": "no_connection"}

        # Determine overall status
        all_checks_passed = all(health_status["checks"].values())
        if not all_checks_passed:
            health_status["status"] = "unhealthy"

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "error"
        health_status["error"] = str(e)
        return health_status
