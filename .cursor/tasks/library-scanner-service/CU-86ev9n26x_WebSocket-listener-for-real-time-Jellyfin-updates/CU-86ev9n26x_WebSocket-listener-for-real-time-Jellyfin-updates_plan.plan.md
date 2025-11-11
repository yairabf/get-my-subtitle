# WebSocket Listener for Real-Time Jellyfin Updates - Plan

**Epic**: Library Scanner Service  
**Task**: CU-86ev9n26x_WebSocket-listener-for-real-time-Jellyfin-updates  
**Status**: Completed  
**Date**: November 11, 2025

## Overview

Implement a WebSocket client for real-time Jellyfin library updates with automatic reconnection, using webhook as fallback for reliability and periodic re-sync.

## Problem Statement

Currently, the scanner service relies on:
1. File system watching (limited to local media paths)
2. Webhook notifications (requires manual Jellyfin plugin configuration)

Both approaches have limitations:
- File system watching doesn't detect Jellyfin metadata or remote libraries
- Webhooks are passive and require external plugin setup
- No real-time push notifications from Jellyfin server

The WebSocket implementation will provide instant, bidirectional communication with Jellyfin for immediate library event detection.

## Architecture

### Components

1. **WebSocket Client** (`scanner/websocket_client.py`)
   - Manages persistent WebSocket connection to Jellyfin
   - Handles authentication and session management
   - Implements automatic reconnection with exponential backoff
   - Processes incoming Jellyfin messages

2. **Configuration Extensions** (`common/config.py`)
   - Add Jellyfin server connection settings
   - Add WebSocket-specific configuration options
   - Add fallback sync configuration

3. **Scanner Integration** (`scanner/scanner.py`)
   - Initialize and manage WebSocket client lifecycle
   - Coordinate between WebSocket, webhook, and file system watcher
   - Implement periodic fallback sync logic

4. **Worker Updates** (`scanner/worker.py`)
   - Add WebSocket connection to startup sequence
   - Handle graceful shutdown of WebSocket connection

### Jellyfin WebSocket Protocol

Jellyfin's WebSocket API:
- Endpoint: `ws://{server}/socket?api_key={api_key}`
- Authentication: API key in query parameter or bearer token
- Message format: JSON with `MessageType` field
- Key message types:
  - `LibraryChanged`: Library updates/additions
  - `UserDataChanged`: Playback state changes
  - `KeepAlive`: Connection health check

### Connection Flow

```
[Scanner Service]
    ↓
[Initialize WebSocket Client]
    ↓
[Connect to Jellyfin WebSocket]
    ↓
[Authenticate with API Key]
    ↓
[Subscribe to Library Events]
    ↓
[Process Messages] ← → [Automatic Reconnection on Failure]
    ↓
[Trigger Subtitle Processing]
```

### Fallback Strategy

- **Primary**: WebSocket listener (real-time)
- **Secondary**: Webhook endpoint (passive, requires plugin)
- **Tertiary**: Periodic library sync (once daily, configurable)
- **Last Resort**: File system watcher (local media only)

## Implementation Steps

### 1. Add Configuration Settings

**File**: `common/config.py`

Add new configuration fields:
```python
# Jellyfin WebSocket Configuration
jellyfin_url: Optional[str] = Field(default=None, env="JELLYFIN_URL")
jellyfin_api_key: Optional[str] = Field(default=None, env="JELLYFIN_API_KEY")
jellyfin_websocket_enabled: bool = Field(default=True, env="JELLYFIN_WEBSOCKET_ENABLED")
jellyfin_websocket_reconnect_delay: float = Field(default=2.0, env="JELLYFIN_WEBSOCKET_RECONNECT_DELAY")
jellyfin_websocket_max_reconnect_delay: float = Field(default=300.0, env="JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY")
jellyfin_fallback_sync_enabled: bool = Field(default=True, env="JELLYFIN_FALLBACK_SYNC_ENABLED")
jellyfin_fallback_sync_interval_hours: int = Field(default=24, env="JELLYFIN_FALLBACK_SYNC_INTERVAL_HOURS")
```

### 2. Create WebSocket Client

