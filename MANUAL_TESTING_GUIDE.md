# Manual Testing Guide for Subtitle Management System

## Overview

This guide will walk you through manually testing the event-driven subtitle management system. We'll test all major flows, verify event publishing, check Redis state, and validate the entire workflow.

---

## Prerequisites

### 1. Environment Setup

```bash
# Ensure you have .env file
cp env.template .env

# Edit .env and add your API keys (if needed for real testing)
# For basic testing, default values work fine
```

### 2. Clean Start

```bash
# Stop any running containers
docker-compose down -v

# Clean up Docker resources
docker system prune -f

# Remove old logs
rm -rf logs/*
```

---

## Test Plan

We'll test these scenarios:
1. ✅ **Infrastructure Health Check** - Verify all services start correctly
2. ✅ **Subtitle Download Flow** - Test successful subtitle download
3. ✅ **Translation Flow** - Test subtitle not found → translation
4. ✅ **Error Handling** - Test failure scenarios
5. ✅ **Event History** - Verify event tracking works
6. ✅ **RabbitMQ Integration** - Check event publishing
7. ✅ **Redis State** - Verify state management

---

## Test 1: Infrastructure Health Check

### Start All Services

```bash
# Build and start all services
docker-compose up --build -d

# This will start:
# - Redis (port 6379)
# - RabbitMQ (ports 5672, 15672)
# - Manager API (port 8000)
# - Downloader Worker
# - Translator Worker
# - Consumer Service
```

### Check Service Status

```bash
# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Expected output: All services should show "healthy" or "Up"
```

### Verify Each Service

```bash
# Check Manager API health
curl http://localhost:8000/health

# Expected: {"status": "ok"}

# Check RabbitMQ Management UI
open http://localhost:15672
# Login: guest / guest
# Verify: Exchange "subtitle.events" exists

# Check Redis
docker exec -it get-my-subtitle-redis-1 redis-cli ping
# Expected: PONG
```

### View Logs

```bash
# View all logs
docker-compose logs -f

# Or view specific services
docker-compose logs -f manager
docker-compose logs -f downloader
docker-compose logs -f translator
docker-compose logs -f consumer
```

**✅ Expected Results:**
- All services start without errors
- Health checks pass
- RabbitMQ exchange created
- Redis connection successful
- No error messages in logs

---

## Test 2: Subtitle Download Flow (Subtitle Found)

This tests the happy path where the subtitle is found immediately.

### Submit Download Request

```bash
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "video_title": "Test Video",
    "language": "he",
    "preferred_sources": ["opensubtitles"]
  }'
```

**Expected Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "DOWNLOAD_QUEUED",
  "message": "Download job queued successfully"
}
```

**Save the job_id for next steps!**

### Check Job Status

```bash
# Replace {job_id} with actual job ID
curl http://localhost:8000/subtitles/{job_id}/status

# Check every 2-3 seconds
watch -n 2 'curl -s http://localhost:8000/subtitles/{job_id}/status | jq'
```

**Expected Status Progression:**
1. `DOWNLOAD_QUEUED` → Initial state
2. `DOWNLOAD_IN_PROGRESS` → Downloader processing
3. `DONE` → Subtitle found and downloaded (90% probability)

OR

1. `DOWNLOAD_QUEUED` → Initial state
2. `DOWNLOAD_IN_PROGRESS` → Downloader processing
3. `TRANSLATE_QUEUED` → Subtitle not found, needs translation (10% probability)
4. `TRANSLATE_IN_PROGRESS` → Translator processing
5. `DONE` → Translation completed

### Check Event History

```bash
curl http://localhost:8000/subtitles/{job_id}/events | jq
```

**Expected Events (Subtitle Found):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_count": 2,
  "events": [
    {
      "event_type": "subtitle.ready",
      "timestamp": "2025-10-29T10:05:00Z",
      "source": "downloader",
      "payload": {
        "job_id": "...",
        "download_url": "https://example.com/subtitle.srt",
        "language": "he"
      }
    },
    {
      "event_type": "subtitle.download.requested",
      "timestamp": "2025-10-29T10:04:58Z",
      "source": "manager",
      "payload": {
        "job_id": "...",
        "video_url": "https://example.com/video.mp4",
        "language": "he"
      }
    }
  ]
}
```

### Monitor Logs

```bash
# In separate terminal, watch logs
docker-compose logs -f downloader consumer

# Look for:
# - "Processing download task"
# - "Subtitle found and downloaded"
# - "Published subtitle.ready event"
# - "RECEIVED EVENT: subtitle.ready"
# - "Updated job status to DONE"
```

**✅ Expected Results:**
- Job progresses through statuses correctly
- Events are published and recorded
- Consumer processes events
- Final status is DONE
- Event history shows complete timeline

---

## Test 3: Translation Flow (Subtitle Not Found)

