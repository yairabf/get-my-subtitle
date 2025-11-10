---
epic: library-scanner-service
task: CU-86ev9n26w_Jellyfin-Webhook-listener
created: 2025-01-11
completed: 2025-01-11
---

# Jellyfin Webhook Listener - Implementation Summary

## What Was Implemented

Successfully implemented an HTTP webhook endpoint in the scanner service to receive and process Jellyfin webhook notifications. The webhook handler converts these notifications into the same internal event flow used by the file system watcher, ensuring consistent processing regardless of the trigger source.

### Key Components

1. **Webhook Handler** (`scanner/webhook_handler.py`)
   - `JellyfinWebhookHandler` class for processing webhook payloads
   - Validates event types (`library.item.added`, `library.item.updated`)
   - Filters for video items (`Movie`, `Episode`)
   - Creates subtitle requests and stores jobs in Redis
   - Publishes `MEDIA_FILE_DETECTED` events (same as file system events)
   - Enqueues download tasks via orchestrator
   - Handles errors gracefully with appropriate responses

2. **HTTP Server** (`scanner/scanner.py`)
   - FastAPI application instance integrated into `MediaScanner` class
   - Webhook endpoint at `POST /webhooks/jellyfin`
   - Health check endpoint at `GET /health`
   - Runs concurrently with file system watcher using asyncio
   - Graceful shutdown handling for both services

3. **Webhook Configuration** (`common/config.py`)
   - Added `scanner_webhook_host`: HTTP server host (default: `0.0.0.0`)
   - Added `scanner_webhook_port`: HTTP server port (default: `8001`)
   - Reuses existing `jellyfin_*` settings for webhook processing

## Implementation Details

### Files Created

1. **`scanner/webhook_handler.py`** (New, 157 lines)
   - `JellyfinWebhookHandler` class implementation
   - Webhook payload validation and processing
   - Event publishing and job creation
   - Error handling and response generation

2. **`tests/scanner/test_webhook_handler.py`** (New, 300+ lines)
   - Comprehensive test suite covering:
     - Valid movie/episode webhook processing
     - Event filtering (ignores non-video items and unsupported events)
     - Missing video URL handling
     - Enqueue failure handling
     - Exception handling
     - Event publishing verification

### Files Modified

1. **`scanner/requirements.txt`** (Modified)
   - Added `fastapi==0.115.6`
   - Added `uvicorn[standard]==0.32.1`

2. **`scanner/scanner.py`** (Modified)
   - Added FastAPI app instance to `MediaScanner` class
   - Added `_create_webhook_app()` method to create FastAPI application
   - Added `start_webhook_server()` method to run HTTP server in background
   - Added `stop_webhook_server()` method for graceful shutdown
   - Added webhook endpoint at `POST /webhooks/jellyfin`
   - Added health check endpoint at `GET /health`

3. **`scanner/worker.py`** (Modified)
   - Updated `main()` function to start both file system watcher and HTTP server
   - Added concurrent operation of both services using asyncio
   - Updated signal handlers to stop both services gracefully
   - Added logging for both services

4. **`common/config.py`** (Modified)
   - Added `scanner_webhook_host` configuration setting
   - Added `scanner_webhook_port` configuration setting

5. **`docker-compose.yml`** (Modified)
   - Added port mapping for scanner service (8001:8001)
   - Updated healthcheck to use HTTP endpoint (`curl -f http://localhost:8001/health`)

6. **`scanner/Dockerfile`** (Modified)
   - Added curl installation for healthcheck
   - Added `EXPOSE 8001` directive

## Key Features Implemented

### Webhook Processing
- Validates Jellyfin webhook payloads using `JellyfinWebhookPayload` schema
- Filters for supported event types (`library.item.added`, `library.item.updated`)
- Filters for video item types (`Movie`, `Episode`)
- Handles missing video URL/path gracefully
- Uses Jellyfin configuration settings for language and auto-translate

### Event-Driven Integration
- Publishes `MEDIA_FILE_DETECTED` events to RabbitMQ (same as file system events)
- Creates subtitle jobs in Redis
- Enqueues download tasks via orchestrator
- Supports automatic translation when configured
- Integrates with existing consumer service for audit trail

