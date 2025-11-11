# Event Publisher to Manager (SUBTITLE_REQUESTED) - Implementation Summary

## Task: CU-86ev9n26z_Event-publisher-to-Manager-SUBTITLEREQUESTED
**Epic**: Library Scanner Service

## Overview

Successfully transformed the Scanner-Manager communication from direct method calls to a fully event-driven architecture using RabbitMQ topic exchange. The Scanner now publishes both `MEDIA_FILE_DETECTED` (observability) and `SUBTITLE_REQUESTED` (workflow triggering) events, while the Manager consumes `SUBTITLE_REQUESTED` events to trigger subtitle download workflows.

## What Was Implemented

### 1. Schema Updates
**File**: `common/schemas.py`
- Added new `SUBTITLE_REQUESTED = "subtitle.requested"` event type to `EventType` enum
- This event serves as the actionable trigger for the Manager to initiate subtitle workflows

### 2. Manager Event Consumer
**File**: `manager/event_consumer.py` (NEW)
- Created `SubtitleEventConsumer` class with full RabbitMQ integration
- Connects to `subtitle.events` topic exchange
- Binds queue `manager.subtitle.requests` to routing key `subtitle.requested`
- Processes incoming events asynchronously
- Extracts `SubtitleRequest` from event payload
- Calls `orchestrator.enqueue_download_task()` to initiate workflows
- Handles errors gracefully and updates Redis job status
- Supports graceful shutdown

**Key Methods**:
- `async def connect()` - Establishes RabbitMQ connection and queue binding
- `async def start_consuming()` - Main message processing loop
- `async def _on_message()` - Handles individual incoming messages
- `async def _process_subtitle_request()` - Processes SUBTITLE_REQUESTED events
- `async def disconnect()` - Cleanup and connection closure

### 3. Manager Lifecycle Integration
**File**: `manager/main.py`
- Imported and integrated `event_consumer` into FastAPI lifespan
- Consumer starts automatically on application startup in background task
- Graceful shutdown with timeout handling
- Added `/health/consumer` endpoint to monitor consumer status

**Health Check Endpoint**:
```python
GET /health/consumer
Response: {
    "status": "consuming" | "not_consuming",
    "connected": true | false,
    "queue_name": "manager.subtitle.requests",
    "routing_key": "subtitle.requested"
}
```

### 4. Scanner Event Handler Updates
**File**: `scanner/event_handler.py`
- **Removed**: Direct `orchestrator` import and method calls
- **Added**: Publishing of two events per media file detection:
  1. `MEDIA_FILE_DETECTED` - For observability, dashboards, audit trails
  2. `SUBTITLE_REQUESTED` - For workflow triggering by Manager

**Event Payload Structure**:
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

### 5. Scanner Service Decoupling
**Files**: `scanner/scanner.py`, `scanner/webhook_handler.py`, `scanner/websocket_client.py`
- Removed all `orchestrator` imports and connection/disconnection calls
- Updated all three media detection paths (filesystem, webhook, WebSocket) to publish events instead of calling orchestrator
- Scanner now only depends on: Redis, event_publisher (no Manager dependency)

### 6. Comprehensive Test Suite

#### Manager Tests
**File**: `tests/manager/test_event_consumer.py` (NEW)
- 13 comprehensive unit tests covering:
  - Consumer initialization and connection
  - Event parsing and processing
  - Error handling and Redis updates
  - Message callback with valid/invalid/wrong event types
  - Graceful disconnect and mock mode handling
  - Auto-translate flag handling

#### Scanner Tests  
**File**: `tests/scanner/test_event_handler.py` (NEW)
- 19 unit tests covering:
  - Media file detection and filtering
  - Video title extraction
  - File stability checking
  - **Dual event publishing** (MEDIA_FILE_DETECTED + SUBTITLE_REQUESTED)
  - Auto-translate flag logic
  - Exception handling
  - File system event handling (created, modified)
  - Task cancellation and cleanup

