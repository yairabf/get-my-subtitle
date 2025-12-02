"""Utility functions for connection health checking and reconnection logging."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def check_and_log_reconnection(
    ensure_connected_func,
    connection_name: str,
    worker_name: Optional[str] = None
) -> bool:
    """
    Check connection health and log reconnection success if applicable.
    
    This utility detects when a connection is lost, attempts reconnection via the
    provided ensure_connected function, and logs the outcome with consistent messaging.
    Includes comprehensive exception handling to prevent crashes in health check loops.
    
    Args:
        ensure_connected_func: Async function that ensures connection (e.g., redis_client.ensure_connected)
        connection_name: Name of the connection for logging (e.g., "Redis", "Event Publisher")
        worker_name: Optional worker name for context (e.g., "translator", "downloader")
        
    Returns:
        True if connected, False otherwise
        
    Example:
        >>> await check_and_log_reconnection(
        ...     redis_client.ensure_connected,
        ...     "Redis",
        ...     "translator"
        ... )
    """
    context = f" in {worker_name}" if worker_name else ""
    
    try:
        # First check: detect if connection is lost
        was_disconnected = not await ensure_connected_func()
        
        if was_disconnected:
            # Log warning about disconnection
            logger.warning(f"{connection_name} connection lost{context}, attempting reconnection...")
            
            try:
                # Second check: verify if reconnection succeeded
                if await ensure_connected_func():
                    logger.info(f"✅ {connection_name} reconnection successful{context}")
                    return True
                
                return False
                
            except Exception as e:
                logger.warning(f"{connection_name} reconnection check failed{context}: {e}")
                return False
        
        # Was already connected
        return True
        
    except Exception as e:
        logger.error(f"Error checking {connection_name} connection{context}: {e}")
        return False
