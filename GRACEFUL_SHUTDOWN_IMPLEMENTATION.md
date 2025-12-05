# Graceful Shutdown Implementation

## Overview

This document describes the implementation of graceful shutdown functionality across all workers in the subtitle management system. The implementation ensures clean exits, proper resource cleanup, and no message loss during shutdown events (SIGINT/SIGTERM).

## Implementation Summary

### 1. Core Component: ShutdownManager

**File:** `src/common/shutdown_manager.py`

A centralized utility class that provides:
- Async-compatible signal handling (SIGINT, SIGTERM)
- Shutdown event flag for consumption loop control
- Configurable timeout for in-flight message processing (default: 30 seconds)
- Cleanup callback registration system (LIFO execution order)
- Shutdown state tracking (not_started, initiated, in_progress, completed)
- Idempotent signal handling (multiple signals handled gracefully)

**Key Methods:**
- `setup_signal_handlers()`: Registers async signal handlers
- `is_shutdown_requested()`: Check if shutdown has been triggered
- `register_cleanup_callback()`: Register cleanup functions (executed in LIFO order)
- `execute_cleanup()`: Execute all cleanup callbacks
- `wait_for_shutdown()`: Wait for shutdown signal with timeout

### 2. Configuration

**File:** `src/common/config.py`

Added new configuration parameter:
```python
shutdown_timeout: float = Field(
    default=30.0, env="SHUTDOWN_TIMEOUT"
)  # Timeout in seconds for graceful shutdown (in-flight message processing)
```

### 3. Worker Updates

#### Scanner Worker (`src/scanner/worker.py`)

**Changes:**
- Replaced synchronous `signal.signal()` with `ShutdownManager`
- Removed `signal_handler_sync` function
- Updated main loop to check `shutdown_manager.is_shutdown_requested()`
- Registered cleanup callbacks for scanner components

**Benefits:**
- Proper async signal handling
- Clean shutdown of file system watcher
- Graceful webhook server shutdown

#### Translator Worker (`src/translator/worker.py`)

**Changes:**
- Added `ShutdownManager` to consumption loop
- Replaced `should_stop` flag with `shutdown_manager.is_shutdown_requested()`
- Wrapped message processing in `asyncio.wait_for()` with timeout
- Added shutdown check before processing each message

**Benefits:**
- Timeout enforcement during shutdown (prevents hanging)
- Messages are properly nacked/requeued if timeout occurs
- Clean RabbitMQ channel and connection closure

#### Downloader Worker (`src/downloader/worker.py`)

**Changes:**
- Added `ShutdownManager` to consumption loop
- Replaced `should_stop` flag with `shutdown_manager.is_shutdown_requested()`
- Wrapped message processing in `asyncio.wait_for()` with timeout
- Added shutdown check before processing each message

**Benefits:**
- Timeout enforcement during shutdown
- Clean OpenSubtitles client disconnection
- Proper resource cleanup (Redis, RabbitMQ, event publisher)

#### Consumer Worker (`src/consumer/worker.py`)

**Changes:**
- Added `ShutdownManager` as instance variable in `EventConsumer`
- Replaced `_should_stop` flag with `shutdown_manager.is_shutdown_requested()`
- Updated `stop()` method to use shutdown manager
- Wrapped message processing in `asyncio.wait_for()` with timeout

**Benefits:**
- Consistent shutdown behavior across all workers
- Timeout enforcement during event processing
- Clean Redis and RabbitMQ connection closure

### 4. Testing

**Files:**
- `tests/common/test_shutdown_manager.py` (20 tests)
- `tests/scanner/test_worker.py` (3 shutdown tests)
- `tests/translator/test_worker.py` (4 shutdown tests)
- `tests/downloader/test_worker.py` (4 shutdown tests)
- `tests/consumer/test_worker.py` (5 shutdown tests)

**Test Coverage:**
- Signal handling (SIGINT, SIGTERM)
- Timeout enforcement during shutdown
- Cleanup callback execution (sync and async)
- Message consumption stops on shutdown
- Multiple signals handling (idempotent)
- Cleanup callback ordering (LIFO)
- Exception handling during cleanup

