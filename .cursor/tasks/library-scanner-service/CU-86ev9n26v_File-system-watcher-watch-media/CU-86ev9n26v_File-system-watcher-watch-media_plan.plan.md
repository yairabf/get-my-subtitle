---
epic: library-scanner-service
task: CU-86ev9n26v_File-system-watcher-watch-media
created: 2025-01-09
---

# File System Watcher Service

## Overview

Implement a background service that monitors the `/media` directory for new or updated media files and triggers a scan event when changes are detected. The service will use the `watchdog` library for efficient file system monitoring and integrate with the existing event-driven architecture.

## Problem Statement

Currently, subtitle processing must be manually triggered via API endpoints or Jellyfin webhooks. There is no automatic mechanism to detect when new media files are added to the file system. The system needs:

- Automatic detection of new media files in `/media` directory
- Automatic triggering of subtitle processing for detected files
- Integration with existing event-driven architecture
- Efficient file system monitoring without polling
- Debouncing to avoid processing incomplete files

## Architecture

### New Components

1. **Scanner Service** (`scanner/`)
   - Standalone worker service similar to downloader/translator
   - Uses watchdog library for file system monitoring
   - Integrates with RabbitMQ and Redis
   - Publishes events using existing EventPublisher

2. **MEDIA_FILE_DETECTED Event Type** (`common/schemas.py`)
   - Add `MEDIA_FILE_DETECTED = "media.file.detected"` to `EventType` enum
   - Follows existing event naming convention

3. **Scanner Configuration** (`common/config.py`)
   - Media path configuration
   - Recursive watching option
   - File extension filtering
   - Debounce timing
   - Language defaults

4. **MediaFileEventHandler** (`scanner/worker.py`)
   - Extends `FileSystemEventHandler` from watchdog
   - Filters events for video file extensions
   - Implements debouncing logic
   - Handles file creation and modification events

5. **MediaScanner** (`scanner/worker.py`)
   - Manages Observer lifecycle
   - Connects to RabbitMQ and Redis
   - Publishes events when media files detected
   - Creates subtitle requests via orchestrator

### Event Flow

```
1. File System Event (created/modified)
   ↓
2. MediaFileEventHandler filters for media files
   ↓
3. Wait for file stability (debouncing)
   ↓
4. Create SubtitleRequest and store in Redis
   ↓
5. Publish MEDIA_FILE_DETECTED event
   ↓
6. Enqueue download task via orchestrator
   ↓
7. Consumer processes event (audit trail)
```

## Implementation Steps

### 1. Create Scanner Service Structure

**Directory**: `scanner/`
- `__init__.py` - Package initialization
- `worker.py` - Main scanner worker implementation
- `requirements.txt` - Dependencies (watchdog, aio-pika, redis, etc.)
- `Dockerfile` - Container definition
- `README.md` - Service documentation

### 2. Update Common Schemas

**File**: `common/schemas.py`

Add new event type:
```python
class EventType(str, Enum):
    # ... existing events ...
    MEDIA_FILE_DETECTED = "media.file.detected"
```

### 3. Update Configuration

**File**: `common/config.py`

Add scanner-specific settings:
- `scanner_media_path`: Path to media directory (default: `/media`)
- `scanner_watch_recursive`: Watch subdirectories recursively (default: `true`)
- `scanner_media_extensions`: List of file extensions (default: `[".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm"]`)
- `scanner_debounce_seconds`: Seconds to wait for file stability (default: `2.0`)
- `scanner_default_source_language`: Default source language (default: `en`)
- `scanner_default_target_language`: Default target language (optional)
- `scanner_auto_translate`: Auto-translate after download (default: `false`)

**File**: `env.template`

Add scanner environment variables with defaults.

### 4. Implement Scanner Worker

**File**: `scanner/worker.py`

**MediaFileEventHandler**:
- Filter events for video file extensions
- Debounce rapid file changes (check file size stability)
- Handle `on_created` and `on_modified` events
- Ignore directory events and non-media files
- Extract video title from filename

**MediaScanner**:
- Manage Observer lifecycle (start/stop)
- Connect to RabbitMQ and Redis
- Publish events when media files detected
- Create subtitle requests via orchestrator
- Handle graceful shutdown

**Key Implementation Details**:
- Use `watchdog.observers.Observer` for cross-platform file watching
- Implement debouncing by checking file size stability
- Extract video title from filename (remove extension, clean up)
- Create SubtitleRequest with default settings
- Store job in Redis
- Publish MEDIA_FILE_DETECTED event
- Enqueue download task via orchestrator

### 5. Docker Integration

**File**: `docker-compose.yml`

Add scanner service:
```yaml
scanner:
  build:
    context: .
    dockerfile: ./scanner/Dockerfile
  volumes:
    - ./common:/app/common
    - ./scanner:/app/scanner
    - ./manager:/app/manager
    - /media:/media:ro
  env_file:
    - .env
  environment:
    REDIS_URL: redis://redis:6379
    RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
  depends_on:
    manager:
      condition: service_healthy
```

### 6. Consumer Service Updates

**File**: `consumer/worker.py`

Add handler for MEDIA_FILE_DETECTED event (for audit trail):
- Add `handle_media_file_detected` method
- Record event in Redis history
- Update routing to include `media.*` pattern

### 7. Testing

**Directory**: `tests/scanner/`
- Unit tests for event handler logic
- Unit tests for debouncing
- Unit tests for filename parsing
- Integration tests for full flow
- Test error scenarios

## Files to Create/Modify

### New Files
- `scanner/__init__.py`
- `scanner/worker.py`
- `scanner/requirements.txt`
- `scanner/Dockerfile`
- `scanner/README.md`
- `tests/scanner/__init__.py`
- `tests/scanner/test_worker.py`

### Modified Files
- `common/schemas.py` - Add MEDIA_FILE_DETECTED event type
- `common/config.py` - Add scanner configuration settings
- `docker-compose.yml` - Add scanner service
- `consumer/worker.py` - Add event handler and routing
- `env.template` - Add scanner environment variables

## Key Design Decisions

1. **Debouncing**: Wait for file size to stabilize before processing (prevents processing incomplete files)
2. **Event vs Direct Processing**: Scanner publishes events AND creates jobs (similar to Jellyfin webhook pattern)
3. **File Extension Filtering**: Only process known video file extensions
4. **Read-Only Mount**: Mount `/media` as read-only in Docker for safety
5. **Pattern Matching**: Use watchdog's event filtering for efficient processing

## Testing Strategy

1. **Unit Tests**: Test event handler filtering, debouncing logic, filename parsing
2. **Integration Tests**: Test full flow from file detection to job creation
3. **Manual Testing**: Test with actual media files in `/media` directory
4. **Edge Cases**: Test with files being written, permission errors, missing directories

## Success Criteria

- Scanner service monitors `/media` directory recursively
- New media files trigger subtitle processing automatically
- Updated media files trigger re-processing (if configured)
- Service handles errors gracefully (permissions, missing paths)
- Service integrates seamlessly with existing event-driven architecture
- Service can be started/stopped independently
- All events are properly logged and tracked

