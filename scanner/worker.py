"""Scanner worker for monitoring media files and triggering subtitle processing."""

import asyncio
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import settings  # noqa: E402
from common.logging_config import setup_service_logging  # noqa: E402
from scanner.scanner import MediaScanner  # noqa: E402

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger


async def main() -> None:
    """Main entry point for the scanner service."""
    scanner = MediaScanner()

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        scanner.stop()
        # Schedule async cleanup
        asyncio.create_task(scanner.stop_webhook_server())
        asyncio.create_task(scanner.disconnect())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Connect to services
        await scanner.connect()

        # Start file system watcher
        scanner.start()

        # Start webhook server
        await scanner.start_webhook_server()

        # Start fallback sync
        await scanner.start_fallback_sync()

        # Keep running until stopped
        logger.info("🚀 Scanner service running. Press Ctrl+C to stop.")
        logger.info("   - File system watcher: active")
        logger.info("   - Webhook server: active")
        logger.info(
            f"   - WebSocket client: {'connected' if scanner.websocket_client.is_connected() else 'disconnected'}"
        )
        logger.info(
            f"   - Fallback sync: {'enabled' if settings.jellyfin_fallback_sync_enabled else 'disabled'}"
        )
        while scanner.is_running():
            await asyncio.sleep(1)

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