#### Integration Tests
**File**: `tests/integration/test_scanner_manager_events.py` (NEW)
- 4 end-to-end integration tests:
  - Scanner publishes → Manager consumes → Download enqueued
  - Multiple events processed sequentially
  - Non-SUBTITLE_REQUESTED events ignored
  - Malformed events handled gracefully

**Test Results**: All 32 tests pass ✅

## Architecture Benefits

### Decoupling
- Scanner has zero knowledge of Manager implementation
- Services can be deployed, scaled, and updated independently
- Clear separation of concerns

### Scalability
- Multiple Manager instances can consume from same queue
- Load balancing handled automatically by RabbitMQ
- Can add new event consumers without modifying Scanner

### Observability
- `MEDIA_FILE_DETECTED` events provide audit trail
- `SUBTITLE_REQUESTED` events trigger workflows
- Complete event history in Redis for debugging

### Resilience
- Queue persists messages if Manager is down
- Automatic retry on connection failures (robust connection)
- Graceful degradation (mock mode) if RabbitMQ unavailable

## Event Flow

```
Scanner detects media file
    ↓
Creates job in Redis (PENDING status)
    ↓
Publishes MEDIA_FILE_DETECTED event (observability)
    ↓
Publishes SUBTITLE_REQUESTED event (workflow trigger)
    ↓
RabbitMQ routes event to manager.subtitle.requests queue
    ↓
Manager's event consumer receives event
    ↓
Extracts SubtitleRequest from payload
    ↓
Calls orchestrator.enqueue_download_task()
    ↓
Job status updated to DOWNLOAD_QUEUED in Redis
    ↓
Download worker picks up task from queue
```

## Configuration

No new environment variables required. Uses existing:
- `RABBITMQ_URL` - Already configured for all services
- Scanner and Manager services already had RabbitMQ connections

## Testing Strategy

Followed TDD (Test-Driven Development) approach:
1. Created comprehensive test file first
2. Implemented functionality to make tests pass
3. All tests pass before moving to next component
4. Integration tests validate end-to-end flow

## Files Changed

### New Files (3)
- `manager/event_consumer.py` - Event consumer implementation
- `tests/manager/test_event_consumer.py` - Consumer unit tests
- `tests/scanner/test_event_handler.py` - Event handler unit tests  
- `tests/integration/test_scanner_manager_events.py` - Integration tests

### Modified Files (7)
- `common/schemas.py` - Added SUBTITLE_REQUESTED event type
- `manager/main.py` - Integrated event consumer lifecycle
- `scanner/event_handler.py` - Publish events instead of calling orchestrator
- `scanner/scanner.py` - Removed orchestrator dependency
- `scanner/webhook_handler.py` - Publish events instead of calling orchestrator
- `scanner/websocket_client.py` - Publish events instead of calling orchestrator

## Verification

### Unit Tests
```bash
pytest tests/manager/test_event_consumer.py -v  # 13 passed
pytest tests/scanner/test_event_handler.py -v   # 19 passed
```

### Integration Tests
```bash
pytest tests/integration/test_scanner_manager_events.py -v  # 4 passed
```

### Health Check
```bash
curl http://localhost:8000/health/consumer
```

## Lessons Learned

1. **Event-driven architecture** provides better decoupling than direct RPC calls
2. **Dual event pattern** (observability + workflow) separates concerns effectively
3. **Graceful degradation** (mock mode) allows services to start even when dependencies unavailable
4. **Comprehensive testing** (unit + integration) validates both components and end-to-end flow
5. **aio-pika's robust connection** handles reconnection automatically with exponential backoff

## Next Steps

Potential future enhancements:
1. Add more event consumers for different workflows
2. Implement event replay/reprocessing for failed jobs
3. Add metrics/monitoring for event processing latency
4. Implement event filtering at queue level for different Manager instances
5. Add dead-letter queue for permanently failed events

## Rollback Plan

If issues arise:
1. Both patterns can coexist temporarily during transition
2. Can disable consumer and revert Scanner to direct orchestrator calls
3. Events are durable and will be preserved in queue
4. No data loss risk as jobs are tracked in Redis regardless of transport

---

**Status**: ✅ Complete - All tasks implemented and tested
**Date**: November 11, 2025

