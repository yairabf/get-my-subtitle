---
epic: library-scanner-service
task: CU-86ev9n27d_Unit-tests-for-model-validation-and-serialization
created: 2025-01-29
---

# Unit Tests for Model Validation and Serialization

## Overview

Write comprehensive unit tests to verify schema integrity, field validation, and correct JSON serialization/deserialization for all shared models in the codebase. This includes both common schemas (`common/schemas.py`) and manager-specific schemas (`manager/schemas.py`).

## Problem Statement

The codebase has multiple Pydantic models used across different services, but lacks comprehensive test coverage for:
- Field validation (required fields, optional fields, type validation)
- Enum value validation
- JSON serialization (`model_dump()`, `model_dump_json()`)
- JSON deserialization (`model_validate()`, `model_validate_json()`)
- Round-trip serialization integrity
- Edge cases (empty strings, None values, invalid types)

Without proper test coverage, schema changes could introduce breaking changes or validation issues that go undetected.

## Architecture

### Models to Test

#### Common Schemas (`common/schemas.py`)
1. **Enums**:
   - `SubtitleStatus` - Status enum values
   - `EventType` - Event type enum values

2. **Request/Response Models**:
   - `SubtitleRequest` - Subtitle request model
   - `SubtitleResponse` - Subtitle response model
   - `DownloadTask` - Download task model
   - `TranslationTask` - Translation task model
   - `HealthResponse` - Health check response

3. **Event Models**:
   - `SubtitleEvent` - Generic subtitle event
   - `TranslationCheckpoint` - Translation checkpoint model

#### Manager Schemas (`manager/schemas.py`)
1. **Request Models**:
   - `SubtitleRequestCreate` - Create subtitle request
   - `SubtitleRequestUpdate` - Update subtitle request
   - `SubtitleTranslateRequest` - Translation request

2. **Response Models**:
   - `SubtitleStatusResponse` - Status response
   - `QueueStatusResponse` - Queue status response
   - `SubtitleDownloadResponse` - Download response
   - `WebhookAcknowledgement` - Webhook acknowledgement

3. **Webhook Models**:
   - `JellyfinWebhookPayload` - Jellyfin webhook payload

### Test Organization

Tests should be organized into separate files by concern:
- `tests/common/test_schemas_validation.py` - Validation tests for common schemas
- `tests/common/test_schemas_serialization.py` - Serialization tests for common schemas
- `tests/manager/test_schemas_validation.py` - Validation tests for manager schemas
- `tests/manager/test_schemas_serialization.py` - Serialization tests for manager schemas

## Implementation Steps

1. **Create Validation Test Files**
   - Create `tests/common/test_schemas_validation.py`
   - Create `tests/manager/test_schemas_validation.py`
   - Test enum values, required fields, optional fields, type validation

2. **Create Serialization Test Files**
   - Create `tests/common/test_schemas_serialization.py`
   - Create `tests/manager/test_schemas_serialization.py`
   - Test JSON serialization, deserialization, round-trip integrity

3. **Test Enum Validation**
   - Verify valid enum values are accepted
   - Verify invalid enum values raise ValidationError
   - Test all enum members

4. **Test Required Fields**
   - Verify missing required fields raise ValidationError
   - Verify all required fields are present in error messages

5. **Test Optional Fields**
   - Verify optional fields can be omitted
   - Verify optional fields can be None (if allowed)
   - Verify optional fields with default values

6. **Test Type Validation**
   - Verify correct types are accepted
   - Verify incorrect types raise ValidationError
   - Test UUID validation, datetime validation, URL validation

7. **Test JSON Serialization**
   - Verify `model_dump()` returns correct dict structure
   - Verify `model_dump_json()` returns valid JSON string
   - Verify UUID serialization to string
   - Verify datetime serialization to ISO format
   - Verify enum serialization to string

8. **Test JSON Deserialization**
   - Verify `model_validate()` creates instance from dict
   - Verify `model_validate_json()` creates instance from JSON string
   - Verify UUID deserialization from string
   - Verify datetime deserialization from ISO string
   - Verify enum deserialization from string

9. **Test Round-Trip Integrity**
   - Verify serialize → deserialize maintains data integrity
   - Verify serialize to JSON → deserialize maintains data integrity

10. **Test Edge Cases**
    - Empty strings (where allowed)
    - None values (where allowed)
    - Invalid types
    - Missing fields

## Testing Strategy

### Validation Tests

For each model, test:
- Valid instances can be created
- Required fields are enforced
- Optional fields work correctly
- Type validation works (UUID, datetime, enum, etc.)
- Invalid values raise ValidationError with correct error locations

### Serialization Tests

For each model, test:
- `model_dump()` returns correct dict structure
- `model_dump_json()` returns valid JSON string
- `model_validate()` creates instance from dict
- `model_validate_json()` creates instance from JSON string
- Round-trip serialization maintains data integrity
- Special types (UUID, datetime, enum) serialize/deserialize correctly

### Test Patterns

Use pytest parameterization where appropriate:
- Multiple enum values
- Multiple invalid values
- Multiple valid/invalid combinations

Use descriptive test names:
- `test_<model>_valid_<scenario>`
- `test_<model>_missing_<field>_raises_error`
- `test_<model>_invalid_<field>_type_raises_error`
- `test_<model>_serialization_<aspect>`

## Files to Create

1. `tests/common/test_schemas_validation.py` - Validation tests for common schemas
2. `tests/common/test_schemas_serialization.py` - Serialization tests for common schemas
3. `tests/manager/test_schemas_validation.py` - Validation tests for manager schemas
4. `tests/manager/test_schemas_serialization.py` - Serialization tests for manager schemas

## Files to Reference

- `common/schemas.py` - Common schema definitions
- `manager/schemas.py` - Manager schema definitions
- `tests/common/test_schemas_new_models.py` - Example test patterns
- `tests/common/test_schemas.py` - Existing test patterns

## Success Criteria

- ✅ All shared models have validation tests
- ✅ All shared models have serialization tests
- ✅ Tests verify enum values, required fields, optional fields, type validation
- ✅ Tests verify JSON serialization/deserialization
- ✅ Tests verify round-trip integrity
- ✅ All tests pass
- ✅ Code quality checks pass (Black, isort, flake8)
- ✅ Tests follow existing patterns and conventions

