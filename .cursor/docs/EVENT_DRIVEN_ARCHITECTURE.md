# Event-Driven Architecture

This document explains the event-driven orchestration system implemented for the subtitle management platform.

## Overview

The system uses RabbitMQ topic exchanges to decouple workers from state management, providing better observability, auditability, and scalability.

## Architecture Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /subtitles/download
       ▼
┌─────────────┐
│   Manager   │────────┐
│   (FastAPI) │        │ Publishes to topic exchange
└──────┬──────┘        │ "subtitle.events"
       │               │
       │ Publishes to  ▼
       │ work queue   ┌──────────────────────┐
       ▼              │   RabbitMQ Topic     │
┌─────────────┐       │     Exchange         │
│ Downloader  │       │ (subtitle.events)    │
│   Worker    │       └─────┬────────────────┘
└──────┬──────┘             │
       │                    │ Routing keys:
       │ Publishes events   │ - subtitle.*
       │                    │ - job.*
       ▼                    │
┌──────────────────────┐    │
│   RabbitMQ Topic     │◄───┘
│     Exchange         │
│ (subtitle.events)    │
└─────┬────────────────┘
      │
      │ Routes events to bound queues
      ▼
┌─────────────┐
│  Consumer   │──────► Redis (Update Status)
│   Service   │──────► Redis (Record Events)
└─────────────┘
```

## Key Components

### 1. Event Publisher (`common/event_publisher.py`)

Reusable utility for publishing events to the topic exchange.

**Features:**
- Connects to RabbitMQ topic exchange
- Publishes events with routing keys
- Handles connection failures gracefully (mock mode)
- Persists events with durable messages

**Usage:**
```python
from common.event_publisher import event_publisher
from common.schemas import SubtitleEvent, EventType

# Publish an event
event = SubtitleEvent(
    event_type=EventType.SUBTITLE_READY,
    job_id=request_id,
    timestamp=DateTimeUtils.get_current_utc_datetime(),
    source="downloader",
    payload={
        "subtitle_path": "/path/to/subtitle.srt",
        "download_url": "https://example.com/subtitle.srt"
    }
)
await event_publisher.publish_event(event)
```

### 2. Event Consumer (`consumer/worker.py`)

Dedicated service that consumes events and updates job states.

**Responsibilities:**
- Listen to all `subtitle.*` and `job.*` events
- Update job statuses in Redis based on events
- Record complete event history for audit trail
- Provide centralized state management

**Event Handlers:**
- `handle_subtitle_ready` - Marks job as DONE
- `handle_subtitle_translated` - Marks job as DONE
- `handle_job_failed` - Marks job as FAILED
- `handle_download_requested` - Records event (status already updated by manager)
- `handle_translate_requested` - Records event (status already updated by manager)

### 3. Enhanced Redis Client (`common/redis_client.py`)

Extended with event-related methods:

**New Methods:**
- `update_phase(job_id, status, source, metadata)` - Update status with source tracking
- `record_event(job_id, event_type, payload, source)` - Store event in history
- `get_job_events(job_id, limit)` - Retrieve event history

**Storage Pattern:**
- Jobs: `job:{job_id}` (hash)
- Events: `job:events:{job_id}` (list, most recent first)

### 4. Event Schemas (`common/schemas.py`)

**New Status Enums:**
```python
class SubtitleStatus(str, Enum):
    PENDING = "pending"
    DOWNLOAD_QUEUED = "download_queued"
    DOWNLOAD_IN_PROGRESS = "download_in_progress"
    TRANSLATE_QUEUED = "translate_queued"
    TRANSLATE_IN_PROGRESS = "translate_in_progress"
    DONE = "done"
    FAILED = "failed"
```

**Event Types:**
```python
class EventType(str, Enum):
    SUBTITLE_DOWNLOAD_REQUESTED = "subtitle.download.requested"
    SUBTITLE_READY = "subtitle.ready"
    SUBTITLE_TRANSLATE_REQUESTED = "subtitle.translate.requested"
    SUBTITLE_TRANSLATED = "subtitle.translated"
    JOB_FAILED = "job.failed"
