# How to Verify Reconnection Logging Works

## Quick Test

### Step 1: Start All Workers

Open 5 terminal windows and run:

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

Wait for all workers to start and show they're connected.

### Step 2: Restart Infrastructure

In a new terminal:

```bash
docker compose restart redis rabbitmq
```

### Step 3: Watch for Reconnection Logs

In each worker terminal, you should see:

**During connection loss:**
```
ERROR:aiormq.connection:Unexpected connection close from remote "amqp://guest:******@localhost:5672/", Connection.Close(reply_code=320, reply_text="CONNECTION_FORCED - broker forced connection closure with reason 'shutdown'")
WARNING:aio_pika.robust_connection:Connection attempt to "amqp://guest:******@localhost:5672/" failed: [Errno 61] Connection refused. Reconnecting after 5 seconds.
WARNING:common.redis_client:Redis health check failed, attempting reconnection...
WARNING:common.redis_client:Failed to connect to Redis (attempt 1/10): Connection refused. Retrying in 3.0s...
```

**After successful reconnection:**
```
INFO:common.redis_client:✅ Redis reconnection successful!
INFO:[worker_name]:🔄 [Worker Type] reconnected to RabbitMQ successfully!
```

### Expected Success Messages by Worker

| Worker      | Expected Log Message                                                    |
|-------------|-------------------------------------------------------------------------|
| Manager     | `🔄 Manager event consumer reconnected to RabbitMQ successfully!`       |
|             | `🔄 Orchestrator reconnected to RabbitMQ successfully!`                 |
|             | `🔄 Event publisher reconnected to RabbitMQ successfully!`              |
| Downloader  | `🔄 Downloader worker reconnected to RabbitMQ successfully!`            |
|             | `✅ Redis reconnection successful!`                                     |
| Translator  | `🔄 Translator worker reconnected to RabbitMQ successfully!`            |
|             | `✅ Redis reconnection successful!`                                     |
| Consumer    | `🔄 Consumer worker reconnected to RabbitMQ successfully!`              |
|             | `✅ Redis reconnection successful!`                                     |
| Scanner     | `🔄 Event publisher reconnected to RabbitMQ successfully!`              |
|             | `✅ Redis reconnection successful!`                                     |

## What If Reconnection Doesn't Work?

### No Reconnection Messages Appear

**Possible causes:**
1. Infrastructure didn't restart properly
2. Workers crashed during reconnection
3. Firewall/network issues

**Solution:**
```bash
# Check infrastructure is running
docker compose ps

# Restart infrastructure cleanly
docker compose down
docker compose up -d

# Check logs
docker compose logs redis
docker compose logs rabbitmq
```

### Workers Crash During Reconnection

**Possible causes:**
1. Max retries exceeded
2. Application bug in reconnection logic

**Solution:**
```bash
# Check worker logs for stack traces
# Look for errors before the crash

# Increase retry limits in .env if needed
REDIS_RECONNECT_MAX_RETRIES=20
RABBITMQ_RECONNECT_MAX_RETRIES=20
```

### Connection Refused Persists

**Possible causes:**
1. Redis or RabbitMQ not fully started
2. Port conflicts
3. Docker networking issues

**Solution:**
```bash
# Check if services are listening
nc -zv localhost 6379  # Redis
nc -zv localhost 5672  # RabbitMQ

# Check Docker logs
docker compose logs redis
docker compose logs rabbitmq

# Restart Docker if needed
docker compose restart
```

## Timeline

Typical reconnection timeline:

1. **T=0s**: Infrastructure restart initiated
2. **T=1s**: Connections lost, error messages appear
3. **T=1-5s**: Workers attempt reconnection (with backoff)
4. **T=5-10s**: Infrastructure fully started
5. **T=10-15s**: Workers successfully reconnect
6. **T=15s**: Success messages appear in logs

## Success Criteria

✅ All workers show connection loss warnings  
✅ All workers show retry attempts with exponential backoff  
✅ All workers show success messages after reconnection  
✅ Workers continue processing messages after reconnection  
✅ No manual intervention required  

## Automated Verification Script

Create a test script to automate verification:

```bash
#!/bin/bash
# verify_reconnection.sh

echo "Starting workers in background..."
./run-worker.sh manager > /tmp/manager.log 2>&1 &
sleep 2
./run-worker.sh downloader > /tmp/downloader.log 2>&1 &
./run-worker.sh translator > /tmp/translator.log 2>&1 &
./run-worker.sh consumer > /tmp/consumer.log 2>&1 &
./run-worker.sh scanner > /tmp/scanner.log 2>&1 &

echo "Waiting for workers to start..."
sleep 10

echo "Restarting infrastructure..."
docker compose restart redis rabbitmq

echo "Waiting for reconnection..."
sleep 30

echo "Checking for success messages..."
echo "Manager:"
grep "reconnected to RabbitMQ successfully" /tmp/manager.log

echo "Downloader:"
grep "reconnection successful" /tmp/downloader.log

echo "Translator:"
grep "reconnection successful" /tmp/translator.log

echo "Consumer:"
grep "reconnection successful" /tmp/consumer.log

echo "Scanner:"
grep "reconnection successful" /tmp/scanner.log

echo "Stopping workers..."
pkill -f "run-worker.sh"

echo "Done!"
```

## Next Steps

After verifying reconnection logging works:

1. ✅ Test with actual media files to ensure end-to-end functionality
2. ✅ Test with longer outages (30+ seconds)
3. ✅ Test with multiple infrastructure restarts
4. ✅ Monitor production logs for reconnection patterns
5. ✅ Set up alerts for repeated reconnection failures

