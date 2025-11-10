"""Media file scanner that monitors directory for new/updated files."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from watchdog.observers import Observer

from common.config import settings
from common.event_publisher import event_publisher
from common.logging_config import setup_service_logging
from common.redis_client import redis_client
from manager.orchestrator import orchestrator
from scanner.event_handler import MediaFileEventHandler
from scanner.webhook_handler import JellyfinWebhookHandler

# Configure logging
service_logger = setup_service_logging("scanner", enable_file_logging=True)
logger = service_logger.logger


class MediaScanner:
    """Media file scanner that monitors directory for new/updated files."""

    def __init__(self):
        """Initialize the media scanner."""
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[MediaFileEventHandler] = None
        self.running = False
        self.webhook_app: Optional[FastAPI] = None
        self.webhook_server_task: Optional[asyncio.Task] = None
        self.webhook_handler = JellyfinWebhookHandler()

    async def connect(self) -> None:
        """Connect to Redis, RabbitMQ, and orchestrator."""
        logger.info("🔌 Connecting to Redis...")
        await redis_client.connect()

        logger.info("🔌 Connecting to RabbitMQ...")
        await orchestrator.connect()

        logger.info("🔌 Connecting to event publisher...")
        await event_publisher.connect()

        logger.info("✅ All connections established")

    async def disconnect(self) -> None:
        """Disconnect from services."""
        logger.info("🔌 Disconnecting from services...")
        await orchestrator.disconnect()
        await event_publisher.disconnect()
        await redis_client.disconnect()
        logger.info("✅ All connections closed")

    def start(self) -> None:
        """Start the file system observer."""
        if self.running:
            logger.warning("Scanner is already running")
            return

        media_path = Path(settings.scanner_media_path)

        if not media_path.exists():
            logger.error(f"Media path does not exist: {media_path}")
            raise FileNotFoundError(f"Media path does not exist: {media_path}")

        if not media_path.is_dir():
            logger.error(f"Media path is not a directory: {media_path}")
            raise ValueError(f"Media path is not a directory: {media_path}")

        logger.info(f"📂 Starting file system watcher on: {media_path}")
        logger.info(f"   Recursive: {settings.scanner_watch_recursive}")
        logger.info(f"   Extensions: {settings.scanner_media_extensions}")
        logger.info(f"   Debounce: {settings.scanner_debounce_seconds}s")

        self.event_handler = MediaFileEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(media_path),
            recursive=settings.scanner_watch_recursive,
        )
        self.observer.start()
        self.running = True

        logger.info("✅ File system watcher started")

    def stop(self) -> None:
        """Stop the file system observer."""
        if not self.running:
            return

        logger.info("🛑 Stopping file system watcher...")

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)

        self.running = False
        logger.info("✅ File system watcher stopped")

    def is_running(self) -> bool:
        """
        Check if scanner is running.

        Returns:
            True if scanner is running, False otherwise
        """
        return self.running

    def _create_webhook_app(self) -> FastAPI:
        """
        Create FastAPI application for webhook endpoint.

        Returns:
            FastAPI application instance
        """
        app = FastAPI(
            title="Scanner Webhook API",
            description="Webhook endpoint for Jellyfin notifications",
            version="1.0.0",
        )

        @app.post("/webhooks/jellyfin")
        async def handle_jellyfin_webhook(payload: dict):
            """Handle webhook notifications from Jellyfin."""
            from manager.schemas import JellyfinWebhookPayload

            # FastAPI receives payload as dict, convert to Pydantic model for validation
            webhook_payload = JellyfinWebhookPayload(**payload)

            result = await self.webhook_handler.process_webhook(webhook_payload)
            return result.model_dump()

        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "scanner"}

        return app

    async def start_webhook_server(self) -> None:
        """Start the webhook HTTP server."""
        if self.webhook_app is not None:
            logger.warning("Webhook server is already running")
            return

        logger.info(
            f"🌐 Starting webhook server on {settings.scanner_webhook_host}:{settings.scanner_webhook_port}"
        )

        self.webhook_app = self._create_webhook_app()

        # Import uvicorn here to avoid import errors if not installed
        import uvicorn

        # Create server config
        config = uvicorn.Config(
            app=self.webhook_app,
            host=settings.scanner_webhook_host,
            port=settings.scanner_webhook_port,
            log_config=None,  # Use our own logging
        )
        server = uvicorn.Server(config)

        # Run server in background task
        self.webhook_server_task = asyncio.create_task(server.serve())

        logger.info("✅ Webhook server started")

    async def stop_webhook_server(self) -> None:
        """Stop the webhook HTTP server."""
        if self.webhook_server_task is None:
            return

        logger.info("🛑 Stopping webhook server...")

        # Cancel the server task
        self.webhook_server_task.cancel()
        try:
            await self.webhook_server_task
        except asyncio.CancelledError:
            pass

        self.webhook_app = None
        self.webhook_server_task = None

        logger.info("✅ Webhook server stopped")
