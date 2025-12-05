"""Graceful shutdown management for async workers."""

import asyncio
import logging
import signal
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class ShutdownState(Enum):
    """Shutdown state tracking."""

    NOT_STARTED = "not_started"
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ShutdownManager:
    """
    Manages graceful shutdown for async workers.

    Features:
    - Async-compatible signal handling (SIGINT, SIGTERM)
    - Shutdown event flag for consumption loop control
    - Configurable timeout for in-flight message processing
    - Cleanup callback registration system
    - Shutdown state tracking
    - Idempotent signal handling (multiple signals handled gracefully)

    Example:
        ```python
        shutdown_manager = ShutdownManager("translator", shutdown_timeout=30.0)
        await shutdown_manager.setup_signal_handlers()

        # Register cleanup callbacks
        shutdown_manager.register_cleanup_callback(
            lambda: redis_client.disconnect()
        )

        # Main loop
        while not shutdown_manager.is_shutdown_requested():
            await process_messages()

        # Cleanup
        await shutdown_manager.execute_cleanup()
        ```
    """

    def __init__(self, service_name: str, shutdown_timeout: float = 30.0):
        """
        Initialize the shutdown manager.

        Args:
            service_name: Name of the service (for logging)
            shutdown_timeout: Timeout in seconds for graceful shutdown (must be between 1.0 and 300.0)

        Raises:
            ValueError: If shutdown_timeout is outside valid range
        """
        if not 1.0 <= shutdown_timeout <= 300.0:
            raise ValueError(
                f"shutdown_timeout must be between 1.0 and 300.0 seconds, got {shutdown_timeout}"
            )

        self.service_name = service_name
        self.shutdown_timeout = shutdown_timeout
        self._shutdown_event = asyncio.Event()
        self._cleanup_callbacks: List[Callable] = []
        self._state = ShutdownState.NOT_STARTED
        self._signal_received_count = 0
        logger.info(
            f"🛡️  Shutdown manager initialized for {service_name} "
            f"(timeout: {shutdown_timeout}s)"
        )

    async def setup_signal_handlers(self) -> None:
        """
        Setup async-compatible signal handlers for SIGINT and SIGTERM.

        Uses asyncio.get_event_loop().add_signal_handler() for proper
        async integration instead of synchronous signal.signal().
        """
        loop = asyncio.get_event_loop()

        # Define signal handler
        def handle_signal(signum: int) -> None:
            """
            Handle shutdown signals (SIGINT/SIGTERM).

            First signal: Initiates graceful shutdown
            Second signal: Attempts fast cleanup with 5s timeout, then forces exit
            Subsequent signals: Logged but ignored
            """
            self._signal_received_count += 1
            signal_name = signal.Signals(signum).name

            if self._signal_received_count == 1:
                logger.info(
                    f"🛑 Received {signal_name}, initiating graceful shutdown for {self.service_name}..."
                )
                self._state = ShutdownState.INITIATED
                self._shutdown_event.set()
            elif self._signal_received_count == 2:
                logger.critical(
                    f"⚠️  Received second {signal_name}. Attempting fast shutdown with minimal cleanup..."
                )
                # Attempt fast cleanup with short timeout
                try:
                    asyncio.create_task(self._fast_cleanup())
                except Exception as e:
                    logger.error(f"Fast cleanup task creation failed: {e}")
                finally:
                    import sys

                    # Use sys.exit instead of os._exit to allow some cleanup
                    sys.exit(1)
            else:
                logger.warning(
                    f"⚠️  Received {signal_name} (count: {self._signal_received_count}), "
                    f"already shutting down..."
                )

        # Register handlers for SIGINT and SIGTERM
        try:
            loop.add_signal_handler(signal.SIGINT, lambda: handle_signal(signal.SIGINT))
            loop.add_signal_handler(
                signal.SIGTERM, lambda: handle_signal(signal.SIGTERM)
            )
            logger.info(
                f"✅ Signal handlers registered for {self.service_name} (SIGINT, SIGTERM)"
            )
        except NotImplementedError:
            # Windows doesn't support add_signal_handler, fallback to signal.signal
            logger.warning(
                "⚠️  asyncio.add_signal_handler not supported on this platform, "
                "using fallback signal.signal()"
            )
            signal.signal(signal.SIGINT, lambda s, f: handle_signal(s))
            signal.signal(signal.SIGTERM, lambda s, f: handle_signal(s))

    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.

        Returns:
            True if shutdown signal received, False otherwise
        """
        return self._shutdown_event.is_set()

    def request_shutdown(self) -> None:
        """
        Manually request shutdown without receiving a signal.

        This is useful for programmatic shutdown or testing scenarios
        where you want to trigger shutdown without sending OS signals.
        """
        logger.info(f"🛑 Manual shutdown requested for {self.service_name}")
        self._state = ShutdownState.INITIATED
        self._shutdown_event.set()

    def _trigger_shutdown_for_testing(self) -> None:
        """
        TESTING ONLY: Manually trigger shutdown for test scenarios.

        This method should only be used in test code to simulate
        shutdown conditions without relying on signal handling.
        """
        self._shutdown_event.set()
        self._state = ShutdownState.INITIATED

    def get_state(self) -> ShutdownState:
        """
        Get current shutdown state.

        Returns:
            Current ShutdownState
        """
        return self._state

    def register_cleanup_callback(self, callback: Callable) -> None:
        """
        Register a cleanup callback to be executed during shutdown.

        Callbacks are executed in reverse order of registration (LIFO).
        This ensures proper cleanup order (e.g., close channel before connection).

        Args:
            callback: Async or sync callable to execute during cleanup
        """
        self._cleanup_callbacks.append(callback)
        logger.debug(
            f"Registered cleanup callback for {self.service_name} "
            f"(total: {len(self._cleanup_callbacks)})"
        )

    async def execute_cleanup(self) -> None:
        """
        Execute all registered cleanup callbacks in reverse order (LIFO).

        Handles both async and sync callbacks gracefully.
        Logs errors but continues with remaining callbacks.
        """
        if self._state == ShutdownState.COMPLETED:
            logger.debug(f"Cleanup already executed for {self.service_name}")
            return

        self._state = ShutdownState.IN_PROGRESS
        logger.info(
            f"🧹 Executing cleanup for {self.service_name} "
            f"({len(self._cleanup_callbacks)} callbacks)..."
        )

        # Execute callbacks in reverse order (LIFO)
        for i, callback in enumerate(reversed(self._cleanup_callbacks), 1):
            try:
                callback_name = getattr(callback, "__name__", str(callback))
                logger.debug(
                    f"Executing cleanup callback {i}/{len(self._cleanup_callbacks)}: {callback_name}"
                )

                # Handle both async and sync callbacks
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()

            except Exception as e:
                callback_name = getattr(callback, "__name__", str(callback))
                logger.error(
                    f"❌ Error executing cleanup callback {callback_name}: {e}",
                    exc_info=True,
                )

        self._state = ShutdownState.COMPLETED
        logger.info(f"✅ Cleanup completed for {self.service_name}")

    async def _fast_cleanup(self) -> None:
        """
        Execute critical cleanup only with aggressive timeout.

        This is called when a second shutdown signal is received,
        attempting minimal cleanup before forcing exit.
        """
        try:
            logger.warning("⚡ Executing fast cleanup (5s timeout)...")
            await asyncio.wait_for(self.execute_cleanup(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("❌ Fast cleanup timeout - forcing exit")
        except Exception as e:
            logger.error(f"❌ Fast cleanup failed: {e}")

    async def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown signal with optional timeout.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if shutdown was requested, False if timeout occurred
        """
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def __repr__(self) -> str:
        """String representation of shutdown manager."""
        return (
            f"ShutdownManager(service={self.service_name}, "
            f"state={self._state.value}, "
            f"timeout={self.shutdown_timeout}s, "
            f"callbacks={len(self._cleanup_callbacks)})"
        )
