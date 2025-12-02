"""Scanner worker for monitoring media files and triggering subtitle processing."""

import asyncio
import signal
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings  # noqa: E402
from common.connection_utils import check_and_log_reconnection  # noqa: E402
from common.event_publisher import event_publisher  # noqa: E402
from common.logging_config import setup_service_logging  # noqa: E402
from common.redis_client import redis_client  # noqa: E402
from scanner.scanner import MediaScanner  # noqa: E402

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger


async def main() -> None:
    """Main entry point for the scanner service."""
    scanner = MediaScanner()
    shutdown_event = asyncio.Event()

    # Setup async signal handlers for graceful shutdown
    def signal_handler_sync(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler_sync)
    signal.signal(signal.SIGTERM, signal_handler_sync)

    try:
        # Connect to services
        await scanner.connect()

        # Start file system watcher
        scanner.start()

        # Start webhook server
        await scanner.start_webhook_server()

        # Start fallback sync
        await scanner.start_fallback_sync()

        # Keep running until stopped with periodic health checks
        logger.info("🚀 Scanner service running. Press Ctrl+C to stop.")
        logger.info("   - File system watcher: active")
        logger.info("   - Webhook server: active")
        logger.info(
            f"   - WebSocket client: {'connected' if scanner.websocket_client.is_connected() else 'disconnected'}"
        )
        logger.info(
            f"   - Fallback sync: {'enabled' if settings.jellyfin_fallback_sync_enabled else 'disabled'}"
        )
        
        health_check_interval = settings.redis_health_check_interval
        last_health_check = 0
        
        while scanner.is_running() and not shutdown_event.is_set():
            await asyncio.sleep(1)
            
            # Periodic health check
            current_time = asyncio.get_event_loop().time()
            if current_time - last_health_check > health_check_interval:
                # Check Redis connection
                await check_and_log_reconnection(
                    redis_client.ensure_connected,
                    "Redis",
                    "scanner"
                )
                
                # Check event publisher connection
                await check_and_log_reconnection(
                    event_publisher.ensure_connected,
                    "Event Publisher",
                    "scanner"
                )
                
                last_health_check = current_time

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        scanner.stop()
        await scanner.stop_webhook_server()
        await scanner.disconnect()
        logger.info("👋 Scanner service stopped")


if __name__ == "__main__":
    asyncio.run(main())