```

## Event Flows

### Flow 1: Subtitle Download (Found)

```
1. Client → Manager: POST /subtitles/download (target=he)
2. Manager → Redis: status = DOWNLOAD_QUEUED
3. Manager → RabbitMQ: publish(subtitle.download.requested)
4. Consumer → consumes event → Records in history

5. Downloader → consumes from work queue
6. Downloader → Redis: status = DOWNLOAD_IN_PROGRESS
7. Downloader → tries to fetch Hebrew subtitle
8. Downloader → RabbitMQ: publish(subtitle.ready)

9. Consumer → consumes event → Redis: status = DONE
10. Consumer → Records event in history
```

### Flow 2: Subtitle Download (Not Found, Needs Translation)

```
1-7. (Same as Flow 1)
8. Downloader → subtitle not found, downloads English fallback
9. Downloader → RabbitMQ: publish(subtitle.translate.requested)
10. Downloader → enqueues translation task

11. Consumer → consumes event → Records in history

12. Translator → consumes from translation queue
13. Translator → Redis: status = TRANSLATE_IN_PROGRESS
14. Translator → translates subtitle
15. Translator → RabbitMQ: publish(subtitle.translated)

16. Consumer → consumes event → Redis: status = DONE
17. Consumer → Records event in history
```

### Flow 3: Job Failure

```
1-5. (Any flow starts)
6. Worker → encounters error
7. Worker → RabbitMQ: publish(job.failed, error_message="...")

8. Consumer → consumes event → Redis: status = FAILED
9. Consumer → Records event with error details
```

## Workflow States

### State Transitions

```
PENDING
  ↓
DOWNLOAD_QUEUED (manager publishes to queue)
  ↓
DOWNLOAD_IN_PROGRESS (downloader starts processing)
  ↓
  ├─→ DONE (subtitle found)
  │
  └─→ TRANSLATE_QUEUED (subtitle not found)
       ↓
       TRANSLATE_IN_PROGRESS (translator starts)
       ↓
       DONE (translation complete)

At any point:
  ↓
FAILED (error occurs)
```

## Benefits

### 1. Decoupling

- Workers publish events without knowing who consumes them
- Consumer manages state without workers needing direct Redis access
- Clean separation of concerns

### 2. Observability

- Complete event history for debugging
- Timeline of what happened and when
- Source tracking (which service did what)

### 3. Auditability

- Immutable event log
- Can replay events for analysis
- Compliance and debugging

### 4. Extensibility

- Easy to add new event consumers (metrics, notifications, etc.)
- Workers don't change when adding new consumers
- Flexible routing with topic exchange

### 5. Reliability

- Events are durable in RabbitMQ
- Can handle temporary service outages
- Messages aren't lost

## RabbitMQ Configuration

### Exchange

- **Name**: `subtitle.events`
- **Type**: `topic`
- **Durable**: `true`

### Routing Keys

Events are published with routing keys matching their event type:
- `subtitle.download.requested`
- `subtitle.ready`
- `subtitle.translate.requested`
- `subtitle.translated`
- `job.failed`

### Topic Patterns

Consumers bind with patterns to receive specific events:
- `subtitle.*` - All subtitle events
- `job.*` - All job events
- `#` - All events (for logging/metrics)

## API Enhancements

### New Endpoint: GET /subtitles/{job_id}/events

Retrieve complete event history for a job:

```bash
curl http://localhost:8000/subtitles/{job_id}/events
```

**Response:**
```json
{
  "job_id": "abc-123",
  "event_count": 4,
  "events": [
    {
      "event_type": "subtitle.translated",
      "timestamp": "2024-01-01T00:05:00Z",
      "source": "translator",
      "payload": {
        "translated_path": "/subtitles/translated.srt",
        "download_url": "https://example.com/subtitle.srt"
      }
    },
    {
      "event_type": "subtitle.translate.requested",
      "timestamp": "2024-01-01T00:02:00Z",
      "source": "downloader",
      "payload": {
        "subtitle_file_path": "/subtitles/fallback.srt",
        "source_language": "en",
        "target_language": "he"
      }
    },
    {
      "event_type": "subtitle.download.requested",
      "timestamp": "2024-01-01T00:00:00Z",
      "source": "manager",
      "payload": {
        "video_url": "https://example.com/video.mp4",
        "language": "he"
      }
    }
  ]
}
```