### Concurrent Operation
- File system watcher and HTTP server run simultaneously
- Both services share the same connections (Redis, RabbitMQ, orchestrator)
- Graceful shutdown handles both services correctly
- Signal handlers coordinate shutdown of both services

### Error Handling
- Handles invalid payloads with appropriate error responses
- Handles missing video URLs with error status
- Handles enqueue failures with error status and job status update
- Handles exceptions gracefully with error responses
- Comprehensive logging at all levels

### Health Monitoring
- Health check endpoint at `/health` for monitoring
- Docker healthcheck uses HTTP endpoint
- Service status reporting

## Testing

### Unit Tests
- Webhook handler payload validation
- Event type filtering logic
- Item type filtering logic
- Job creation and event publishing
- Error handling scenarios
- Exception handling

### Integration Tests
- Full flow from webhook receipt to job creation
- Event publishing verification
- Orchestrator integration
- Redis job storage

## Configuration

### Environment Variables

Webhook server settings are configurable via environment variables:

- `SCANNER_WEBHOOK_HOST`: HTTP server host (default: `0.0.0.0`)
- `SCANNER_WEBHOOK_PORT`: HTTP server port (default: `8001`)

Webhook processing uses existing Jellyfin configuration:

- `JELLYFIN_DEFAULT_SOURCE_LANGUAGE`: Default source language (default: `en`)
- `JELLYFIN_DEFAULT_TARGET_LANGUAGE`: Default target language (optional)
- `JELLYFIN_AUTO_TRANSLATE`: Enable automatic translation (default: `true`)

## Usage

### Running with Docker Compose

```bash
docker-compose up scanner
```

The webhook endpoint will be available at `http://localhost:8001/webhooks/jellyfin`

### Running Locally

```bash
cd scanner
python worker.py
```

### Webhook Endpoint

**POST** `/webhooks/jellyfin`

**Request Body:**
```json
{
  "event": "library.item.added",
  "item_type": "Movie",
  "item_name": "Sample Movie",
  "item_path": "/media/movies/sample.mp4",
  "item_id": "abc123",
  "library_name": "Movies",
  "video_url": "http://jellyfin.local/videos/abc123"
}
```

**Response:**
```json
{
  "status": "received",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Subtitle processing queued for Sample Movie"
}
```

## Integration Points

The webhook handler integrates with:

1. **Redis**: Stores job information and status
2. **RabbitMQ**: Publishes `MEDIA_FILE_DETECTED` events
3. **Manager/Orchestrator**: Creates subtitle requests and enqueues tasks
4. **Consumer**: Processes `MEDIA_FILE_DETECTED` events for audit trail
5. **Downloader**: Processes download tasks triggered by webhook

## Deviations from Plan

No significant deviations from the original plan. All planned features were implemented as specified.

## Lessons Learned

1. **Concurrent Services**: Running file system watcher and HTTP server concurrently using asyncio works well, but requires careful shutdown coordination
2. **Schema Reuse**: Reusing schemas from manager service (`JellyfinWebhookPayload`, `WebhookAcknowledgement`) ensures consistency
3. **Event Consistency**: Publishing `MEDIA_FILE_DETECTED` events for webhook notifications ensures consistent processing flow
4. **Port Separation**: Using different port (8001) for scanner webhook avoids conflicts with manager service (8000)
5. **Health Checks**: HTTP health check endpoint is more reliable than Python-based checks for Docker health monitoring

## Next Steps

Potential future enhancements:

1. **Webhook Authentication**: Add authentication/authorization for webhook endpoints
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **Webhook Retry Logic**: Add retry logic for failed webhook processing
4. **Webhook Event History**: Track webhook event history for debugging
5. **Multiple Webhook Sources**: Support webhooks from other media servers

## Success Criteria Met

✅ Scanner service accepts HTTP requests on `/webhooks/jellyfin`  
✅ Webhook notifications trigger subtitle processing  
✅ Webhook events follow same flow as file system events  
✅ Both file watcher and HTTP server run concurrently  
✅ Graceful shutdown handles both services  
✅ Tests cover webhook processing logic  
✅ Health check endpoint responds correctly  
✅ Docker healthcheck uses HTTP endpoint  

