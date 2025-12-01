# Scanner Service

The Scanner service monitors media files through multiple methods and automatically triggers subtitle processing.

> **📖 See Also**: [Main README](../README.md) for project overview, setup instructions, and development guide.

## Overview

The scanner provides three complementary methods for detecting new media:

1. **WebSocket Listener** (Primary): Real-time notifications from Jellyfin server
2. **Webhook Endpoint** (Secondary): HTTP endpoint for Jellyfin webhook plugin
3. **Manual Scan** (On-Demand): Triggered via API for full library reconciliation
4. **File System Watcher** (Fallback): Local file monitoring with `watchdog`

When new media is detected through any method, the scanner:

1. Validates the file is a supported video format
2. Creates a subtitle request job
3. Publishes a `MEDIA_FILE_DETECTED` event
4. Enqueues the download task via the orchestrator

## Features

### WebSocket Integration
- **Real-Time Updates**: Instant notifications from Jellyfin via WebSocket
- **Automatic Reconnection**: Exponential backoff on connection failures
- **Fallback Sync**: Periodic health checks and fallback mechanisms

### File System Monitoring
- **Recursive Monitoring**: Watches `/media` directory and all subdirectories
- **File Extension Filtering**: Only processes known video file extensions
- **Debouncing**: Waits for file size to stabilize before processing

### General
- **Event-Driven**: Integrates with existing RabbitMQ event system
- **Automatic Processing**: Triggers subtitle download automatically
- **Multi-Source Support**: Combines WebSocket, webhook, and file system watching

## Configuration

### Jellyfin WebSocket Configuration

Required for WebSocket functionality:

- `JELLYFIN_URL`: Jellyfin server URL (e.g., `http://jellyfin.local:8096`)
- `JELLYFIN_API_KEY`: Jellyfin API key for authentication
- `JELLYFIN_WEBSOCKET_ENABLED`: Enable WebSocket listener (default: `true`)

Optional WebSocket settings:

- `JELLYFIN_WEBSOCKET_RECONNECT_DELAY`: Initial reconnection delay in seconds (default: `2.0`)
- `JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY`: Maximum reconnection delay in seconds (default: `300.0`)
- `JELLYFIN_FALLBACK_SYNC_ENABLED`: Enable periodic fallback sync (default: `true`)
- `JELLYFIN_FALLBACK_SYNC_INTERVAL_HOURS`: Fallback sync interval in hours (default: `24`)

### Jellyfin General Configuration

- `JELLYFIN_AUTO_TRANSLATE`: Auto-translate Jellyfin media (default: `true`)
  - When true, automatically translates subtitles if desired language isn't found
  - Downloads in fallback language, then translates to desired language