If Test 2 resulted in immediate download (90% chance), run another job to trigger translation (keep trying until you get the 10% case).

### Submit Another Request

```bash
# Submit multiple requests if needed
for i in {1..5}; do
  curl -X POST http://localhost:8000/subtitles/download \
    -H "Content-Type: application/json" \
    -d "{
      \"video_url\": \"https://example.com/video$i.mp4\",
      \"video_title\": \"Test Video $i\",
      \"language\": \"he\",
      \"preferred_sources\": [\"opensubtitles\"]
    }"
  echo ""
  sleep 1
done
```

### Monitor for Translation Flow

```bash
# Check all jobs
docker-compose logs -f downloader | grep "not found"

# When you see "Subtitle not found" message:
# - Get the job_id from logs
# - Check its status
curl http://localhost:8000/subtitles/{job_id}/status
```

**Expected Status Progression:**
1. `DOWNLOAD_QUEUED`
2. `DOWNLOAD_IN_PROGRESS`
3. `TRANSLATE_QUEUED` ← Key difference!
4. `TRANSLATE_IN_PROGRESS`
5. `DONE`

### Check Event History

```bash
curl http://localhost:8000/subtitles/{job_id}/events | jq
```

**Expected Events (Translation Flow):**
```json
{
  "job_id": "...",
  "event_count": 3,
  "events": [
    {
      "event_type": "subtitle.translated",
      "timestamp": "2025-10-29T10:10:00Z",
      "source": "translator",
      "payload": {
        "job_id": "...",
        "source_language": "en",
        "target_language": "he"
      }
    },
    {
      "event_type": "subtitle.translate.requested",
      "timestamp": "2025-10-29T10:09:30Z",
      "source": "downloader",
      "payload": {
        "job_id": "...",
        "reason": "subtitle_not_found"
      }
    },
    {
      "event_type": "subtitle.download.requested",
      "timestamp": "2025-10-29T10:09:00Z",
      "source": "manager",
      "payload": {
        "job_id": "...",
        "video_url": "..."
      }
    }
  ]
}
```

**✅ Expected Results:**
- Job transitions through download → translation → done
- Three events recorded in correct order
- Translator worker processes the task
- Consumer updates status correctly

---

## Test 4: RabbitMQ Event Verification

Let's directly inspect RabbitMQ to verify events are being published.

### Access RabbitMQ Management UI

```bash
# Open in browser
open http://localhost:15672

# Login: guest / guest
```

### Verify Exchange

1. Click **Exchanges** tab
2. Find `subtitle.events`
3. Should show:
   - Type: `topic`
   - Features: `D` (Durable)
   - Message rate showing activity

### Verify Queue

1. Click **Queues** tab
2. Find `subtitle.events.consumer`
3. Should show:
   - Messages: 0 (if consumer is processing)
   - Message rate showing activity
   - Consumers: 1 (consumer service connected)

### Verify Bindings

1. Click on `subtitle.events.consumer` queue
2. Scroll to **Bindings**
3. Should see bindings:
   - `subtitle.*` → routes all subtitle events
   - `job.*` → routes all job events

### Publish Test Event (Manual)

1. Click **Exchanges** tab
2. Click `subtitle.events`
3. Scroll to **Publish message**
4. Set:
   - Routing key: `test.event`
   - Payload: `{"test": "manual event"}`
5. Click **Publish message**

**Check consumer logs:**
```bash
docker-compose logs consumer | grep "test.event"
# Should see: "RECEIVED EVENT: test.event"
```

**✅ Expected Results:**
- Exchange exists and is active
- Queue has consumer connected
- Bindings are correct
- Events are routing properly
- Consumer processes events

---

## Test 5: Redis State Verification

Let's directly inspect Redis to verify state management.

### Access Redis CLI

```bash
# Enter Redis container
docker exec -it get-my-subtitle-redis-1 redis-cli

# Or use one-liner
docker exec -it get-my-subtitle-redis-1 redis-cli
```

### Check Job Keys

```redis
# List all job keys
KEYS job:*

# Example output:
# 1) "job:550e8400-e29b-41d4-a716-446655440000"
# 2) "job:events:550e8400-e29b-41d4-a716-446655440000"
# 3) "job:660e8400-e29b-41d4-a716-446655440001"
```

### Inspect Job Data

```redis
# Get job details (replace with actual job_id)
GET job:550e8400-e29b-41d4-a716-446655440000

# Should return JSON like:
# {
#   "job_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "DONE",
#   "video_url": "https://example.com/video.mp4",
#   "language": "he",
#   "created_at": "2025-10-29T10:04:58Z",
#   "updated_at": "2025-10-29T10:05:00Z"
# }
```

### Check Event History

