---
epic: library-scanner-service
task: CU-86ev9n26v_File-system-watcher-watch-media
created: 2025-01-09
completed: 2025-01-09
---

# File System Watcher Service - Implementation Summary

## What Was Implemented

Successfully implemented a background scanner service that monitors the `/media` directory for new or updated media files and automatically triggers subtitle processing. The service uses the `watchdog` library for efficient file system monitoring and integrates seamlessly with the existing event-driven architecture.

### Key Components

1. **Scanner Service** (`scanner/`)
   - Complete standalone worker service following existing service patterns
   - Uses watchdog library for cross-platform file system monitoring
   - Integrates with RabbitMQ and Redis
   - Publishes events using existing EventPublisher infrastructure

2. **MEDIA_FILE_DETECTED Event Type** (`common/schemas.py`)
   - Added `MEDIA_FILE_DETECTED = "media.file.detected"` to `EventType` enum
   - Follows existing event naming convention
   - Enables event-driven integration with consumer service

3. **Scanner Configuration** (`common/config.py`)
   - Added comprehensive scanner settings:
     - `scanner_media_path`: Path to media directory (default: `/media`)
     - `scanner_watch_recursive`: Watch subdirectories recursively (default: `true`)
     - `scanner_media_extensions`: List of file extensions with validator for comma-separated env vars
     - `scanner_debounce_seconds`: Seconds to wait for file stability (default: `2.0`)
     - `scanner_default_source_language`: Default source language (default: `en`)
     - `scanner_default_target_language`: Default target language (optional)
     - `scanner_auto_translate`: Auto-translate after download (default: `false`)

4. **MediaFileEventHandler** (`scanner/worker.py`)
   - Extends `FileSystemEventHandler` from watchdog
   - Filters events for video file extensions (`.mp4`, `.mkv`, `.avi`, `.mov`, `.m4v`, `.webm`)
   - Implements debouncing by checking file size stability
   - Handles `on_created` and `on_modified` events
   - Ignores directory events and non-media files
   - Extracts video title from filename (cleans separators, removes extension)
   - Manages pending file processing tasks

5. **MediaScanner** (`scanner/worker.py`)
   - Manages Observer lifecycle (start/stop)
   - Connects to RabbitMQ, Redis, and orchestrator
   - Publishes `MEDIA_FILE_DETECTED` events when media files detected
   - Creates subtitle requests and stores in Redis
   - Enqueues download tasks via orchestrator
   - Handles graceful shutdown with signal handlers

## Implementation Details

### Files Created

1. **`scanner/__init__.py`** (New)
   - Package initialization for scanner service

2. **`scanner/worker.py`** (New, 425 lines)
   - Main scanner implementation with:
     - `MediaFileEventHandler` class for file system event handling
     - `MediaScanner` class for service lifecycle management
     - `main()` function for service entry point
     - Comprehensive error handling and logging

3. **`scanner/requirements.txt`** (New)
   - Dependencies: `watchdog==6.0.0`, `aio-pika==9.3.1`, `redis==5.2.0`, `pydantic[dotenv]==2.10.4`, `pydantic-settings==2.6.1`

4. **`scanner/Dockerfile`** (New)
   - Container definition following existing service patterns
   - Python 3.11-slim base image
   - Copies common and scanner code
   - Sets up Python path and working directory

5. **`scanner/README.md`** (New)
   - Complete documentation for scanner service
   - Configuration guide
   - Usage instructions
   - Integration details

6. **`tests/scanner/__init__.py`** (New)
   - Test package initialization

7. **`tests/scanner/test_worker.py`** (New, 373 lines)
   - Comprehensive test suite covering:
     - Event handler filtering and debouncing
     - File title extraction
     - Scanner lifecycle management
     - Integration tests for full flow

### Files Modified

1. **`common/schemas.py`** (Modified)
   - Added `MEDIA_FILE_DETECTED = "media.file.detected"` to `EventType` enum

2. **`common/config.py`** (Modified)
   - Added scanner configuration settings with field validator for comma-separated extensions
   - Added `List` and `Union` imports
   - Added `field_validator` import from pydantic

3. **`docker-compose.yml`** (Modified)
   - Added scanner service definition
   - Mounted `/media` directory as read-only
   - Added dependencies on manager service
   - Configured environment variables

