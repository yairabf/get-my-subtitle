"""Utility functions for connection health checking and reconnection logging."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def check_and_log_reconnection(
    ensure_connected_func,
    connection_name: str,
    worker_name: Optional[str] = None,
    check_before_func=None,
) -> bool:
    """
    Check connection health and log reconnection success if applicable.

    This utility detects when a connection is lost, attempts reconnection via the
    provided ensure_connected function, and logs the outcome with consistent messaging.
    Includes comprehensive exception handling to prevent crashes in health check loops.

    Note: The ensure_connected_func is expected to internally handle reconnection,
    so we only need to call it once. We track the connection state before calling
    to determine if reconnection occurred.

    Args:
        ensure_connected_func: Async function that ensures connection (e.g., redis_client.ensure_connected)
        connection_name: Name of the connection for logging (e.g., "Redis", "Event Publisher")
        worker_name: Optional worker name for context (e.g., "translator", "downloader")
        check_before_func: Optional function to check connection state before ensure_connected
                          (e.g., lambda: redis_client.connected)

    Returns:
        True if connected, False otherwise

    Example:
        >>> await check_and_log_reconnection(
        ...     redis_client.ensure_connected,
        ...     "Redis",
        ...     "translator",
        ...     lambda: redis_client.connected
        ... )
    """
    context = f" ({worker_name} worker)" if worker_name else ""

    try:
        # Check if connection was healthy before calling ensure_connected
        was_connected_before = True
        if check_before_func:
            try:
                was_connected_before = check_before_func()
            except Exception:
                was_connected_before = False

        # Call ensure_connected which handles reconnection internally
        try:
            is_connected = await ensure_connected_func()
        except Exception as e:
            logger.error(f"Error ensuring {connection_name} connection{context}: {e}")
            return False

        # If connection succeeded and it was disconnected before, log success
        if is_connected and not was_connected_before:
            logger.info(f"✅ {connection_name} reconnected successfully{context}!")
        elif not is_connected:
            logger.warning(f"⚠️ {connection_name} connection check failed{context}")
        # Note: If was already connected and still connected, we don't log (normal case)

        return is_connected

    except Exception as e:
        logger.error(f"Error checking {connection_name} connection{context}: {e}")
        return False