```redis
# Get event count
LLEN job:events:550e8400-e29b-41d4-a716-446655440000

# Get all events (newest first)
LRANGE job:events:550e8400-e29b-41d4-a716-446655440000 0 -1

# Each event should be JSON with:
# - event_type
# - timestamp
# - source
# - payload
```

### Check TTL

```redis
# Check TTL on completed job
TTL job:550e8400-e29b-41d4-a716-446655440000

# Should return seconds (604800 = 7 days for completed jobs)
```

### Exit Redis CLI

```redis
EXIT
```

**✅ Expected Results:**
- Job keys exist in Redis
- Job data contains complete information
- Event history stored as Redis list
- TTL set correctly based on job status
- Data structure matches schemas

---

## Test 6: Error Handling

Let's test how the system handles errors.

### Test Invalid Job ID

```bash
# Try to get status of non-existent job
curl http://localhost:8000/subtitles/00000000-0000-0000-0000-000000000000/status

# Expected: 404 Not Found
```

### Test Invalid Job Events

```bash
# Try to get events of non-existent job
curl http://localhost:8000/subtitles/00000000-0000-0000-0000-000000000000/events

# Expected: 404 Not Found
```

### Test Invalid Request Body

```bash
# Missing required fields
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4"
  }'

# Expected: 422 Validation Error
```

**✅ Expected Results:**
- Proper error responses
- Meaningful error messages
- No service crashes
- Logs show error handling

---

## Test 7: Service Resilience

Test how the system handles service failures.

### Test RabbitMQ Down

```bash
# Stop RabbitMQ
docker-compose stop rabbitmq

# Submit a job
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "video_title": "Test Video",
    "language": "he",
    "preferred_sources": ["opensubtitles"]
  }'

# Check logs - should see "mock mode" messages
docker-compose logs manager | grep -i "mock"

# Restart RabbitMQ
docker-compose start rabbitmq
```

**✅ Expected Results:**
- System continues to function
- Workers fall back to mock mode
- Jobs still process (via direct queue)
- No crashes

### Test Redis Down

```bash
# Stop Redis
docker-compose stop redis

# Try to submit job
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "video_title": "Test Video",
    "language": "he",
    "preferred_sources": ["opensubtitles"]
  }'

# Should return error (Redis required for state)

# Restart Redis
docker-compose start redis
```

**✅ Expected Results:**
- Graceful error handling
- Meaningful error messages
- Services reconnect when Redis comes back

---

## Test 8: End-to-End Complete Flow

Let's run a complete workflow and verify everything works together.

### Step 1: Submit Job

```bash
# Submit new job
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/final-test.mp4",
    "video_title": "Final Test Video",
    "language": "he",
    "preferred_sources": ["opensubtitles"]
  }')

# Extract job_id
JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"
```

### Step 2: Monitor Progress

```bash
# Watch status changes
while true; do
  STATUS=$(curl -s http://localhost:8000/subtitles/$JOB_ID/status | jq -r '.status')
  echo "$(date): Status = $STATUS"
  
  if [ "$STATUS" == "DONE" ] || [ "$STATUS" == "FAILED" ]; then
    break
  fi
  
  sleep 2
done
```

### Step 3: Verify Final State

```bash
# Get final status
curl http://localhost:8000/subtitles/$JOB_ID/status | jq

# Get event history
curl http://localhost:8000/subtitles/$JOB_ID/events | jq

# Check Redis
docker exec -it get-my-subtitle-redis-1 redis-cli GET "job:$JOB_ID" | jq

# Check event count
docker exec -it get-my-subtitle-redis-1 redis-cli LLEN "job:events:$JOB_ID"
```

### Step 4: Verify Logs

```bash
# Check all services processed the job
docker-compose logs | grep $JOB_ID

# Should see messages from:
# - manager: "Created new job"
# - downloader: "Processing download task"
# - downloader: "Published subtitle.ready" or "Published subtitle.translate.requested"
# - translator: (if translation needed) "Processing translation task"
# - consumer: "RECEIVED EVENT"
# - consumer: "Updated job status"
```

**✅ Expected Results:**
- Job completes successfully
- All events recorded
- Logs show complete flow
- Redis state is correct
- RabbitMQ routed events properly
- Consumer processed all events

---

## Test 9: Performance & Scale

### Test Multiple Concurrent Jobs

```bash
# Submit 10 jobs simultaneously
for i in {1..10}; do
  curl -X POST http://localhost:8000/subtitles/download \
    -H "Content-Type: application/json" \
    -d "{
      \"video_url\": \"https://example.com/video$i.mp4\",
      \"video_title\": \"Load Test Video $i\",
      \"language\": \"he\",
      \"preferred_sources\": [\"opensubtitles\"]
    }" &
done
wait

echo "10 jobs submitted"
```

### Monitor Queue Depths

```bash
# Check RabbitMQ queue
open http://localhost:15672
# Navigate to Queues → subtitle.events.consumer
# Check "Messages" and "Message rate"

# Check logs for processing
docker-compose logs -f consumer | grep "RECEIVED EVENT"
```

