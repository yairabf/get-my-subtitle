---
epic: shared-components
task: CU-86ev9n273_Define-common-schemas
completed: 2025-01-29
---

# Define Common Schemas - Implementation Summary

## What Was Implemented

Successfully added new Pydantic models to `common/schemas.py` for event wrapping, API-level request validation, and job metadata tracking. All models follow existing code patterns, maintain backward compatibility, and include comprehensive test coverage.

### Files Modified

1. **`common/schemas.py`**
   - Added `EventEnvelope` model for standardized event metadata
   - Added `SubtitleDownloadRequest` model for API-level download requests
   - Added `TranslationRequest` model for API-level translation requests
   - Added `JobRecord` model for standardized job metadata
   - Added `create_subtitle_ready_event()` factory function
   - Updated imports: Added `Literal` from typing, `HttpUrl` from pydantic
   - Enhanced docstrings for `DownloadTask` and `TranslationTask` clarifying they're internal models
   - Added section comments organizing new models

2. **`tests/common/test_schemas_new_models.py`** (New File)
   - Created comprehensive test suite with 104 parameterized test cases
   - Full coverage for all new models and factory function
   - All tests passing with no failures

## Implementation Details

### EventEnvelope Model

**Purpose**: Standardized envelope for wrapping events published to event exchange for better observability and traceability.

**Features**:
- Auto-generated `event_id` (UUID) using `uuid4()`
- Auto-generated `timestamp` (UTC datetime) using `DateTimeUtils.get_current_utc_datetime()`
- Required fields: `event_type` (EventType enum), `source` (str), `payload` (Dict[str, Any])
- Optional fields: `correlation_id` (UUID), `metadata` (Dict[str, Any])
- JSON schema examples included

**Test Coverage**: 12 tests covering auto-generation, validation, optional fields, and serialization

### SubtitleDownloadRequest Model

**Purpose**: API-level request model for subtitle download operations with strict validation.

**Features**:
- `video_url`: Pydantic `HttpUrl` validation (only HTTP/HTTPS URLs accepted)
- `video_title`: String with `min_length=1, max_length=500`
- `language`: Pattern validation `^[a-z]{2}$` for ISO 639-1 codes
- `target_language`: Optional, same pattern validation
- `preferred_sources`: List[str] with `default_factory=list`

**Test Coverage**: 24 tests covering URL validation (valid/invalid), language codes (10 valid, 6 invalid), title constraints, and optional fields

### TranslationRequest Model

**Purpose**: API-level request model for subtitle translation operations with strict validation.

**Features**:
- `subtitle_file_path`: Non-empty string (`min_length=1`)
- `source_language`: Pattern validation `^[a-z]{2}$` for ISO 639-1 codes
- `target_language`: Pattern validation `^[a-z]{2}$` for ISO 639-1 codes
- `video_title`: Optional string for context

**Test Coverage**: 14 tests covering path validation, language code validation, and optional fields

### JobRecord Model

**Purpose**: Standardized job metadata model for API responses and monitoring without exposing internal Redis structures.

**Features**:
- Required: `job_id` (UUID), `status` (SubtitleStatus enum), `created_at`, `updated_at` (datetime), `task_type` (Literal["download", "translation", "download_with_translation"])
- Optional: `video_url`, `video_title`, `language`, `target_language`, `result_url`, `error_message`
- `progress_percentage`: int with bounds `ge=0, le=100` (default: 0)
- Integrates with existing `SubtitleStatus` enum

**Test Coverage**: 20 tests covering required fields, task type literals, status enum integration, optional fields, and progress bounds

### create_subtitle_ready_event Factory Function

**Purpose**: Type-safe convenience method for creating SubtitleEvent with SUBTITLE_READY type and consistent payload structure.

**Features**:
- Parameters: `job_id` (UUID), `subtitle_path` (str), `language` (str), `source` (str, default="downloader"), `download_url` (Optional[str])
- Returns `SubtitleEvent` with `event_type=EventType.SUBTITLE_READY`
- Auto-generates timestamp using `DateTimeUtils.get_current_utc_datetime()`
- Maintains consistent payload structure

**Test Coverage**: 7 tests covering event creation, payload structure, optional parameters, and timestamp generation

## Testing Results

### Test Statistics
- **Total Tests**: 104
- **Passed**: 104
- **Failed**: 0
- **Coverage**: 100% for all new models

