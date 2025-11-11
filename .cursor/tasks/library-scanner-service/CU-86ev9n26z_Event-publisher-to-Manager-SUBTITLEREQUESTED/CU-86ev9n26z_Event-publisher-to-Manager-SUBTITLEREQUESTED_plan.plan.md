# Event Publisher to Manager (SUBTITLE_REQUESTED) - Implementation Plan

## Task: CU-86ev9n26z_Event-publisher-to-Manager-SUBTITLEREQUESTED
**Epic**: Library Scanner Service

## Overview

Transform the Scanner-Manager communication from direct method calls to event-driven architecture. Scanner will publish both `MEDIA_FILE_DETECTED` (for observability) and `SUBTITLE_REQUESTED` (for workflow triggering) events. Manager will consume `SUBTITLE_REQUESTED` events via RabbitMQ topic exchange and enqueue download tasks accordingly.

## Current Architecture Issues

Currently, Scanner directly imports and calls `orchestrator.enqueue_download_task()`, creating tight coupling:
- Scanner depends on Manager's orchestrator module
- Cannot scale services independently
- Difficult to add new consumers for the same events
- Direct RPC-style communication instead of event-driven

## Target Architecture

**Scanner Service:**
- Detect media files (filesystem watcher, WebSocket, webhook)
- Create job in Redis
- Publish `MEDIA_FILE_DETECTED` event (observability)
- Publish `SUBTITLE_REQUESTED` event (actionable workflow trigger)
- **No direct orchestrator calls**

**Manager Service:**
- Consume `SUBTITLE_REQUESTED` events from topic exchange
- Parse event payload
- Enqueue download tasks via orchestrator
- Update job status on errors

## Implementation Steps

### 1. Update Schemas

**File:** `common/schemas.py`

Add new event type:
```python
class EventType(str, Enum):
    # ... existing events
    SUBTITLE_REQUESTED = "subtitle.requested"
```

### 2. Create Manager Event Consumer

**File:** `manager/event_consumer.py` (NEW)

Create a dedicated consumer class:
- Connect to RabbitMQ topic exchange (`subtitle.events`)
- Bind queue to routing key `subtitle.requested`
- Parse incoming `SubtitleEvent` messages
- Extract `SubtitleRequest` from payload
- Call `orchestrator.enqueue_download_task()`
- Handle errors and update Redis status
- Support graceful shutdown

Key methods:
- `async def connect()` - establish connection and declare queue/binding
- `async def start_consuming()` - main message processing loop
- `async def _process_subtitle_request()` - handle individual events
- `async def disconnect()` - cleanup

### 3. Integrate Consumer into Manager Lifecycle

**File:** `manager/main.py`

Update lifespan context manager:
- Import and instantiate `SubtitleEventConsumer`
- Start consumer task in background during startup
- Stop consumer task during shutdown
- Add health check endpoint to verify consumer status

### 4. Update Scanner Event Handler

**File:** `scanner/event_handler.py`

Remove orchestrator dependency and update `_process_media_file()`:
- **Remove import:** `from manager.orchestrator import orchestrator`
- Keep job creation and Redis storage
- Publish `MEDIA_FILE_DETECTED` event (existing)
- **Add:** Publish `SUBTITLE_REQUESTED` event with full request payload
- **Remove:** Direct `orchestrator.enqueue_download_task()` calls
- Remove success/failure handling (Manager handles this now)

Event payload structure:
```python
{
    "video_url": str,
    "video_title": str,
    "language": str,
    "target_language": Optional[str],
    "preferred_sources": List[str],
    "auto_translate": bool
}
```

### 5. Update Scanner Service Dependencies

**Files:**
- `scanner/scanner.py` - Remove orchestrator import and connection
- `scanner/webhook_handler.py` - Update to publish events instead of calling orchestrator
- `scanner/websocket_client.py` - Update to publish events instead of calling orchestrator

### 6. Update Tests

**New test file:** `tests/manager/test_event_consumer.py`
- Test consumer connection and queue binding
- Test event parsing and orchestrator calls
- Test error handling and Redis updates
- Test graceful shutdown
- Use mocked RabbitMQ and Redis

**Update:** `tests/scanner/test_event_handler.py`
- Remove orchestrator mocking
- Verify both events are published (MEDIA_FILE_DETECTED, SUBTITLE_REQUESTED)
- Verify event payload structure

**Integration test:** `tests/integration/test_scanner_manager_events.py`
- End-to-end test: Scanner publishes → Manager consumes → Download enqueued
- Verify event flow through RabbitMQ

## Benefits

- **Decoupling:** Scanner has no knowledge of Manager implementation
- **Scalability:** Can run multiple Manager instances consuming same events
- **Extensibility:** Other services can subscribe to same events
- **Observability:** Clear event trail for debugging
- **Resilience:** Queue persists messages if Manager is down

## Configuration

No new environment variables required. Uses existing:
- `RABBITMQ_URL` - already configured
- `scanner/manager` services already have RabbitMQ connections

## Rollback Plan

If issues arise:
1. Event consumer runs alongside existing direct calls initially
2. Can disable consumer and revert scanner to direct orchestrator calls
3. Both patterns can coexist during transition

