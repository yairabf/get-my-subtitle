# Fix for False "Connection Lost" Warnings

## Problem

Workers were logging `⚠️ RabbitMQ connection lost:` warnings during normal startup/reconnection, even when RabbitMQ was running fine. This created confusion and made it hard to identify real connection issues.

**Example of false warning:**
```
2025-12-05 10:26:24 - WARNING - ⚠️ RabbitMQ connection lost: 
2025-12-05 10:26:24 - INFO - Connected to RabbitMQ - Queue 'manager.subtitle.requests'
```

## Root Cause

The `close_callbacks` were being triggered during normal connection establishment and graceful shutdowns, not just during unexpected disconnections. The callback was logging warnings for every close event, including intentional ones.

## Solution

### Removed Close Callbacks from Workers

Removed the `close_callbacks` from all workers since:
1. They were causing false warnings during normal operations
2. The library-level logs (`ERROR:aiormq.connection`) already show real connection losses
3. Reconnection success is what matters most for operators

**Files Modified:**
- `src/manager/event_consumer.py`
- `src/manager/orchestrator.py`
- `src/downloader/worker.py`
- `src/translator/worker.py`
- `src/consumer/worker.py`

**Before:**
```python
connection.close_callbacks.add(
    lambda conn, exc=None: logger.warning(f"⚠️ RabbitMQ connection lost: {exc}") if exc else None
)
```

**After:**
```python
# Removed close_callbacks - library logs already show connection loss
```

### Improved Event Publisher Close Callback

The event publisher keeps its close callback but only logs on actual errors:

**File:** `src/common/event_publisher.py`

**Before:**
```python
async def _on_disconnect(self, connection: AbstractConnection, exc: Optional[Exception] = None) -> None:
    if exc:
        logger.warning(f"⚠️ Event publisher connection lost: {exc}")
    else:
        logger.info("Event publisher connection closed gracefully")
```

**After:**
```python
async def _on_disconnect(self, connection: AbstractConnection, exc: Optional[Exception] = None) -> None:
    # Only log if there was an actual error during active connection
    # Don't log during normal startup/shutdown
    if exc and not isinstance(exc, (asyncio.CancelledError,)):
        logger.warning(f"⚠️ Event publisher connection lost: {exc}")
```

## What You'll See Now

### During Normal Startup
```
INFO: Connected to RabbitMQ - Queue 'manager.subtitle.requests'
```
✅ No false warnings

### During Actual Connection Loss
```
ERROR:aiormq.connection:Unexpected connection close from remote "amqp://guest:******@localhost:5672/"
WARNING:aio_pika.robust_connection:Connection attempt failed: Connection refused. Reconnecting after 5 seconds.
```
⚠️ Library-level logs show the real issue

### During Successful Reconnection
```
INFO:manager.event_consumer:🔄 Manager event consumer reconnected to RabbitMQ successfully!
```
✅ Clear success message

## Benefits

1. **No False Positives**: Only see warnings when there's a real problem
2. **Cleaner Logs**: Less noise during normal operations
3. **Clear Success**: Focus on reconnection success messages
4. **Library Logs Available**: Real issues still visible in aiormq/aio_pika logs

## Comparison

### Before (with false warnings)
```
2025-12-05 10:26:24 - WARNING - ⚠️ RabbitMQ connection lost: 
2025-12-05 10:26:24 - INFO - Connected to RabbitMQ - Queue 'manager.subtitle.requests'
2025-12-05 10:26:24 - WARNING - ⚠️ RabbitMQ connection lost: 
2025-12-05 10:26:24 - INFO - 🔄 Manager event consumer reconnected to RabbitMQ successfully!
```

### After (clean logs)
```
2025-12-05 10:26:24 - INFO - Connected to RabbitMQ - Queue 'manager.subtitle.requests'
2025-12-05 10:26:24 - INFO - 🔄 Manager event consumer reconnected to RabbitMQ successfully!
```

## When to Worry

### ⚠️ Real Connection Issues Look Like:
```
ERROR:aiormq.connection:Unexpected connection close from remote "amqp://guest:******@localhost:5672/"
WARNING:aio_pika.robust_connection:Connection attempt to "amqp://guest:******@localhost:5672/" failed: [Errno 61] Connection refused. Reconnecting after 5 seconds.
WARNING:aio_pika.robust_connection:Connection attempt to "amqp://guest:******@localhost:5672/" failed: [Errno 61] Connection refused. Reconnecting after 5 seconds.
```

Followed by (after RabbitMQ is back):
```
INFO:downloader.worker:🔄 Downloader worker reconnected to RabbitMQ successfully!
```

## Testing

1. Start any worker
2. **Should NOT see**: `⚠️ RabbitMQ connection lost:` during startup
3. **Should see**: Success messages and normal operation logs
4. Stop RabbitMQ
5. **Should see**: Library-level error logs
6. Start RabbitMQ
7. **Should see**: `🔄 ... reconnected to RabbitMQ successfully!`

## Status

✅ **Fixed** - False warnings removed, only real issues trigger warnings
