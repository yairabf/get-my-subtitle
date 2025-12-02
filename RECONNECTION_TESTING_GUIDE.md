# Redis and RabbitMQ Reconnection Testing Guide

## Overview

This guide provides step-by-step instructions to test the automatic reconnection functionality for Redis and RabbitMQ across all workers in the subtitle management system.

## Prerequisites

- Docker Compose environment running
- All services started: manager, scanner, downloader, translator, consumer
- Access to Docker CLI to stop/start containers

## Test Scenarios

### 1. Redis Reconnection Test

#### Test 1.1: Redis Crash and Recovery - Downloader Worker

**Steps:**
1. Start all services: `docker-compose up -d`
2. Verify downloader worker is running and processing messages
3. Stop Redis: `docker-compose stop redis`
4. Observe downloader logs - should see:
   - "Redis health check failed"
   - "Redis connection lost, attempting reconnection..."
5. Wait 30 seconds (health check interval)
6. Restart Redis: `docker-compose start redis`
7. Observe downloader logs - should see:
   - "Starting Redis reconnection..."
   - "Connected to Redis successfully"
   - "Redis reconnection successful"
8. Send a test message to verify functionality restored

**Expected Result:** 
- Worker automatically reconnects to Redis
- Message processing resumes without manual intervention
- No data loss or service disruption

#### Test 1.2: Redis Crash and Recovery - Translator Worker

Follow same steps as Test 1.1 but observe translator worker logs.

#### Test 1.3: Redis Crash and Recovery - Consumer Worker

Follow same steps as Test 1.1 but observe consumer worker logs.

#### Test 1.4: Redis Crash and Recovery - Scanner Worker

**Steps:**
1. Start all services
2. Verify scanner worker is running
3. Stop Redis: `docker-compose stop redis`
4. Wait for health check cycle (30 seconds)
5. Restart Redis: `docker-compose start redis`
6. Add a new media file to trigger scanning
7. Verify event is published successfully

**Expected Result:**
- Scanner automatically reconnects
- Events are published successfully after reconnection

### 2. RabbitMQ Reconnection Test

#### Test 2.1: RabbitMQ Crash and Recovery - Downloader Worker

**Steps:**
1. Start all services: `docker-compose up -d`
2. Verify downloader worker is consuming messages
3. Stop RabbitMQ: `docker-compose stop rabbitmq`
4. Observe downloader logs - should see:
   - "RabbitMQ connection lost, reconnecting..."
   - "Error in consumer (failure #1)"
5. Restart RabbitMQ: `docker-compose start rabbitmq`
6. Wait for reconnection (initial delay: 3s, exponential backoff)
7. Observe downloader logs - should see:
   - "Connecting to RabbitMQ..."
   - "Connected to RabbitMQ successfully"
   - "Starting to consume messages..."
8. Enqueue a test download task
9. Verify message is processed successfully

**Expected Result:**
- Worker automatically reconnects to RabbitMQ
- Message consumption resumes
- Exponential backoff prevents connection spam

#### Test 2.2: RabbitMQ Crash and Recovery - Translator Worker

Follow same steps as Test 2.1 but observe translator worker logs and enqueue translation task.

#### Test 2.3: RabbitMQ Crash and Recovery - Consumer Worker

**Steps:**
1. Start all services
2. Stop RabbitMQ: `docker-compose stop rabbitmq`
3. Observe consumer worker logs
4. Restart RabbitMQ: `docker-compose start rabbitmq`
5. Verify consumer reconnects and processes events

#### Test 2.4: Event Publisher Reconnection

**Steps:**
1. Start all services
2. Stop RabbitMQ: `docker-compose stop rabbitmq`
3. Trigger an event (e.g., via scanner or manager API)
4. Observe event publisher logs - should see:
   - "Failed to publish event..."
   - "Attempting to reconnect and retry event publishing..."
5. Restart RabbitMQ: `docker-compose start rabbitmq`
6. Verify event publisher reconnects and publishes pending event

**Expected Result:**
- Event publisher automatically reconnects
- Failed events are retried once after reconnection

### 3. Combined Failure Test

#### Test 3.1: Both Redis and RabbitMQ Crash

**Steps:**
1. Start all services
2. Stop both Redis and RabbitMQ simultaneously:
   ```bash
   docker-compose stop redis rabbitmq
   ```
3. Observe all worker logs
4. Restart both services:
   ```bash
   docker-compose start redis rabbitmq
   ```
5. Verify all workers reconnect successfully
6. Test end-to-end workflow (scan → download → translate)

**Expected Result:**
- All workers reconnect to both services
- System resumes normal operation
- No manual intervention required

### 4. Exponential Backoff Test

#### Test 4.1: Verify Exponential Backoff

