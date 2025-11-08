---
epic: translator-service
task: CU-86ev9n26p_Publish-TRANSLATIONCOMPLETED-event
created: 2025-01-08
---

# Publish TRANSLATION_COMPLETED Event

## Overview

Implement event publishing for translation completion that includes duration tracking, file path, and source/target language metadata. This event will be published at the end of successful translation to enable monitoring and analytics.

## Problem Statement

Currently, the system publishes a `SUBTITLE_TRANSLATED` event when translation completes, but it lacks critical monitoring metadata:
- No duration tracking for performance monitoring
- Limited metadata for analytics and observability
- No standardized event for monitoring systems to track translation performance

The system needs to:
- Track translation duration from start to completion
- Publish a dedicated `TRANSLATION_COMPLETED` event with comprehensive metadata
- Include file paths, duration, and language information for monitoring
- Log metadata for monitoring systems

## Architecture

### New Components

1. **TRANSLATION_COMPLETED Event Type** (`common/schemas.py`)
   - Add `TRANSLATION_COMPLETED = "translation.completed"` to `EventType` enum
   - Follows existing event naming convention

2. **Duration Tracking** (`translator/worker.py`)
   - Capture start time at beginning of translation
   - Calculate duration at completion
   - Use `DateTimeUtils` for consistent timestamp handling

3. **Event Publishing** (`translator/worker.py`)
   - Publish `TRANSLATION_COMPLETED` event after successful translation
   - Include comprehensive payload with all required metadata
   - Publish before existing `SUBTITLE_TRANSLATED` event for proper ordering

4. **Enhanced Logging** (`translator/worker.py`)
   - Log translation start time
   - Log completion duration
   - Log event publication with duration metadata

### Event Payload Structure

```json
{
  "event_type": "translation.completed",
  "job_id": "uuid-string",
  "timestamp": "2025-01-08T10:00:00Z",
  "source": "translator",
  "payload": {
    "file_path": "/path/to/translated.srt",
    "duration_seconds": 45.67,
    "source_language": "en",
    "target_language": "es",
    "subtitle_file_path": "/path/to/original.srt",
    "translated_path": "/path/to/translated.srt"
  }
}
```

### Key Files

- `common/schemas.py` - Add `TRANSLATION_COMPLETED` to `EventType` enum
- `translator/worker.py` - Add duration tracking and event publishing
- `tests/common/test_schemas.py` - Test new event type
- `tests/common/test_event_publisher.py` - Include in parametrized tests
- `tests/translator/test_worker.py` - Test duration tracking and event publishing

## Implementation Steps

### Phase 1: Add Event Type

Add `TRANSLATION_COMPLETED` to `EventType` enum in `common/schemas.py`:
- Follow existing naming convention (`subtitle.translated` → `translation.completed`)
- Place after `SUBTITLE_TRANSLATED` for logical ordering

### Phase 2: Duration Tracking

Update `translator/worker.py`:
1. **At Start of Translation**:
   - Capture start time using `DateTimeUtils.get_current_utc_datetime()`
   - Log translation start time for monitoring
   - Store in variable for later duration calculation

2. **At End of Translation**:
   - Calculate duration: `(end_time - start_time).total_seconds()`
   - Log completion duration
   - Use duration in event payload

### Phase 3: Event Publishing

Update `translator/worker.py`:
1. **After Successful Translation**:
   - Create `SubtitleEvent` with `EventType.TRANSLATION_COMPLETED`
   - Include comprehensive payload:
     - `file_path`: Translated file path
     - `duration_seconds`: Translation duration (float)
     - `source_language`: Source language code
     - `target_language`: Target language code
     - `subtitle_file_path`: Original subtitle file path
     - `translated_path`: Output file path
   - Publish using `event_publisher.publish_event()`
   - Publish before `SUBTITLE_TRANSLATED` event

2. **Logging**:
   - Log event publication with duration information
   - Include structured logging for monitoring systems

### Phase 4: Testing

1. **Schema Tests** (`test_schemas.py`):
   - Verify `TRANSLATION_COMPLETED` event type exists
   - Test event creation with full payload
   - Test event validation

2. **Event Publisher Tests** (`test_event_publisher.py`):
   - Include `TRANSLATION_COMPLETED` in parametrized event type tests
   - Verify event publishing works correctly

3. **Worker Tests** (`test_worker.py`):
   - Test duration tracking accuracy
   - Test event publishing with correct payload
   - Test payload structure validation
   - Test event ordering (TRANSLATION_COMPLETED before SUBTITLE_TRANSLATED)

## API Changes

None - internal enhancement only. Translation API remains unchanged.

## Testing Strategy

### Unit Tests

1. **Schema Tests**:
   - Verify `TRANSLATION_COMPLETED` enum value exists
   - Test event creation with required payload fields
   - Test payload validation

2. **Event Publisher Tests**:
   - Include `TRANSLATION_COMPLETED` in all event type tests
   - Verify routing key is correct
   - Verify message serialization

3. **Worker Tests**:
   - Test duration calculation accuracy
   - Test event payload structure
   - Test event publication order
   - Test logging includes duration

### Integration Considerations

- Event published to same RabbitMQ topic exchange (`subtitle.events`)
- Uses existing `EventPublisher` infrastructure
- Compatible with existing event consumers
- Duration tracking starts after message parsing (measures actual translation time)
- Event published even if checkpoint cleanup fails (non-blocking)

## Success Criteria

- ✅ `TRANSLATION_COMPLETED` event type added to enum
- ✅ Duration tracked from start to completion
- ✅ Event published with all required metadata
- ✅ Event includes `duration_seconds` as float
- ✅ Event includes file paths and language information
- ✅ Comprehensive logging for monitoring
- ✅ Event published before `SUBTITLE_TRANSLATED` event
- ✅ All tests passing
- ✅ No breaking changes to existing functionality
- ✅ Backward compatible with existing `SUBTITLE_TRANSLATED` event

## Design Patterns Used

- **Observer Pattern**: Event publishing for monitoring and analytics
- **Decorator Pattern**: Duration tracking wraps translation process
- **Strategy Pattern**: Event payload structure follows existing patterns