**Note:** Language configuration is now centralized. See [Subtitle Language Configuration](#subtitle-language-configuration) below.

### Scanner Webhook Configuration

- `SCANNER_WEBHOOK_HOST`: Webhook server host (default: `0.0.0.0`)
- `SCANNER_WEBHOOK_PORT`: Webhook server port (default: `8001`)

### File System Watcher Configuration

- `SCANNER_MEDIA_PATH`: Path to media directory (default: `/media`)
- `SCANNER_WATCH_RECURSIVE`: Watch subdirectories recursively (default: `true`)
- `SCANNER_MEDIA_EXTENSIONS`: Comma-separated list of extensions (default: `.mp4,.mkv,.avi,.mov,.m4v,.webm`)
- `SCANNER_DEBOUNCE_SECONDS`: Seconds to wait for file stability (default: `2.0`)
- `SCANNER_AUTO_TRANSLATE`: Auto-translate after download (default: `false`)

**Note:** Language configuration is now centralized. See [Subtitle Language Configuration](#subtitle-language-configuration) below.

### Subtitle Language Configuration

- `SUBTITLE_DESIRED_LANGUAGE`: The goal language (what you want to download) (default: `en`)
- `SUBTITLE_FALLBACK_LANGUAGE`: Fallback when desired isn't found (then translated to desired) (default: `en`)

When a subtitle in the desired language isn't found, the system will:
1. Download in the fallback language
2. Automatically translate from fallback to desired language (if auto-translate is enabled)

## Architecture

The scanner service is organized into modular components:

- **`worker.py`**: Main entry point - initializes and runs the scanner service
- **`scanner.py`**: `MediaScanner` class - manages all scanner components and service connections
- **`websocket_client.py`**: `JellyfinWebSocketClient` class - handles WebSocket connection to Jellyfin
- **`webhook_handler.py`**: `JellyfinWebhookHandler` class - processes webhook notifications from Jellyfin
- **`event_handler.py`**: `MediaFileEventHandler` class - handles file system events and processes media files

### Module Responsibilities

**worker.py**
- Service entry point
- Signal handling for graceful shutdown
- Main event loop

**scanner.py (MediaScanner)**
- Component lifecycle management (WebSocket, webhook, file watcher)
- Service connections (Redis, RabbitMQ, orchestrator)
- Fallback sync coordination
- Configuration and initialization

**websocket_client.py (JellyfinWebSocketClient)**
- WebSocket connection management
- Message parsing and routing
- Automatic reconnection with exponential backoff
- Library change event processing
- Item fetching and processing

**webhook_handler.py (JellyfinWebhookHandler)**
- Webhook request validation
- Event filtering (library.item.added, library.item.updated)
- Item type validation (Movie, Episode)
- Job creation and enqueueing

**event_handler.py (MediaFileEventHandler)**
- File system event handling (on_created, on_modified)
- File filtering and validation
- Debouncing logic
- Media file processing
- Job creation and event publishing

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

### WebSocket Flow (Primary)

1. **Connection**: WebSocket client connects to Jellyfin server on startup
2. **Authentication**: API key is sent during connection handshake
3. **Message Listening**: Client listens for `LibraryChanged` messages
4. **Item Processing**: When new items are added:
   - Fetches item details from Jellyfin API
   - Filters for Movie/Episode types only
   - Creates subtitle request job
   - Publishes event and enqueues download task
5. **Reconnection**: Automatic reconnection with exponential backoff on failures

### Webhook Flow (Secondary)

1. **Endpoint Registration**: HTTP server listens on configured port
2. **Notification Reception**: Jellyfin webhook plugin sends POST requests
3. **Validation**: Validates event type and item type
4. **Job Creation**: Creates subtitle request and enqueues task

### File System Flow (Fallback)

1. **File Detection**: Watchdog detects file system events (created, modified)
2. **Filtering**: Only media files with supported extensions are processed
3. **Debouncing**: File size is checked periodically until stable
4. **Job Creation**: Subtitle request is created and stored in Redis
5. **Event Publishing**: `MEDIA_FILE_DETECTED` event is published to RabbitMQ
6. **Task Enqueueing**: Download task is enqueued via orchestrator

### Manual Scan Flow (On-Demand)

1. **Trigger**: POST request to `/scan` endpoint (usually from Manager service)
2. **Execution**: Scanner iterates through all files in the configured media directory
3. **Processing**: Each file is processed as if it was just detected (validation, job creation, event publishing)
4. **Background**: Scan runs asynchronously to avoid blocking the API

### Fallback Strategy

The scanner uses a multi-layered approach:

1. **Primary**: WebSocket listener provides instant notifications
2. **Secondary**: Webhook endpoint as passive receiver
3. **Tertiary**: Periodic sync checks WebSocket health (every 24 hours by default)
4. **Last Resort**: File system watcher for local media changes

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

### WebSocket Errors
- Connection failures: Automatic reconnection with exponential backoff
- Authentication errors: Logs error and continues with fallback methods
- Network interruptions: Reconnects automatically when network is restored
- Message parsing errors: Logs and continues processing other messages

### General Errors
- Missing or inaccessible media directory
- Permission errors
- Files being written (waits for stability)
- Network/service unavailability (retries)

## Integration

The scanner integrates with:

- **Jellyfin Server**: Receives real-time updates via WebSocket and webhook
- **Redis**: Stores job information
- **RabbitMQ**: Publishes events and enqueues tasks
- **Manager/Orchestrator**: Creates subtitle requests
- **Consumer**: Processes `MEDIA_FILE_DETECTED` events (optional)

## Getting Your Jellyfin API Key

To use the WebSocket listener, you need a Jellyfin API key:

1. Log in to your Jellyfin server web interface
2. Go to **Dashboard** → **API Keys**
3. Click **Add API Key** (or **+** button)
4. Enter a name (e.g., "Subtitle Scanner")
5. Copy the generated API key
6. Set it in your `.env` file: `JELLYFIN_API_KEY=your_api_key_here`

## Troubleshooting

### WebSocket Not Connecting

**Symptom**: Log shows "Jellyfin WebSocket is not configured or disabled"

**Solution**: Ensure you have set:
```bash
JELLYFIN_URL=http://your-jellyfin-server:8096
JELLYFIN_API_KEY=your_api_key
JELLYFIN_WEBSOCKET_ENABLED=true
```

**Symptom**: Connection fails with authentication error

**Solution**: 
- Verify your API key is correct
- Check that the API key hasn't been revoked in Jellyfin
- Ensure your Jellyfin server is accessible from the scanner service

### WebSocket Keeps Reconnecting

**Symptom**: Logs show frequent reconnection attempts

**Possible Causes**:
- Network instability between scanner and Jellyfin
- Jellyfin server is restarting or under heavy load
- Firewall blocking WebSocket connections

**Solution**:
- Check network connectivity: `ping your-jellyfin-server`
- Verify Jellyfin server logs for issues
- Ensure WebSocket traffic is allowed through firewall
- Increase reconnection delays if needed:
  ```bash
  JELLYFIN_WEBSOCKET_RECONNECT_DELAY=5.0
  JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY=600.0
  ```

### No Media Detection

**Symptom**: New media added to Jellyfin but no subtitle processing triggered

**Debugging Steps**:

1. **Check WebSocket Status**: Look for "WebSocket client: connected" in logs
2. **Verify Event Reception**: Watch logs when adding media to Jellyfin
3. **Test Webhook**: If WebSocket isn't working, configure Jellyfin webhook plugin
4. **File System Watcher**: As last resort, ensure media path is mounted correctly

**Enable Debug Logging**:
```bash
LOG_LEVEL=DEBUG
```

### Duplicate Processing

**Symptom**: Same media file processed multiple times

**Cause**: Multiple detection methods triggering simultaneously

**Solution**: This is expected behavior in edge cases. The system handles duplicates gracefully:
- Redis stores jobs by ID to prevent actual duplication
- Multiple detection ensures reliability
- If problematic, disable file system watcher for Jellyfin-managed media

## Performance Considerations

- **WebSocket Connection**: Minimal overhead, persistent connection
- **API Calls**: One API call per new media item to fetch details
- **Memory Usage**: Low, event-driven architecture
- **Network**: Bandwidth usage is minimal, mostly idle with periodic keep-alives

## Security Considerations

- **API Key Storage**: Store API keys securely using environment variables
- **Network Exposure**: WebSocket uses same authentication as Jellyfin API
- **HTTPS/WSS**: Use HTTPS URLs for production to enable WSS (secure WebSocket)
- **Firewall**: Only webhook port (8001) needs to be exposed if using webhooks