### Test Breakdown by Model
- EventEnvelope: 12 tests
- SubtitleDownloadRequest: 24 tests
- TranslationRequest: 14 tests
- JobRecord: 20 tests
- Factory Function: 7 tests
- Additional validation tests: 27 tests

### Test Fixes Applied
- Removed "xx" from invalid language codes test (it matches pattern `^[a-z]{2}$` but isn't a real ISO code - pattern validation only checks format, not actual language validity)
- Added documentation explaining pattern validation behavior

## Deviations from Plan

**No significant deviations**. Implementation followed the plan exactly:

1. ✅ All models added as specified
2. ✅ All validation constraints implemented correctly
3. ✅ Factory function created with all planned features
4. ✅ Comprehensive test coverage achieved
5. ✅ Documentation added as planned
6. ✅ No breaking changes introduced

## Architecture Decisions

1. **Pattern Validation vs. Whitelist**: Chose pattern validation (`^[a-z]{2}$`) for language codes rather than a whitelist of valid ISO 639-1 codes. This provides flexibility while ensuring format correctness. Actual language validity can be validated at the service layer if needed.

2. **EventEnvelope vs. SubtitleEvent**: Kept both models separate. `EventEnvelope` is for wrapping events with standardized metadata, while `SubtitleEvent` remains the core event model. Future integration can wrap `SubtitleEvent` in `EventEnvelope` if needed.

3. **Request vs. Task Models**: Maintained clear separation:
   - Request models (`SubtitleDownloadRequest`, `TranslationRequest`) for API validation
   - Task models (`DownloadTask`, `TranslationTask`) for internal worker queues
   - Manager service will convert Request → Task (future integration)

4. **Factory Function Approach**: Used factory function instead of subclassing to maintain single `SubtitleEvent` class and avoid inheritance hierarchy complexity.

## Code Quality

- ✅ Follows existing code patterns and conventions
- ✅ Uses utility functions from `common/utils.py` (DateTimeUtils)
- ✅ Comprehensive docstrings with examples
- ✅ JSON schema examples for all models
- ✅ Type hints throughout
- ✅ No linting errors
- ✅ All tests parameterized for comprehensive coverage

## Lessons Learned

1. **Pattern Validation Limitations**: Pattern validation (`^[a-z]{2}$`) only checks format, not semantic validity. "xx" passes pattern validation but isn't a real ISO 639-1 code. This is acceptable for format validation; semantic validation can be added at service layer if needed.

2. **Pydantic HttpUrl Validation**: Pydantic's `HttpUrl` type is strict and only accepts HTTP/HTTPS schemes, which is exactly what we need for video URLs. This provides better validation than string patterns.

3. **Literal Types**: Using `Literal["download", "translation", "download_with_translation"]` for `task_type` provides excellent type safety and validation at the schema level.

## Next Steps

1. **API Integration**: Integrate `SubtitleDownloadRequest` and `TranslationRequest` into manager API endpoints
2. **Orchestrator Updates**: Update orchestrator to convert Request models to Task models
3. **EventEnvelope Integration**: Optionally wrap `SubtitleEvent` in `EventEnvelope` for enhanced observability
4. **JobRecord Usage**: Use `JobRecord` in GET `/jobs/{job_id}` API endpoint responses
5. **Additional Factory Functions**: Consider adding factory functions for other common event types if needed

## Files Created/Modified

### Created
- `tests/common/test_schemas_new_models.py` (754 lines, 104 tests)

### Modified
- `common/schemas.py` (473 lines, added ~230 lines of new models and documentation)

### Documentation
- `.cursor/tasks/shared-components/CU-86ev9n273_Define-common-schemas/CU-86ev9n273_Define-common-schemas_plan.plan.md`
- `.cursor/tasks/shared-components/CU-86ev9n273_Define-common-schemas/CU-86ev9n273_Define-common-schemas_summary.md`

## Success Criteria Met

- ✅ All new Pydantic models validate correctly with type hints
- ✅ Comprehensive parameterized tests with 100% coverage for new models (104 tests, all passing)
- ✅ No breaking changes to existing functionality
- ✅ Clear docstrings explaining purpose and usage of each model
- ✅ Follows existing code patterns (Field annotations, json_schema_extra examples)
- ✅ Uses utility functions from common/utils.py for consistency