4. **`consumer/worker.py`** (Modified)
   - Added `handle_media_file_detected` method for event processing
   - Updated `process_event` to route `MEDIA_FILE_DETECTED` events
   - Updated `setup_consumers` to bind `media.*` routing pattern

5. **`env.template`** (Modified)
   - Added scanner configuration environment variables with defaults

## Key Features Implemented

### File System Monitoring
- Recursive directory monitoring using watchdog Observer
- Efficient event-driven file system watching (no polling)
- Cross-platform support (Linux, macOS, Windows)

### File Filtering
- Extension-based filtering for video files
- Configurable list of supported extensions
- Case-insensitive extension matching

### Debouncing
- File size stability checking before processing
- Configurable debounce delay (default: 2 seconds)
- Prevents processing incomplete files during copy operations

### Event-Driven Integration
- Publishes `MEDIA_FILE_DETECTED` events to RabbitMQ
- Creates subtitle jobs in Redis
- Enqueues download tasks via orchestrator
- Integrates with existing consumer service for audit trail

### Error Handling
- Graceful handling of missing directories
- Permission error handling
- File disappearance during processing
- Service unavailability (Redis, RabbitMQ)

### Logging
- Comprehensive logging at all levels
- File detection events logged
- Processing steps logged
- Error logging with stack traces

## Testing

### Unit Tests
- Event handler filtering logic
- File extension recognition
- Video title extraction
- Debouncing behavior
- Scanner lifecycle management

### Integration Tests
- Full flow from file detection to job creation
- Event publishing verification
- Orchestrator integration
- Redis job storage

## Configuration

### Environment Variables

All scanner settings are configurable via environment variables:

- `SCANNER_MEDIA_PATH`: Path to media directory (default: `/media`)
- `SCANNER_WATCH_RECURSIVE`: Watch subdirectories recursively (default: `true`)
- `SCANNER_MEDIA_EXTENSIONS`: Comma-separated list of extensions (default: `.mp4,.mkv,.avi,.mov,.m4v,.webm`)
- `SCANNER_DEBOUNCE_SECONDS`: Seconds to wait for file stability (default: `2.0`)
- `SCANNER_DEFAULT_SOURCE_LANGUAGE`: Default source language (default: `en`)
- `SCANNER_DEFAULT_TARGET_LANGUAGE`: Default target language (optional)
- `SCANNER_AUTO_TRANSLATE`: Auto-translate after download (default: `false`)

## Usage

### Running with Docker Compose

```bash
docker-compose up scanner
```

### Running Locally

```bash
cd scanner
python worker.py
```

## Integration Points

The scanner service integrates with:

1. **Redis**: Stores job information and status
2. **RabbitMQ**: Publishes events and enqueues tasks
3. **Manager/Orchestrator**: Creates subtitle requests
4. **Consumer**: Processes `MEDIA_FILE_DETECTED` events for audit trail
5. **Downloader**: Processes download tasks triggered by scanner

## Deviations from Plan

No significant deviations from the original plan. All planned features were implemented as specified.

## Lessons Learned

1. **Debouncing Strategy**: File size stability checking proved effective for handling files being written
2. **Event Handler Pattern**: Using watchdog's event handler pattern provides clean separation of concerns
3. **Configuration Parsing**: Added validator for comma-separated environment variables to improve usability
4. **Service Pattern**: Following existing service patterns (downloader, translator) made integration straightforward

## Next Steps

Potential future enhancements:

1. **File Metadata Extraction**: Extract video metadata (duration, resolution) for better job creation
2. **Duplicate Detection**: Track processed files to avoid reprocessing
3. **Batch Processing**: Group multiple file detections for batch processing
4. **Configurable Actions**: Allow different actions based on file patterns or directories
5. **Health Monitoring**: Add health check endpoint for monitoring

## Success Criteria Met

✅ Scanner service monitors `/media` directory recursively  
✅ New media files trigger subtitle processing automatically  
✅ Updated media files trigger re-processing  
✅ Service handles errors gracefully  
✅ Service integrates seamlessly with existing event-driven architecture  
✅ Service can be started/stopped independently  
✅ All events are properly logged and tracked  

