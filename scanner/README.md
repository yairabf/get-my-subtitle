# Scanner Service

The Scanner service monitors the `/media` directory for new or updated media files and automatically triggers subtitle processing.

## Overview

The scanner uses the `watchdog` library to monitor the file system for changes. When a new or updated media file is detected, it:

1. Validates the file is a supported video format
2. Waits for the file to stabilize (debouncing)
3. Creates a subtitle request job
4. Publishes a `MEDIA_FILE_DETECTED` event
5. Enqueues the download task via the orchestrator

## Features

- **Recursive Monitoring**: Watches `/media` directory and all subdirectories
- **File Extension Filtering**: Only processes known video file extensions
- **Debouncing**: Waits for file size to stabilize before processing
- **Event-Driven**: Integrates with existing RabbitMQ event system
- **Automatic Processing**: Triggers subtitle download automatically

## Configuration

Environment variables:

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

## How It Works

1. **File Detection**: Watchdog detects file system events (created, modified)
2. **Filtering**: Only media files with supported extensions are processed
3. **Debouncing**: File size is checked periodically until stable
4. **Job Creation**: Subtitle request is created and stored in Redis
5. **Event Publishing**: `MEDIA_FILE_DETECTED` event is published to RabbitMQ
6. **Task Enqueueing**: Download task is enqueued via orchestrator

## Supported File Extensions

- `.mp4`
- `.mkv`
- `.avi`
- `.mov`
- `.m4v`
- `.webm`

## Logging

The scanner service logs all file detection events and processing steps. Logs are written to:
- Console (stdout)
- File: `logs/scanner_YYYYMMDD.log`

## Error Handling

The scanner handles various error scenarios gracefully:

- Missing or inaccessible media directory
- Permission errors
- Files being written (waits for stability)
- Network/service unavailability (retries)

## Integration

The scanner integrates with:

- **Redis**: Stores job information
- **RabbitMQ**: Publishes events and enqueues tasks
- **Manager/Orchestrator**: Creates subtitle requests
- **Consumer**: Processes `MEDIA_FILE_DETECTED` events (optional)

