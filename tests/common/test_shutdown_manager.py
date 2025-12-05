"""Tests for graceful shutdown manager."""

import asyncio
import signal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.shutdown_manager import ShutdownManager, ShutdownState


class TestShutdownManager:
    """Test cases for ShutdownManager."""

    @pytest.fixture
    def shutdown_manager(self):
        """Create a ShutdownManager instance for testing."""
        return ShutdownManager("test_service", shutdown_timeout=5.0)

    def test_initialization(self, shutdown_manager):
        """Test ShutdownManager initialization."""
        assert shutdown_manager.service_name == "test_service"
        assert shutdown_manager.shutdown_timeout == 5.0
        assert not shutdown_manager.is_shutdown_requested()
        assert shutdown_manager.get_state() == ShutdownState.NOT_STARTED

    @pytest.mark.asyncio
    async def test_setup_signal_handlers(self, shutdown_manager):
        """Test signal handler setup."""
        await shutdown_manager.setup_signal_handlers()
        # Verify no exceptions were raised
        assert True

    def test_is_shutdown_requested_initially_false(self, shutdown_manager):
        """Test shutdown not requested initially."""
        assert not shutdown_manager.is_shutdown_requested()

    @pytest.mark.asyncio
    async def test_is_shutdown_requested_after_signal(self, shutdown_manager):
        """Test shutdown requested after signal."""
        await shutdown_manager.setup_signal_handlers()

        # Simulate SIGINT
        shutdown_manager._trigger_shutdown_for_testing()

        assert shutdown_manager.is_shutdown_requested()

    def test_register_cleanup_callback(self, shutdown_manager):
        """Test registering cleanup callbacks."""
        callback1 = Mock()
        callback2 = Mock()

        shutdown_manager.register_cleanup_callback(callback1)
        shutdown_manager.register_cleanup_callback(callback2)

        assert len(shutdown_manager._cleanup_callbacks) == 2

    @pytest.mark.asyncio
    async def test_execute_cleanup_sync_callbacks(self, shutdown_manager):
        """Test cleanup execution with synchronous callbacks."""
        callback1 = Mock()
        callback2 = Mock()

        shutdown_manager.register_cleanup_callback(callback1)
        shutdown_manager.register_cleanup_callback(callback2)

        await shutdown_manager.execute_cleanup()

        # Callbacks executed in reverse order (LIFO)
        assert callback2.call_count == 1
        assert callback1.call_count == 1
        assert shutdown_manager.get_state() == ShutdownState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_cleanup_async_callbacks(self, shutdown_manager):
        """Test cleanup execution with asynchronous callbacks."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()

        shutdown_manager.register_cleanup_callback(callback1)
        shutdown_manager.register_cleanup_callback(callback2)

        await shutdown_manager.execute_cleanup()

        # Callbacks executed in reverse order (LIFO)
        assert callback2.call_count == 1
        assert callback1.call_count == 1
        assert shutdown_manager.get_state() == ShutdownState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_cleanup_mixed_callbacks(self, shutdown_manager):
        """Test cleanup execution with mixed sync/async callbacks."""
        sync_callback = Mock()
        async_callback = AsyncMock()

        shutdown_manager.register_cleanup_callback(sync_callback)
        shutdown_manager.register_cleanup_callback(async_callback)

        await shutdown_manager.execute_cleanup()

        assert async_callback.call_count == 1
        assert sync_callback.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_cleanup_handles_exceptions(self, shutdown_manager):
        """Test cleanup continues even if callbacks raise exceptions."""
        failing_callback = Mock(side_effect=Exception("Callback error"))
        success_callback = Mock()

        shutdown_manager.register_cleanup_callback(failing_callback)
        shutdown_manager.register_cleanup_callback(success_callback)

        # Should not raise exception
        await shutdown_manager.execute_cleanup()

        # Both callbacks should be called despite error
        assert failing_callback.call_count == 1
        assert success_callback.call_count == 1
        assert shutdown_manager.get_state() == ShutdownState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_cleanup_idempotent(self, shutdown_manager):
        """Test cleanup can be called multiple times safely."""
        callback = Mock()
        shutdown_manager.register_cleanup_callback(callback)

        await shutdown_manager.execute_cleanup()
        await shutdown_manager.execute_cleanup()

        # Callback only executed once
        assert callback.call_count == 1

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_success(self, shutdown_manager):
        """Test waiting for shutdown signal."""

        # Trigger shutdown after a delay
        async def trigger_shutdown():
            await asyncio.sleep(0.1)
            shutdown_manager._trigger_shutdown_for_testing()

        task = asyncio.create_task(trigger_shutdown())
        result = await shutdown_manager.wait_for_shutdown(timeout=1.0)
        await task

        assert result is True
        assert shutdown_manager.is_shutdown_requested()

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_timeout(self, shutdown_manager):
        """Test waiting for shutdown with timeout."""
        result = await shutdown_manager.wait_for_shutdown(timeout=0.1)

        assert result is False
        assert not shutdown_manager.is_shutdown_requested()

    @pytest.mark.asyncio
    async def test_state_transitions(self, shutdown_manager):
        """Test shutdown state transitions."""
        assert shutdown_manager.get_state() == ShutdownState.NOT_STARTED

        # Simulate signal
        shutdown_manager._state = ShutdownState.INITIATED
        assert shutdown_manager.get_state() == ShutdownState.INITIATED

        # Start cleanup
        callback = Mock()
        shutdown_manager.register_cleanup_callback(callback)
        await shutdown_manager.execute_cleanup()

        assert shutdown_manager.get_state() == ShutdownState.COMPLETED

    def test_repr(self, shutdown_manager):
        """Test string representation."""
        repr_str = repr(shutdown_manager)
        assert "test_service" in repr_str
        assert "5.0s" in repr_str
        assert "callbacks=0" in repr_str

    @pytest.mark.asyncio
    async def test_signal_handler_first_signal(self, shutdown_manager):
        """Test first signal initiates graceful shutdown."""
        await shutdown_manager.setup_signal_handlers()

        # Manually trigger shutdown event (simulating signal)
        shutdown_manager._trigger_shutdown_for_testing()
        shutdown_manager._state = ShutdownState.INITIATED
        shutdown_manager._signal_received_count = 1

        assert shutdown_manager.is_shutdown_requested()
        assert shutdown_manager.get_state() == ShutdownState.INITIATED

    @pytest.mark.asyncio
    async def test_signal_handler_multiple_signals(self, shutdown_manager):
        """Test multiple signals are handled gracefully."""
        await shutdown_manager.setup_signal_handlers()

        # Simulate multiple signals
        shutdown_manager._trigger_shutdown_for_testing()
        shutdown_manager._signal_received_count = 3

        # Should still be in valid state
        assert shutdown_manager.is_shutdown_requested()

    @pytest.mark.asyncio
    async def test_cleanup_callback_order(self, shutdown_manager):
        """Test cleanup callbacks execute in LIFO order."""
        call_order = []

        def callback1():
            call_order.append(1)

        def callback2():
            call_order.append(2)

        def callback3():
            call_order.append(3)

        shutdown_manager.register_cleanup_callback(callback1)
        shutdown_manager.register_cleanup_callback(callback2)
        shutdown_manager.register_cleanup_callback(callback3)

        await shutdown_manager.execute_cleanup()

        # Callbacks executed in reverse order: 3, 2, 1
        assert call_order == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_async_callback_execution(self, shutdown_manager):
        """Test async callbacks are properly awaited."""
        execution_flag = {"executed": False}

        async def async_callback():
            await asyncio.sleep(0.01)
            execution_flag["executed"] = True

        shutdown_manager.register_cleanup_callback(async_callback)
        await shutdown_manager.execute_cleanup()

        assert execution_flag["executed"] is True


class TestShutdownManagerIntegration:
    """Integration tests for ShutdownManager."""

    @pytest.mark.asyncio
    async def test_full_shutdown_flow(self):
        """Test complete shutdown flow from signal to cleanup."""
        manager = ShutdownManager("integration_test", shutdown_timeout=2.0)
        await manager.setup_signal_handlers()

        # Track execution
        cleanup_executed = {"count": 0}

        async def cleanup_task():
            cleanup_executed["count"] += 1

        manager.register_cleanup_callback(cleanup_task)

        # Simulate work loop
        iterations = 0
        while not manager.is_shutdown_requested() and iterations < 5:
            await asyncio.sleep(0.1)
            iterations += 1

            # Trigger shutdown after 2 iterations
            if iterations == 2:
                manager._shutdown_event.set()

        # Execute cleanup
        await manager.execute_cleanup()

        assert manager.is_shutdown_requested()
        assert cleanup_executed["count"] == 1
        assert manager.get_state() == ShutdownState.COMPLETED

    @pytest.mark.asyncio
    async def test_multiple_services_independent(self):
        """Test multiple shutdown managers work independently."""
        manager1 = ShutdownManager("service1")
        manager2 = ShutdownManager("service2")

        # Only trigger shutdown for manager1
        manager1._shutdown_event.set()

        assert manager1.is_shutdown_requested()
        assert not manager2.is_shutdown_requested()
