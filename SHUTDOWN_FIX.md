# Graceful Shutdown Fix - First Ctrl+C Not Responding

## Problem

When pressing **Ctrl+C** once in the downloader, translator, or consumer workers, they would not respond immediately. The workers appeared to "hang" and required pressing **Ctrl+C** a second time, which would then cause a `RuntimeError: Event loop stopped before Future completed.`

### Root Cause

The workers were using `async for message in queue.iterator()` which blocks indefinitely waiting for the next message from RabbitMQ. When Ctrl+C was pressed:

1. Signal handler sets `shutdown_event.set()`
2. But the code is still blocked waiting for the next message
3. The `shutdown_manager.is_shutdown_requested()` check only happens **after** receiving a message
4. If no messages arrive, the worker never checks for shutdown

### Error on Second Ctrl+C

The second Ctrl+C would call `loop.stop()` which stops the event loop immediately, but the cleanup code in the `finally` block tries to run async operations that need the event loop, resulting in:

```
RuntimeError: Event loop stopped before Future completed.
```

## Solution

### 1. Replace Queue Iterator with Timed Queue.get()

**Before:**
```python
async with queue.iterator() as queue_iter:
    async for message in queue_iter:
        if shutdown_manager.is_shutdown_requested():
            break
        # Process message...
```

**After:**
```python
while not shutdown_manager.is_shutdown_requested():
    try:
        # Get message with timeout to allow periodic shutdown checks
        message = await asyncio.wait_for(
            queue.get(timeout=1.0),
            timeout=1.1  # Slightly longer than queue timeout
        )
        # Process message...
    except asyncio.TimeoutError:
        # No message received, loop continues to check shutdown
        continue
    except aio_pika.exceptions.QueueEmpty:
        # No messages in queue, wait a bit
        await asyncio.sleep(0.1)
        continue
```

### 2. Improve Second Signal Handling

**Before:**
```python
elif self._signal_received_count == 2:
    logger.warning(f"⚠️  Received second {signal_name}, forcing immediate shutdown...")
    loop.stop()  # ❌ Causes RuntimeError
```

**After:**
```python
elif self._signal_received_count == 2:
    logger.warning(f"⚠️  Received second {signal_name}, forcing immediate exit (bypassing cleanup)...")
    import os
    os._exit(1)  # ✅ Hard exit without cleanup
```

## Files Modified

1. ✅ `src/downloader/worker.py` - Lines 616-663
2. ✅ `src/translator/worker.py` - Lines 511-560
3. ✅ `src/consumer/worker.py` - Lines 376-420
4. ✅ `src/common/shutdown_manager.py` - Lines 92-96

## Benefits

1. **✅ First Ctrl+C responds within ~1 second** (instead of blocking indefinitely)
2. **✅ Graceful shutdown works properly** - all cleanup callbacks execute
3. **✅ Second Ctrl+C provides emergency exit** - no more RuntimeError
4. **✅ Periodic shutdown checks** - workers check every second even when idle
5. **✅ All tests still passing** - 33/33 shutdown tests pass

## Testing

All shutdown tests pass:

```bash
pytest tests/common/test_shutdown_manager.py \
       tests/downloader/test_worker.py::TestDownloaderWorkerShutdown \
       tests/translator/test_worker.py::TestTranslatorWorkerShutdown \
       tests/consumer/test_worker.py::TestConsumerWorkerShutdown -v
```

Result: **33 passed** ✅

## Usage

### First Ctrl+C - Graceful Shutdown
Press **Ctrl+C** once:
- ✅ Worker detects shutdown signal within ~1 second
- ✅ Stops consuming new messages
- ✅ Finishes current message (with timeout)
- ✅ Executes all cleanup callbacks
- ✅ Disconnects from Redis, RabbitMQ, etc.
- ✅ Clean exit

### Second Ctrl+C - Emergency Exit
Press **Ctrl+C** a second time (if first is taking too long):
- ✅ Immediately exits using `os._exit(1)`
- ⚠️ Bypasses cleanup (may leave connections open)
- ✅ No RuntimeError
- ✅ Process terminates immediately

## Technical Details

### Why queue.get(timeout=1.0)?

- **Allows periodic shutdown checks:** Instead of blocking indefinitely, the worker checks for shutdown every second
- **Minimal latency:** 1 second is short enough to feel responsive
- **Low overhead:** Timeout exceptions are cheap in asyncio
- **Works with empty queues:** No messages? No problem, just keep checking

### Why os._exit(1) for Second Signal?

- **Immediate termination:** Bypasses all Python cleanup including finally blocks
- **No exceptions raised:** Prevents RuntimeError from stopped event loop
- **True emergency exit:** For when graceful shutdown is stuck
- **Standard practice:** Used in many production systems for hard shutdown

### Why 1.1 second timeout on wait_for?

```python
message = await asyncio.wait_for(
    queue.get(timeout=1.0),  # Queue timeout
    timeout=1.1              # asyncio timeout
)
```

- The outer `asyncio.wait_for()` should be **slightly longer** than the inner `queue.get()` timeout
- This ensures the queue timeout fires first, providing a clean `asyncio.TimeoutError`
- If both timeouts were the same, there would be a race condition

## Alternative Solutions Considered

### ❌ Using asyncio.create_task() for Periodic Checks
```python
async def check_shutdown_periodically():
    while True:
        await asyncio.sleep(1.0)
        if shutdown_manager.is_shutdown_requested():
            queue_iter.stop()
```

**Problem:** Queue iterator doesn't have a stop() method, and cancelling the task would be complex.

### ❌ Using signal.raise_signal() 
```python
import signal
signal.raise_signal(signal.SIGTERM)
```

**Problem:** Would create infinite loop with signal handler, and doesn't solve the blocking issue.

### ✅ Chosen Solution: Timed queue.get()
Simple, reliable, and follows asyncio best practices.

## Rollback Instructions

If this change causes issues, revert to using `queue.iterator()`:

```bash
git diff HEAD~1 src/downloader/worker.py
git checkout HEAD~1 -- src/downloader/worker.py src/translator/worker.py src/consumer/worker.py src/common/shutdown_manager.py
```

Then restart the workers.

## Future Improvements

1. **Make timeout configurable:** Add `SHUTDOWN_CHECK_INTERVAL` env var (default: 1.0)
2. **Add metrics:** Track time from signal to shutdown completion
3. **Graceful drain:** Option to finish all queued messages before shutdown
4. **Third signal behavior:** Could make third Ctrl+C do `os._exit(137)` (SIGKILL exit code)

## References

- [asyncio Queue documentation](https://docs.python.org/3/library/asyncio-queue.html)
- [aio-pika robust connection](https://aio-pika.readthedocs.io/en/latest/apidoc.html#aio_pika.connect_robust)
- [Python signal handling](https://docs.python.org/3/library/signal.html)
- [os._exit() documentation](https://docs.python.org/3/library/os.html#os._exit)
