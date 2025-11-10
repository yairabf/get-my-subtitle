"""Scanner worker for monitoring media files and triggering subtitle processing."""

import asyncio
import signal
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logging_config import setup_service_logging
from scanner.scanner import MediaScanner

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
        asyncio.create_task(scanner.disconnect())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Connect to services
        await scanner.connect()

        # Start file system watcher
        scanner.start()

        # Keep running until stopped
        logger.info("🚀 Scanner service running. Press Ctrl+C to stop.")
        while scanner.is_running():
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        scanner.stop()
        await scanner.disconnect()
        logger.info("👋 Scanner service stopped")


if __name__ == "__main__":
    asyncio.run(main())