## Shutdown Flow

### Normal Shutdown Flow

1. **Signal Received** (SIGINT or SIGTERM)
   - ShutdownManager sets shutdown event
   - State changes to `INITIATED`

2. **Current Message Processing**
   - If message is being processed, wait up to `shutdown_timeout` seconds
   - If timeout occurs, message is nacked and requeued
   - Otherwise, message completes normally

3. **Stop Consuming**
   - Worker exits message consumption loop
   - No new messages are accepted

4. **Cleanup Execution**
   - All registered cleanup callbacks execute in reverse order (LIFO)
   - Both sync and async callbacks supported
   - Errors are logged but don't stop cleanup

5. **Clean Exit**
   - State changes to `COMPLETED`
   - Process exits with code 0

### Force Shutdown Flow

If a second signal is received during shutdown:
- ShutdownManager logs warning
- Event loop is stopped immediately
- Process exits (resources may not be fully cleaned up)

## Message Acknowledgement Strategy

### Normal Completion
- Message is automatically acked by `async with message.process()` context manager

### During Shutdown with Timeout
- Message processing wrapped in `asyncio.wait_for()`
- If timeout occurs, break out of processing
- Context manager automatically nacks message with `requeue=True`
- Message returns to queue for processing by another worker

### Exception During Processing
- Already handled by `message.process()` context manager
- Message is nacked and requeued

## Benefits

1. **No Hanging Processes**: All workers handle SIGINT and SIGTERM gracefully
2. **Timeout Enforcement**: Current message processing respects configurable timeout
3. **Clean Resource Cleanup**: Redis, RabbitMQ, files properly closed
4. **No Message Loss**: Messages are nacked/requeued if not completed
5. **Consistent Behavior**: All workers use same shutdown mechanism
6. **Comprehensive Testing**: All shutdown scenarios validated
7. **Production Ready**: Handles edge cases (multiple signals, cleanup errors)

## Configuration

The shutdown timeout can be configured via environment variable:

```bash
# Default: 30 seconds
SHUTDOWN_TIMEOUT=30.0

# For faster shutdown in development
SHUTDOWN_TIMEOUT=10.0

# For longer-running tasks
SHUTDOWN_TIMEOUT=60.0
```

## Deployment Considerations

### Docker
- Container will now shutdown cleanly with `docker stop`
- Workers have time to complete current messages before exit
- Resources are properly cleaned up

### Kubernetes
- Pods respect termination grace period
- Workers shutdown within `terminationGracePeriodSeconds`
- Recommended: Set `terminationGracePeriodSeconds` to `shutdown_timeout + 10` seconds

### systemd
- Services shutdown cleanly with `systemctl stop`
- Workers handle SIGTERM properly
- No need for `KillMode=mixed` or `SIGKILL`

## Monitoring

Workers log shutdown progress:
- `🛑 Received <signal>, initiating graceful shutdown...`
- `🛑 Shutdown requested, stopping message consumption...`
- `⚠️ Message processing timeout (30s) during shutdown - message will be requeued`
- `🧹 Executing cleanup... (X callbacks)`
- `🔌 Disconnecting <service>...`
- `✅ Cleanup completed for <service>`

## Troubleshooting

### Worker Not Shutting Down
- Check logs for shutdown signal reception
- Verify message processing isn't taking longer than timeout
- Consider increasing `SHUTDOWN_TIMEOUT` for long-running tasks

### Messages Not Being Requeued
- Verify RabbitMQ connection is stable during shutdown
- Check that `message.process()` context manager is used correctly
- Review logs for timeout messages

### Resources Not Cleaned Up
- Verify cleanup callbacks are registered
- Check logs for cleanup errors
- Ensure async cleanup callbacks use `await` properly

## Future Enhancements

1. **Metrics**: Add Prometheus metrics for shutdown duration and message nack counts
2. **Health Checks**: Expose shutdown state via health endpoint
3. **Graceful Drain**: Wait for queue to drain before shutdown (opt-in)
4. **Progressive Timeout**: Warn at 50%, 75%, 90% of timeout
5. **Shutdown Reason**: Track why shutdown was triggered (signal, error, manual)