## Testing

### Unit Tests

- `tests/common/test_event_publisher.py` - Event publishing logic
- `tests/common/test_redis_enhancements.py` - Redis event methods

### Integration Tests

Test complete event flows:

```python
# Submit job
response = client.post("/subtitles/download", json={...})
job_id = response.json()["id"]

# Wait for processing
await asyncio.sleep(5)

# Check event history
events_response = client.get(f"/subtitles/{job_id}/events")
events = events_response.json()["events"]

# Verify event sequence
assert events[0]["event_type"] == "subtitle.ready"
assert events[1]["event_type"] == "subtitle.download.requested"
```

## Deployment

### Docker Compose

All services are configured in `docker-compose.yml`:

```bash
# Start all services
docker-compose up -d

# View consumer logs
docker-compose logs -f consumer

# Scale consumer for higher throughput
docker-compose up -d --scale consumer=3
```

### Service Dependencies

```
redis ─┐
       ├─→ manager ─┐
rabbitmq ┘          ├─→ downloader
                    ├─→ translator
                    └─→ consumer
```

## Monitoring

### Event Processing

Monitor consumer logs for event flow:

```bash
docker-compose logs -f consumer | grep "RECEIVED EVENT"
```

### Event History

Check event counts per job:

```bash
redis-cli LLEN "job:events:{job-id}"
```

### Queue Depth

Monitor RabbitMQ management UI:

```
http://localhost:15672
```

## Future Enhancements

### Potential Additions

1. **Dead Letter Queue** - Handle permanently failed events
2. **Event Replay** - Replay events for debugging or recovery
3. **Metrics Consumer** - Dedicated consumer for metrics collection
4. **Notification Consumer** - Send notifications on job completion
5. **Event Filtering** - Advanced routing based on event content
6. **Event Versioning** - Support schema evolution
7. **Event Compression** - Compress large payloads
8. **Event Encryption** - Encrypt sensitive event data

## Troubleshooting

### Events Not Being Consumed

1. Check consumer is running:
   ```bash
   docker-compose ps consumer
   ```

2. Check exchange and bindings:
   ```bash
   curl -u guest:guest http://localhost:15672/api/exchanges/%2F/subtitle.events
   ```

3. Check consumer logs:
   ```bash
   docker-compose logs -f consumer
   ```

### Events Not Being Recorded

1. Check Redis connection:
   ```bash
   redis-cli ping
   ```

2. Check event history:
   ```bash
   redis-cli LRANGE "job:events:{job-id}" 0 -1
   ```

### Status Not Updating

1. Verify consumer is processing events (check logs)
2. Verify job exists in Redis
3. Check for errors in consumer logs
4. Verify Redis connectivity from consumer

## Best Practices

### Event Publishing

1. Always include complete context in payload
2. Use descriptive event types
3. Include timestamps
4. Tag events with source service

### Event Consumption

1. Acknowledge messages only after successful processing
2. Log all events for debugging
3. Handle errors gracefully
4. Record events even if status update fails

### State Management

1. Use `update_phase` for status updates with source tracking
2. Always record events in history
3. Include metadata in updates
4. Handle concurrent updates carefully

## Migration Guide

### From Direct Redis Updates

Old pattern:
```python
await redis_client.update_job_status(
    job_id, SubtitleStatus.COMPLETED
)
```

New pattern:
```python
# Publish event
event = SubtitleEvent(
    event_type=EventType.SUBTITLE_READY,
    job_id=job_id,
    source="downloader",
    payload={...}
)
await event_publisher.publish_event(event)

# Update status with source tracking
await redis_client.update_phase(
    job_id,
    SubtitleStatus.DOWNLOAD_IN_PROGRESS,
    source="downloader"
)
```

### Backward Compatibility

Legacy status enums are maintained:
- `DOWNLOADING` (maps to `DOWNLOAD_IN_PROGRESS`)
- `TRANSLATING` (maps to `TRANSLATE_IN_PROGRESS`)
- `COMPLETED` (maps to `DONE`)

## Conclusion

The event-driven architecture provides a robust, scalable, and observable foundation for the subtitle management system. By decoupling workers from state management and maintaining a complete event history, the system is easier to debug, monitor, and extend.

