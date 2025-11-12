---
epic: shared-components
task: CU-86ev9n27b_Implement-commonutilspy-timestamp-jobid-validation
created: 2025-01-29
---

# Implement common/utils.py (timestamp, job_id, validation)

## Overview

Extend `common/utils.py` with utility functions for timestamp generation, job ID creation, and generic validation checks. This centralizes common operations across the application and eliminates code duplication.

## Problem Statement

The codebase currently has:
- Direct usage of `uuid4()` for job ID generation scattered across multiple files
- Manual timestamp generation using `datetime.now(timezone.utc)` in various places
- Inconsistent validation logic duplicated across different modules
- No centralized utilities for common validation checks (strings, numbers, URLs, ranges)

This creates:
- Code duplication and maintenance burden
- Inconsistent validation logic
- Potential for bugs when validation logic changes
- Difficulty in ensuring consistent behavior across services

## Architecture

### Components to Add

1. **Extended DateTimeUtils Class** (`common/utils.py`)
   - `get_current_timestamp()` - Returns Unix timestamp (seconds since epoch) as float
   - `get_current_timestamp_ms()` - Returns Unix timestamp in milliseconds as int
   - `format_timestamp_iso8601(dt: datetime)` - Format datetime as ISO 8601 string
   - `parse_timestamp(timestamp: float)` - Convert Unix timestamp to UTC datetime
   - `is_valid_timestamp(timestamp: float)` - Validate timestamp is within reasonable range (1970-2100)

2. **JobIdUtils Class** (`common/utils.py`)
   - `generate_job_id()` - Generate a new UUID4 job identifier, returns UUID object
   - `generate_job_id_string()` - Generate a new UUID4 job identifier as string
   - `is_valid_job_id(job_id: str | UUID)` - Validate if input is a valid UUID format
   - `normalize_job_id(job_id: str | UUID)` - Convert job_id to UUID object, raises ValueError if invalid

3. **ValidationUtils Class** (`common/utils.py`)
   - `is_non_empty_string(value: str)` - Check if string is not None, not empty, and not whitespace-only
   - `is_valid_length(value: str, min_length: int, max_length: int)` - Validate string length within range
   - `is_positive_number(value: int | float)` - Validate number is positive (> 0)
   - `is_non_negative_number(value: int | float)` - Validate number is non-negative (>= 0)
   - `is_in_range(value: int | float, min_val: int | float, max_val: int | float)` - Validate number is within range
   - `is_valid_url_format(url: str)` - Basic URL format validation (scheme and domain)

### Key Files

- `common/utils.py` - Add new utility classes and functions
- `tests/common/test_utils.py` - Comprehensive parameterized tests for all new functions
- `common/schemas.py` - Update to use `JobIdUtils.generate_job_id()` instead of direct `uuid4()`
- `manager/event_consumer.py` - Update to use `ValidationUtils.is_non_empty_string()` for validation

## Implementation Steps

1. **Extend DateTimeUtils Class**
   - Add imports: `Union` from typing, `urlparse` from urllib.parse, `UUID, uuid4` from uuid
   - Add 5 new timestamp utility methods
   - Follow existing code patterns (static methods, comprehensive docstrings)

2. **Create JobIdUtils Class**
   - Add new utility class after `StringUtils`
   - Implement 4 job ID generation and validation functions
   - Handle both UUID objects and string representations

3. **Create ValidationUtils Class**
   - Add new utility class after `JobIdUtils`
   - Implement 6 generic validation functions
   - Handle edge cases gracefully (None, empty, invalid types)

4. **Update Existing Code to Use Utilities**
   - Replace `uuid4` with `JobIdUtils.generate_job_id` in `common/schemas.py`
   - Replace manual validation with `ValidationUtils.is_non_empty_string()` in `manager/event_consumer.py`
   - Update docstring examples to use new utilities

5. **Write Comprehensive Tests**
   - Add tests for all new DateTimeUtils methods
   - Add tests for all JobIdUtils methods
   - Add tests for all ValidationUtils methods
   - Use parameterized tests for edge cases and boundary conditions

## Testing Strategy

- **TDD Approach**: Write tests first, then implement functions
- **Parameterized Tests**: Cover multiple scenarios with single test functions
- **Edge Cases**: Test None, empty strings, invalid types, boundary values
- **Type Validation**: Ensure functions handle type mismatches gracefully
- **Error Cases**: Test that validation functions return False for invalid inputs
- **Conversion Functions**: Test that conversion functions raise appropriate errors

## Success Criteria

- All new utility functions implemented with proper docstrings
- Comprehensive test coverage with parameterized tests (target: 100+ test cases)
- No linting errors
- Functions follow existing code patterns and conventions
- All edge cases handled gracefully
- Type hints throughout
- Functions are pure (no side effects)
- Existing code updated to use new utilities (eliminating duplication)
- All tests passing

## Code Quality Standards

- Follow existing utility class pattern (static methods)
- Use descriptive function names
- Add comprehensive docstrings with examples
- Use type hints throughout
- Handle edge cases gracefully (None, empty, invalid inputs)
- Use pure functions (no side effects)
- Follow Python best practices from Context7 MCP recommendations

