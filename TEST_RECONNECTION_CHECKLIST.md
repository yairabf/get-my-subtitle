# Reconnection Testing Checklist

## Quick Verification Steps

### 1. Start All Workers

```bash
# Terminal 1
./run-worker.sh manager

# Terminal 2  
./run-worker.sh downloader

# Terminal 3
./run-worker.sh translator

# Terminal 4
./run-worker.sh consumer

# Terminal 5
./run-worker.sh scanner
```

### 2. Verify Initial Connections

Check each worker shows:
- [ ] Manager: `✅ Redis connected successfully`
- [ ] Downloader: `✅ Connected to Redis successfully`
- [ ] Translator: `✅ Connected to Redis successfully`
- [ ] Consumer: `✅ Connected to Redis successfully`
- [ ] Scanner: `✅ Connected to Redis successfully`

All workers should also show RabbitMQ connection success.

### 3. Restart Infrastructure

```bash
docker compose restart redis rabbitmq
```

### 4. Watch for Connection Loss

All workers should show:
- [ ] RabbitMQ: `ERROR:aiormq.connection:Unexpected connection close`
- [ ] RabbitMQ: `WARNING:aio_pika.robust_connection:Connection attempt failed`
- [ ] Redis: `⚠️ Redis connection lost` or `⚠️ Redis health check failed`

### 5. Watch for Reconnection Attempts

During reconnection:
- [ ] Redis: `🔄 Starting Redis reconnection process...`
- [ ] Redis: `Failed to connect to Redis (attempt 1/10)...`
- [ ] RabbitMQ: `Reconnecting after 5 seconds`

### 6. Verify Successful Reconnection

**Redis Success Messages (should see one or more per worker):**
- [ ] `✅ Connected to Redis successfully`
- [ ] `✅ Redis reconnection successful! Connection restored.`
- [ ] Scanner also: `✅ Redis reconnected successfully (scanner worker)!`

**RabbitMQ Success Messages:**
- [ ] Manager: `🔄 Manager event consumer reconnected to RabbitMQ successfully!`
- [ ] Manager: `🔄 Orchestrator reconnected to RabbitMQ successfully!`
- [ ] Downloader: `🔄 Downloader worker reconnected to RabbitMQ successfully!`
- [ ] Translator: `🔄 Translator worker reconnected to RabbitMQ successfully!`
- [ ] Consumer: `🔄 Consumer worker reconnected to RabbitMQ successfully!`
- [ ] All: `🔄 Event publisher reconnected to RabbitMQ successfully!`

### 7. Verify Workers Continue Processing

- [ ] Workers don't crash
- [ ] No manual intervention needed
- [ ] Health checks continue running
- [ ] Workers can process messages after reconnection

## Expected Timeline

| Time | Event |
|------|-------|
| T+0s | Infrastructure restart initiated |
| T+1s | Connections lost, errors appear |
| T+1-10s | Reconnection attempts with exponential backoff |
| T+10-15s | Infrastructure fully started |
| T+15-20s | Successful reconnection messages appear |
| T+20s+ | Normal operation resumes |

## Common Issues

### No Reconnection Messages

**Problem:** Infrastructure didn't actually restart
**Solution:** Check `docker compose ps` and logs

### Workers Crash

**Problem:** Max retries exceeded or application bug
**Solution:** Check worker logs for stack traces, increase retry limits

### Partial Reconnections

**Problem:** Only some workers reconnect
**Solution:** Check which services are actually running with `docker compose ps`

## Success Criteria

✅ All workers show connection loss warnings  
✅ All workers show reconnection attempts  
✅ All workers show success messages for both Redis and RabbitMQ  
✅ All workers continue running after reconnection  
✅ No manual intervention required  
✅ Health checks continue working  

## Quick Command to Check Logs

```bash
# Grep for success messages in all worker logs
grep -E "✅|🔄" /tmp/manager.log /tmp/downloader.log /tmp/translator.log /tmp/consumer.log /tmp/scanner.log

# Should show multiple success indicators for each worker
```

## Automated Test Script

```bash
#!/bin/bash
# test_reconnection.sh

echo "🚀 Starting workers..."
./run-worker.sh manager > /tmp/manager.log 2>&1 &
./run-worker.sh downloader > /tmp/downloader.log 2>&1 &
./run-worker.sh translator > /tmp/translator.log 2>&1 &
./run-worker.sh consumer > /tmp/consumer.log 2>&1 &
./run-worker.sh scanner > /tmp/scanner.log 2>&1 &

echo "⏳ Waiting for workers to start (10s)..."
sleep 10

echo "🔄 Restarting infrastructure..."
docker compose restart redis rabbitmq

echo "⏳ Waiting for reconnection (30s)..."
sleep 30

echo ""
echo "📊 Checking for reconnection success messages..."
echo ""

echo "=== Manager ==="
grep "✅.*reconnect" /tmp/manager.log | head -3

echo "=== Downloader ==="
grep "✅.*reconnect" /tmp/downloader.log | head -3

echo "=== Translator ==="
grep "✅.*reconnect" /tmp/translator.log | head -3

echo "=== Consumer ==="
grep "✅.*reconnect" /tmp/consumer.log | head -3

echo "=== Scanner ==="
grep "✅.*reconnect" /tmp/scanner.log | head -3

echo ""
echo "🧹 Cleaning up..."
pkill -f "run-worker.sh"

echo "✅ Test complete!"
```

Make it executable: `chmod +x test_reconnection.sh`
Run it: `./test_reconnection.sh`

