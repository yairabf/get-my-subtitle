---
epic: library-scanner-service
task: CU-86ev9n26w_Jellyfin-Webhook-listener
created: 2025-01-11
---

# Jellyfin Webhook Listener

## Overview

Add an HTTP webhook endpoint to the scanner service to receive Jellyfin webhook notifications for new media additions or updates. The webhook handler will convert these notifications into the same internal event flow used by the file system watcher, ensuring consistent processing regardless of the trigger source.

## Problem Statement

Currently, the scanner service only monitors the file system for media files. There is no mechanism to receive webhook notifications from Jellyfin media server. The system needs:

- HTTP endpoint to receive Jellyfin webhook notifications
- Conversion of webhook payloads into internal scan/subtitle request events
- Consistent processing flow for both file system events and webhook events
- Concurrent operation of file system watcher and HTTP server

## Architecture

### Current State
- Scanner service currently only monitors file system via `watchdog`
- Manager service has a Jellyfin webhook endpoint (`/webhooks/jellyfin`)
- Scanner processes file system events through `MediaFileEventHandler._process_media_file()`

### Target State
- Scanner service runs both file system watcher AND HTTP server concurrently
- HTTP endpoint `/webhooks/jellyfin` receives Jellyfin notifications
- Webhook handler reuses existing `_process_media_file()` logic or creates similar flow
- Both file system events and webhook events follow the same processing pipeline

### New Components

1. **Webhook Handler** (`scanner/webhook_handler.py`)
   - `JellyfinWebhookHandler` class for processing webhook payloads
   - Validates event types and item types
   - Creates subtitle requests and publishes events
   - Reuses existing orchestrator and event publisher

2. **HTTP Server** (`scanner/scanner.py`)
   - FastAPI application instance
   - Webhook endpoint at `/webhooks/jellyfin`
   - Health check endpoint at `/health`
   - Runs concurrently with file system watcher

3. **Webhook Configuration** (`common/config.py`)
   - `scanner_webhook_host`: HTTP server host (default: `0.0.0.0`)
   - `scanner_webhook_port`: HTTP server port (default: `8001`)

### Event Flow

```
1. Jellyfin Webhook Notification
   ↓
2. Webhook Handler validates payload
   ↓
3. Filter for video items (Movie/Episode) and supported events
   ↓
4. Create SubtitleRequest and store in Redis
   ↓
5. Publish MEDIA_FILE_DETECTED event (same as file system events)
   ↓
6. Enqueue download task via orchestrator
   ↓
7. Consumer processes event (audit trail)
```

## Implementation Steps

### 1. Add FastAPI Dependencies

**File**: `scanner/requirements.txt`
- Add `fastapi==0.115.6`
- Add `uvicorn[standard]==0.32.1`

### 2. Create Webhook Handler Module

**File**: `scanner/webhook_handler.py` (new)
- Create `JellyfinWebhookHandler` class
- Reuse webhook payload schema from `manager/schemas.py` (`JellyfinWebhookPayload`)
- Implement webhook processing logic that mirrors file system event processing:
  - Validate event type (`library.item.added`, `library.item.updated`)
  - Filter for video items (`Movie`, `Episode`)
  - Extract video URL/path from payload
  - Create `SubtitleRequest` and `SubtitleResponse`
  - Store job in Redis
  - Publish `MEDIA_FILE_DETECTED` event
  - Enqueue download task via orchestrator

### 3. Add HTTP Server to Scanner Service

**File**: `scanner/scanner.py`
- Modify `MediaScanner` class to include FastAPI app instance
- Add `start_webhook_server()` method to run HTTP server in background
- Add `stop_webhook_server()` method for graceful shutdown
- Ensure HTTP server runs concurrently with file system watcher

### 4. Create Webhook Endpoint

**File**: `scanner/scanner.py`
- Create FastAPI app instance in `_create_webhook_app()` method
- Add `POST /webhooks/jellyfin` endpoint
- Use `JellyfinWebhookPayload` schema for request validation
- Return `WebhookAcknowledgement` response (reuse from `manager/schemas.py`)
- Add `GET /health` endpoint for health checks

### 5. Update Scanner Worker

**File**: `scanner/worker.py`
- Update `main()` function to start both file system watcher and HTTP server
- Ensure both services run concurrently using asyncio
- Handle graceful shutdown for both services

### 6. Add Configuration

**File**: `common/config.py`
- Add `scanner_webhook_host` (default: `0.0.0.0`)
- Add `scanner_webhook_port` (default: `8001` - different from manager's 8000)
- Reuse existing `jellyfin_*` settings for webhook processing

### 7. Update Docker Configuration

**File**: `docker-compose.yml`
- Expose webhook port for scanner service (8001)
- Update healthcheck to use HTTP endpoint
- Ensure port doesn't conflict with manager service

**File**: `scanner/Dockerfile`
- Install curl for healthcheck
- Expose port 8001

### 8. Create Tests

**File**: `tests/scanner/test_webhook_handler.py` (new)
- Test webhook payload validation
- Test event filtering (only process `library.item.added`/`library.item.updated`)
- Test item type filtering (only process `Movie`/`Episode`)
- Test job creation and event publishing
- Test error handling for invalid payloads
- Test enqueue failure handling
- Test exception handling

## Files to Create/Modify

### New Files
- `scanner/webhook_handler.py` - Webhook handler implementation
- `tests/scanner/test_webhook_handler.py` - Webhook handler tests

### Modified Files
- `scanner/requirements.txt` - Add FastAPI dependencies
- `scanner/scanner.py` - Add HTTP server lifecycle management
- `scanner/worker.py` - Start HTTP server alongside file watcher
- `common/config.py` - Add webhook server configuration
- `docker-compose.yml` - Expose webhook port
- `scanner/Dockerfile` - Install curl and expose port

## Key Design Decisions

1. **Reuse Existing Logic**: Webhook handler will reuse the same processing logic as file system events to ensure consistency
2. **Separate Port**: Scanner webhook runs on different port (8001) than manager (8000) to avoid conflicts
3. **Same Event Flow**: Webhook events publish `MEDIA_FILE_DETECTED` events just like file system events
4. **Schema Reuse**: Reuse `JellyfinWebhookPayload` and `WebhookAcknowledgement` schemas from manager service
5. **Concurrent Operation**: File system watcher and HTTP server run concurrently using asyncio

## Testing Strategy

1. **Unit Tests**: Test webhook handler logic in isolation
2. **Integration Tests**: Test full flow from webhook receipt to job creation
3. **Manual Testing**: Send test webhook payloads to verify end-to-end flow

## Success Criteria

- Scanner service accepts HTTP requests on `/webhooks/jellyfin`
- Webhook notifications trigger subtitle processing
- Webhook events follow same flow as file system events
- Both file watcher and HTTP server run concurrently
- Graceful shutdown handles both services
- Tests cover webhook processing logic
- Health check endpoint responds correctly

