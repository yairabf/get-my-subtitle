---
epic: shared-components
task: CU-86ev9n273_Define-common-schemas
created: 2025-01-29
---

# Define Common Schemas

## Overview

Refactor and enhance the `common/schemas.py` file to introduce new Pydantic models for event wrapping (EventEnvelope), API-level request models (SubtitleDownloadRequest, TranslationRequest), and job tracking schemas (JobRecord), while maintaining backward compatibility with existing internal task models and workflows.

## Problem Statement

The codebase currently has:
- `DownloadTask` and `TranslationTask` - Internal worker task models
- `SubtitleEvent` - Generic event model with `event_type` enum field
- `SubtitleRequest` - Mixed-use model for both API and internal operations
- No dedicated event envelope structure for standardized event metadata
- No standardized job metadata model for API responses

This creates ambiguity between API-level validation and internal task processing, and lacks consistent event metadata structure for observability.

## Architecture

### Components to Add

1. **EventEnvelope Model** (`common/schemas.py`)
   - Standardized envelope for wrapping events published to event exchange
   - Auto-generated `event_id` (UUID) and `timestamp` (UTC datetime)
   - Required: `event_type` (EventType enum), `source` (str), `payload` (Dict)
   - Optional: `correlation_id` (UUID), `metadata` (Dict)
   - Only wraps events (not work queue tasks)

2. **API-Level Request Models** (`common/schemas.py`)
   - **SubtitleDownloadRequest**: Validates external user inputs
     - `video_url`: HttpUrl validation (Pydantic)
     - `video_title`: String with min_length=1, max_length=500
     - `language`: Pattern validation for ISO 639-1 codes (^[a-z]{2}$)
     - `target_language`: Optional, same pattern validation
     - `preferred_sources`: List[str] with default empty list
   - **TranslationRequest**: Validates external user inputs
     - `subtitle_file_path`: Non-empty string
     - `source_language`: ISO 639-1 pattern validation
     - `target_language`: ISO 639-1 pattern validation
     - `video_title`: Optional string for context

3. **SubtitleReadyEvent Factory Helper** (`common/schemas.py`)
   - `create_subtitle_ready_event()` function
   - Type-safe convenience method for creating SUBTITLE_READY events
   - Maintains single `SubtitleEvent` class (no inheritance hierarchy)
   - Provides consistent payload structure

4. **JobRecord Model** (`common/schemas.py`)
   - Standardized job metadata for API responses and monitoring
   - Required: `job_id` (UUID), `status` (SubtitleStatus enum), `created_at`, `updated_at` (datetime), `task_type` (Literal)
   - Optional: `video_url`, `video_title`, `language`, `target_language`, `result_url`, `error_message`
   - `progress_percentage`: int with bounds 0-100 (default: 0)
   - Normalized view for API responses (doesn't expose all Redis internals)

### Key Files

- `common/schemas.py` - Add new models, factory function, update documentation
- `tests/common/test_schemas_new_models.py` - Comprehensive parameterized tests

### Relationship to Existing Models

- Keep all existing models (`DownloadTask`, `TranslationTask`, `SubtitleEvent`) unchanged
- `DownloadTask`/`TranslationTask` remain for internal worker queues
- `SubtitleDownloadRequest`/`TranslationRequest` are for API endpoints
- Manager service converts Request → Task models before queueing
- Tasks include internal fields (request_id, retry_count, priority) added by orchestrator

## Implementation Steps

1. **Add EventEnvelope Model**
   - Import `Literal` from typing
   - Import `HttpUrl` from pydantic
   - Add EventEnvelope class with auto-generated fields
   - Add JSON schema examples

2. **Add API Request Models**
   - Add SubtitleDownloadRequest with HttpUrl and pattern validation
   - Add TranslationRequest with path and language validation
   - Add comprehensive docstrings explaining purpose

3. **Create Factory Function**
   - Add `create_subtitle_ready_event()` function
   - Handle optional parameters (download_url, custom source)
   - Maintain consistent payload structure

4. **Add JobRecord Model**
   - Use Literal type for task_type validation
   - Integrate with existing SubtitleStatus enum
   - Add progress percentage bounds validation

5. **Update Documentation**
   - Add docstrings to all new models
   - Update existing DownloadTask/TranslationTask docstrings
   - Add section comments organizing new models

6. **Create Comprehensive Tests**
   - Test EventEnvelope validation and auto-generation
   - Test SubtitleDownloadRequest validation (URLs, language codes, titles)
   - Test TranslationRequest validation (paths, language codes)
   - Test JobRecord construction and bounds
   - Test factory function with all parameter combinations
   - Use parameterized tests for comprehensive coverage

## Testing Strategy

### Unit Tests

Create `tests/common/test_schemas_new_models.py`:

1. **EventEnvelope Tests**
   - Verify event_id is auto-generated UUID
   - Verify timestamp is auto-generated with UTC
   - Validate event_type from enum
   - Test with/without optional fields
   - Test required field validation

2. **SubtitleDownloadRequest Tests**
   - Valid HTTP URLs (https, http, subdomains, ports)
   - Invalid URLs should raise ValidationError (ftp, file, invalid schemes)
   - Language code pattern validation (valid: en, es, fr, etc.)
   - Invalid language codes raise ValidationError (ENG, english, e, en-US, 123, empty)
   - Video title length constraints (1-500 chars)
   - Empty preferred_sources defaults to []
   - Target language optional and validation

3. **TranslationRequest Tests**
   - Non-empty subtitle_file_path
   - Valid ISO language codes
   - Invalid language codes raise ValidationError

4. **JobRecord Tests**
   - All required fields present
   - Optional fields handled correctly
   - Status enum integration
   - Progress percentage bounds (0-100)
   - Invalid task_type raises ValidationError

5. **Factory Function Tests**
   - Returns correct SubtitleEvent
   - Payload structure validation
   - Optional parameters handled correctly
   - Timestamp auto-generated

### Integration Tests

- Verify EventEnvelope doesn't break existing event publishing
- Confirm Request → Task conversion in orchestrator works correctly (future integration)

## Files to Modify

1. `common/schemas.py` - Add new models, factory function
2. `tests/common/test_schemas_new_models.py` - New comprehensive test file

## Files to Reference

- `common/utils.py` - Use `DateTimeUtils` for timestamps
- `manager/orchestrator.py` - Reference for Request → Task conversion pattern
- `common/event_publisher.py` - Reference for event publishing patterns

## Migration Notes

**No Breaking Changes**:
- All existing models remain unchanged
- New models are additions, not replacements
- Existing tests should continue passing
- Future tasks will integrate new Request models into API endpoints

**Future Integration Points**:
1. Manager API endpoints will use SubtitleDownloadRequest/TranslationRequest
2. Orchestrator will convert Request → Task models
3. EventEnvelope can wrap SubtitleEvent for enhanced observability (optional enhancement)
4. JobRecord will be used in GET /jobs/{job_id} API responses

## Success Criteria

- All new Pydantic models validate correctly with type hints
- Comprehensive parameterized tests with 100% coverage for new models
- No breaking changes to existing functionality
- Clear docstrings explaining purpose and usage of each model
- Follows existing code patterns (Field annotations, json_schema_extra examples)
- Uses utility functions from common/utils.py for consistency