**Steps:**
1. Start downloader worker
2. Stop RabbitMQ
3. Observe reconnection attempts in logs
4. Measure delays between reconnection attempts:
   - Attempt 1: ~3s delay
   - Attempt 2: ~6s delay
   - Attempt 3: ~12s delay
   - Attempt 4: ~24s delay
   - Attempt 5+: ~30s delay (capped at max_delay)

**Expected Result:**
- Reconnection delays increase exponentially
- Delays are capped at 30 seconds (max_delay)
- After 3 consecutive failures, delay increases further

### 5. Long-Running Stability Test

#### Test 5.1: Repeated Crash/Recovery Cycles

**Steps:**
1. Start all services
2. Run a script to repeatedly crash and restart services:
   ```bash
   for i in {1..10}; do
     echo "Cycle $i: Stopping services..."
     docker-compose stop redis rabbitmq
     sleep 10
     echo "Cycle $i: Starting services..."
     docker-compose start redis rabbitmq
     sleep 30
   done
   ```
3. Monitor worker logs throughout the test
4. Verify workers reconnect successfully after each cycle

**Expected Result:**
- Workers reconnect reliably across multiple crash/recovery cycles
- No memory leaks or degraded performance
- System remains stable

## Test Commands

### Manual Testing Commands

```bash
# Start services
docker-compose up -d

# View logs for specific worker
docker-compose logs -f downloader
docker-compose logs -f translator
docker-compose logs -f consumer
docker-compose logs -f scanner
docker-compose logs -f manager

# Stop Redis
docker-compose stop redis

# Start Redis
docker-compose start redis

# Stop RabbitMQ
docker-compose stop rabbitmq

# Start RabbitMQ
docker-compose start rabbitmq

# Stop both
docker-compose stop redis rabbitmq

# Start both
docker-compose start redis rabbitmq

# Restart all services
docker-compose restart

# View all logs
docker-compose logs -f
```

### Test Message Commands

```bash
# Test download request (via manager API)
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "test.mp4",
    "video_title": "Test Video",
    "language": "en",
    "preferred_sources": ["opensubtitles"]
  }'

# Trigger manual scan
curl -X POST http://localhost:8000/scan

# Check queue status
curl http://localhost:8000/queue/status
```

## Success Criteria

### For Each Worker:

✅ **Reconnection:**
- Automatically reconnects when Redis restarts
- Automatically reconnects when RabbitMQ restarts
- No manual intervention required

✅ **Logging:**
- Clear log messages indicating connection loss
- Clear log messages indicating reconnection attempts
- Clear log messages indicating successful reconnection

✅ **Functionality:**
- Message processing resumes after reconnection
- No messages are lost during reconnection
- System performance is not degraded

✅ **Backoff:**
- Exponential backoff is applied correctly
- Maximum delay is respected (30s)
- Backoff resets after successful connection

## Configuration Values

Default reconnection settings (can be overridden via environment variables):

```bash
# Redis
REDIS_HEALTH_CHECK_INTERVAL=30          # seconds
REDIS_RECONNECT_MAX_RETRIES=10          # attempts
REDIS_RECONNECT_INITIAL_DELAY=3.0       # seconds
REDIS_RECONNECT_MAX_DELAY=30.0          # seconds

# RabbitMQ
RABBITMQ_HEALTH_CHECK_INTERVAL=30       # seconds
RABBITMQ_RECONNECT_MAX_RETRIES=10       # attempts
RABBITMQ_RECONNECT_INITIAL_DELAY=3.0    # seconds
RABBITMQ_RECONNECT_MAX_DELAY=30.0       # seconds
```

## Troubleshooting

### Issue: Worker doesn't reconnect

**Check:**
1. Verify services are actually restarted: `docker-compose ps`
2. Check worker logs for error messages
3. Verify network connectivity: `docker-compose exec downloader ping redis`
4. Check configuration values are loaded correctly

### Issue: Connection spam (too many reconnection attempts)

**Solution:**
- Verify exponential backoff is working correctly
- Increase `RECONNECT_INITIAL_DELAY` or `RECONNECT_MAX_DELAY`
- Check for infinite loop in reconnection logic

### Issue: Messages are lost during reconnection

**Check:**
1. Verify RabbitMQ message acknowledgement is working
2. Check if messages are properly nacked/rejected during shutdown
3. Verify queue durability settings

## Monitoring

### Key Metrics to Monitor:

1. **Connection Status:**
   - Redis connection health
   - RabbitMQ connection health
   - Event publisher connection health

2. **Reconnection Metrics:**
   - Number of reconnection attempts
   - Time to successful reconnection
   - Frequency of connection failures

3. **Performance Metrics:**
   - Message processing throughput
   - Message latency
   - Queue depth

4. **Error Rates:**
   - Connection failures per hour
   - Failed reconnection attempts
   - Message processing errors

## Next Steps

After completing all tests:

1. Document any issues found
2. Verify all success criteria are met
3. Update environment variables if needed
4. Consider adding automated reconnection tests to CI/CD pipeline
5. Set up monitoring alerts for connection failures in production