### Check Processing Times

```bash
# View consumer logs for timing
docker-compose logs consumer | grep "Updated job"

# All jobs should complete within reasonable time
```

**✅ Expected Results:**
- System handles concurrent jobs
- Queue doesn't back up excessively
- All jobs complete successfully
- No errors or crashes
- Event ordering preserved per job

---

## Debugging Tips

### Common Issues

#### Services Not Starting
```bash
# Check for port conflicts
lsof -i :8000  # Manager API
lsof -i :5672  # RabbitMQ
lsof -i :6379  # Redis

# Check Docker resources
docker system df
docker system prune -f
```

#### Events Not Being Consumed
```bash
# Check consumer is running
docker-compose ps consumer

# Check consumer logs for errors
docker-compose logs consumer

# Check RabbitMQ connection
docker-compose logs consumer | grep -i "connection"

# Restart consumer
docker-compose restart consumer
```

#### Jobs Stuck in Progress
```bash
# Check worker logs
docker-compose logs downloader
docker-compose logs translator

# Check RabbitMQ queues
open http://localhost:15672

# Restart workers
docker-compose restart downloader translator
```

#### Redis Connection Issues
```bash
# Test Redis connection
docker exec -it get-my-subtitle-redis-1 redis-cli ping

# Check Redis logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis
```

### Useful Commands

```bash
# View all container logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f [service_name]

# Check container health
docker-compose ps

# Restart specific service
docker-compose restart [service_name]

# Rebuild specific service
docker-compose up --build -d [service_name]

# Clean restart everything
docker-compose down -v
docker-compose up --build -d

# Access container shell
docker-compose exec [service_name] /bin/sh

# View Redis data
docker exec -it get-my-subtitle-redis-1 redis-cli

# Check RabbitMQ
open http://localhost:15672
```

---

## Test Checklist

Use this checklist to track your testing progress:

- [ ] **Infrastructure**
  - [ ] All services start successfully
  - [ ] Health checks pass
  - [ ] RabbitMQ exchange created
  - [ ] Redis connection works

- [ ] **Download Flow**
  - [ ] Job submitted successfully
  - [ ] Status progresses correctly
  - [ ] Events published to RabbitMQ
  - [ ] Consumer processes events
  - [ ] Final status is DONE

- [ ] **Translation Flow**
  - [ ] Job transitions to translation
  - [ ] Translator processes task
  - [ ] Translation event published
  - [ ] Final status is DONE

- [ ] **Event System**
  - [ ] Events stored in Redis
  - [ ] Event history endpoint works
  - [ ] Events in correct order
  - [ ] All event types present

- [ ] **RabbitMQ**
  - [ ] Exchange exists
  - [ ] Queue created
  - [ ] Bindings correct
  - [ ] Consumer connected
  - [ ] Events routing properly

- [ ] **Redis**
  - [ ] Job data stored correctly
  - [ ] Event history in lists
  - [ ] TTL set correctly
  - [ ] Data structure valid

- [ ] **Error Handling**
  - [ ] Invalid job ID returns 404
  - [ ] Invalid request returns 422
  - [ ] Services handle failures gracefully
  - [ ] Meaningful error messages

- [ ] **Resilience**
  - [ ] Survives RabbitMQ restart
  - [ ] Handles Redis issues
  - [ ] Mock mode works
  - [ ] Services reconnect

- [ ] **Performance**
  - [ ] Handles concurrent jobs
  - [ ] Queue processing efficient
  - [ ] No memory leaks
  - [ ] Logs reasonable size

---

## Success Criteria

Your system is working correctly if:

✅ All services start and stay healthy  
✅ Jobs progress through states correctly  
✅ Events are published to RabbitMQ  
✅ Consumer processes events  
✅ Redis stores job state and events  
✅ Event history API works  
✅ Both download and translation flows work  
✅ Error handling is graceful  
✅ System is resilient to failures  
✅ Concurrent jobs are handled  

---

## Next Steps After Testing

Once manual testing passes:

1. **Document Issues**: Note any bugs or unexpected behavior
2. **Run Automated Tests**: `make test-cov`
3. **Review Logs**: Check for warnings or errors
4. **Optimize**: Identify performance bottlenecks
5. **Security**: Review error messages for information leakage
6. **Monitoring**: Set up metrics and alerting
7. **Production**: Deploy with confidence!

---

## Support

If you encounter issues:

1. Check logs: `docker-compose logs [service]`
2. Verify health: `invoke health`
3. Check RabbitMQ UI: http://localhost:15672
4. Inspect Redis: `invoke redis-cli`
5. Review documentation: `README.md`, `EVENT_DRIVEN_ARCHITECTURE.md`

Happy testing! 🚀

