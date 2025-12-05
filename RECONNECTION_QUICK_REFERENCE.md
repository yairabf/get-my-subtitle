# Reconnection Logging Quick Reference

## What to Look For in Logs

### ✅ SUCCESS - Everything is Working

**Redis:**
```
✅ Connected to Redis successfully
✅ Redis reconnection successful! Connection restored.
```

**RabbitMQ:**
```
🔄 Downloader worker reconnected to RabbitMQ successfully!
🔄 Event publisher reconnected to RabbitMQ successfully!
```

### ⚠️ WARNING - In Progress

**Redis:**
```
⚠️ Redis connection lost: Connection refused
🔄 Starting Redis reconnection process...
Failed to connect to Redis (attempt 1/10): Connection refused. Retrying in 3.0s...
```

**RabbitMQ:**
```
⚠️ RabbitMQ connection lost: CONNECTION_FORCED
Connection attempt to "amqp://..." failed: Connection refused. Reconnecting after 5 seconds.
```

### ❌ ERROR - Action Needed

```
❌ Redis reconnection failed after all retry attempts
Failed to connect to Redis after 10 attempts
```

## Expected Success Messages by Worker

| Worker | Redis | RabbitMQ |
|--------|-------|----------|
| Manager | ✅ (via health check) | 🔄 Manager event consumer<br>🔄 Orchestrator<br>🔄 Event publisher |
| Downloader | ✅ | 🔄 Downloader worker<br>🔄 Event publisher |
| Translator | ✅ | 🔄 Translator worker<br>🔄 Event publisher |
| Consumer | ✅ | 🔄 Consumer worker |
| Scanner | ✅ (via connection_utils) | 🔄 Event publisher |

## Timeline

```
T+0s:    docker compose restart redis rabbitmq
T+1s:    ⚠️ Connection loss messages appear
T+1-10s: Reconnection attempts with backoff
T+10s:   Infrastructure fully started
T+15s:   ✅/🔄 Success messages appear
T+20s:   Normal operation resumes
```

## Quick Test Commands

```bash
# Start all workers (background)
for worker in manager downloader translator consumer scanner; do
    ./run-worker.sh $worker > /tmp/$worker.log 2>&1 &
done

# Wait for startup
sleep 10

# Restart infrastructure
docker compose restart redis rabbitmq

# Wait for reconnection
sleep 30

# Check for success
grep -h "✅\|🔄" /tmp/*.log | grep -i "reconnect"
```

## Grep Patterns

```bash
# Find all reconnection success messages
grep -E "(✅.*reconnect|🔄.*reconnect)" worker.log

# Find all connection loss warnings
grep "⚠️.*connection lost" worker.log

# Find reconnection attempts in progress
grep "🔄.*Starting.*reconnection" worker.log

# Find failures
grep "❌.*reconnection failed" worker.log

# Timeline view
grep -E "(✅|⚠️|🔄|❌)" worker.log | grep -i "redis\|rabbitmq"
```

## Health Check Intervals

| Service | Check Frequency | Method |
|---------|----------------|--------|
| Redis | Every 30 seconds | Background task + periodic checks |
| RabbitMQ | Every 30 seconds | During message consumption |

## Troubleshooting

### No Success Messages After 60 Seconds

1. Check infrastructure is actually running:
   ```bash
   docker compose ps
   ```

2. Check worker didn't crash:
   ```bash
   ps aux | grep "run-worker"
   ```

3. Check logs for errors:
   ```bash
   tail -n 50 /tmp/worker.log | grep -E "(ERROR|CRITICAL|Traceback)"
   ```

### Partial Reconnections

Some workers reconnected, others didn't:

1. Check which services are actually up:
   ```bash
   nc -zv localhost 6379  # Redis
   nc -zv localhost 5672  # RabbitMQ
   ```

2. Check for port conflicts or networking issues

### Workers Crash During Reconnection

1. Check for stack traces in logs
2. Verify max retries aren't too low
3. Check for application bugs in reconnection code

## Configuration

Adjust retry behavior in `.env`:

```bash
# Redis
REDIS_RECONNECT_MAX_RETRIES=10
REDIS_RECONNECT_INITIAL_DELAY=3.0
REDIS_RECONNECT_MAX_DELAY=30.0
REDIS_HEALTH_CHECK_INTERVAL=30

# RabbitMQ  
RABBITMQ_RECONNECT_MAX_RETRIES=10
RABBITMQ_RECONNECT_INITIAL_DELAY=3.0
RABBITMQ_RECONNECT_MAX_DELAY=30.0
RABBITMQ_HEALTH_CHECK_INTERVAL=30
```

## Emoji Legend

| Emoji | Meaning |
|-------|---------|
| ✅ | Success / Connected |
| ⚠️ | Warning / Connection Lost |
| 🔄 | Reconnecting / Reconnected |
| ❌ | Error / Failed |
| 🔌 | Connecting |
| 🚀 | Starting |
| 👋 | Stopping |

## Files to Check

**Core:**
- `src/common/redis_client.py` - Redis reconnection logic
- `src/common/event_publisher.py` - RabbitMQ reconnection callbacks
- `src/common/connection_utils.py` - Health check utility

**Workers:**
- `src/downloader/worker.py`
- `src/translator/worker.py`
- `src/consumer/worker.py`
- `src/scanner/worker.py`
- `src/manager/event_consumer.py`
- `src/manager/orchestrator.py`

## Success Criteria Checklist

- [ ] All workers start successfully
- [ ] All workers show connection loss warnings
- [ ] All workers show reconnection attempts
- [ ] All workers show ✅/🔄 success messages
- [ ] All workers continue running
- [ ] No manual intervention required
- [ ] Health checks continue working
- [ ] Workers process messages after reconnection

## Getting Help

If reconnection isn't working:

1. Check **RECONNECTION_FIX_SUMMARY.md** for overview
2. Check **TEST_RECONNECTION_CHECKLIST.md** for detailed test steps
3. Check **REDIS_RECONNECTION_LOGGING_COMPLETE.md** for Redis details
4. Check **RECONNECTION_LOGGING_FIX.md** for technical details
5. Check worker logs for specific error messages
6. Verify infrastructure is actually running and accessible