**File**: `scanner/websocket_client.py` (new)

Implement WebSocket client with:
- Connection management with authentication
- Message parsing and routing
- Automatic reconnection with exponential backoff
- Library event processing
- Integration with existing subtitle request flow

Key methods:
- `connect()`: Establish WebSocket connection with Jellyfin
- `disconnect()`: Graceful shutdown
- `_handle_message()`: Process incoming Jellyfin messages
- `_handle_library_changed()`: Process library change events
- `_reconnect()`: Automatic reconnection logic
- `_process_media_item()`: Trigger subtitle processing for new media

### 3. Integrate with Scanner Service

**File**: `scanner/scanner.py`

Modifications:
- Add WebSocket client initialization in `__init__`
- Start WebSocket connection in `connect()`
- Stop WebSocket connection in `disconnect()`
- Add periodic sync task for fallback
- Coordinate between WebSocket and webhook handlers

### 4. Update Worker Startup

**File**: `scanner/worker.py`

Changes:
- Ensure WebSocket connection is established during startup
- Handle WebSocket disconnection in signal handlers
- Add logging for WebSocket connection status

### 5. Update Dependencies

**File**: `scanner/requirements.txt`

Add:
```
websockets==12.0
aiohttp==3.9.1
```

### 6. Create Tests

**Files**: 
- `tests/scanner/test_websocket_client.py` (new)

Test coverage:
- WebSocket connection establishment
- Authentication handling
- Message parsing and routing
- Reconnection logic with exponential backoff
- Library event processing
- Integration with subtitle workflow
- Fallback behavior

### 7. Update Documentation

**File**: `scanner/README.md`

Document:
- WebSocket configuration options
- Connection requirements
- Fallback mechanisms
- Troubleshooting guide

## API Changes

### New Configuration Variables

```bash
# Jellyfin Server Configuration
JELLYFIN_URL=http://jellyfin.local:8096
JELLYFIN_API_KEY=your_api_key_here

# WebSocket Settings
JELLYFIN_WEBSOCKET_ENABLED=true
JELLYFIN_WEBSOCKET_RECONNECT_DELAY=2.0
JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY=300.0

# Fallback Sync
JELLYFIN_FALLBACK_SYNC_ENABLED=true
JELLYFIN_FALLBACK_SYNC_INTERVAL_HOURS=24
```

### No Public API Changes

The implementation is internal to the scanner service. External API remains unchanged.

## Testing Strategy

### Unit Tests
- WebSocket client connection/disconnection
- Message parsing for various Jellyfin message types
- Reconnection logic and exponential backoff calculation
- Library event filtering (Movie/Episode only)
- Authentication error handling

### Integration Tests
- Full WebSocket flow with mocked Jellyfin server
- Subtitle processing triggered by WebSocket events
- Fallback to webhook when WebSocket unavailable
- Periodic sync execution

### Manual Testing
- Connect to real Jellyfin server
- Add new media items and verify immediate detection
- Test connection interruption and recovery
- Verify webhook fallback functionality
- Test periodic sync behavior

## Success Criteria

1. ✅ WebSocket client successfully connects to Jellyfin server
2. ✅ Library change events trigger subtitle processing immediately
3. ✅ Automatic reconnection works with exponential backoff
4. ✅ Webhook continues to work as fallback
5. ✅ Periodic sync executes on configured schedule
6. ✅ All tests pass with >90% coverage
7. ✅ No impact on existing file system watcher functionality
8. ✅ Graceful error handling and logging
9. ✅ Configuration is straightforward and well-documented

## Risk Assessment

### Risks
- **Jellyfin API changes**: WebSocket protocol may change in future versions
- **Connection stability**: Network issues could cause frequent reconnections
- **Performance**: Processing all library events could be resource-intensive

### Mitigations
- Use well-established Python `websockets` library
- Implement robust reconnection logic with backoff
- Filter events early (only Movie/Episode types)
- Maintain webhook and file watcher as fallbacks
- Add comprehensive logging for troubleshooting

## Dependencies

- Existing scanner service infrastructure
- Redis for job storage
- RabbitMQ for task queuing
- Event publisher for notifications
- Orchestrator for subtitle workflow

