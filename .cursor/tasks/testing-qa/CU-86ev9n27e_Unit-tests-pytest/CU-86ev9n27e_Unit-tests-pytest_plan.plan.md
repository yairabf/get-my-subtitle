---
epic: testing-qa
task: CU-86ev9n27e_Unit-tests-pytest
created: 2025-11-13
---

# Unit Tests (pytest) - Implementation Plan

## Overview

This plan implements comprehensive unit tests using pytest to validate individual components across the codebase. The focus is on modules with missing or incomplete test coverage, following pytest best practices including parametrization, fixtures, async testing, and proper mocking.

## Current Test Coverage Analysis

### Well-Tested Modules (No Action Needed)

- `common/utils.py` - Comprehensive tests exist
- `common/duplicate_prevention.py` - Comprehensive tests exist
- `common/subtitle_parser.py` - Comprehensive tests exist
- `common/token_counter.py` - Comprehensive tests exist
- `common/retry_utils.py` - Comprehensive tests exist
- `common/event_publisher.py` - Tests exist
- `common/redis_client.py` - Tests exist
- `common/schemas.py` - Validation and serialization tests exist
- Manager, downloader, translator, scanner modules - Various tests exist

### Modules Requiring Unit Tests

1. **`common/config.py`** - Settings class and field validators
2. **`common/logging_config.py`** - Logging setup functions and ServiceLogger class
3. **`manager/file_service.py`** - File storage operations
4. **Additional edge cases** - Enhance existing tests where needed

## Implementation Strategy

### 1. Test Configuration Module (`common/config.py`)

**File**: `tests/common/test_config.py`

**Test Cases**:

- Settings class initialization with defaults
- Environment variable loading and validation
- Field validators (scanner_media_extensions parsing)
- Type validation for all fields
- Default value verification
- Edge cases (empty strings, None values, invalid types)

**Approach**:

- Use `pytest.mark.parametrize` for multiple scenarios
- Mock environment variables using `monkeypatch`
- Test field validators independently
- Test Settings class instantiation with various configurations

### 2. Test Logging Configuration Module (`common/logging_config.py`)

**File**: `tests/common/test_logging_config.py`

**Test Cases**:

- `setup_logging()` function:
  - Logger creation with different service names
  - Log level configuration (from settings and override)
  - Console handler setup
  - File handler setup (with and without log_file)
  - Formatter configuration
  - Handler removal to prevent duplicates
- `get_log_file_path()` function:
  - Path generation format
  - Date string inclusion
- `ServiceLogger` class:
  - Initialization with/without file logging
  - All logging methods (info, debug, warning, error, critical, exception)
  - Logger propagation settings
- `configure_third_party_loggers()` function:
  - Third-party logger level configuration
  - Different log levels
- `setup_service_logging()` function:
  - Integration test of full setup flow

**Approach**:

- Use temporary directories for file logging tests
- Mock `DateTimeUtils.get_date_string_for_log_file()` for consistent testing
- Verify logger handlers and formatters
- Test log output capture using pytest's `caplog` fixture
- Use `pytest.mark.parametrize` for different log levels

### 3. Test File Service Module (`manager/file_service.py`)

**File**: `tests/manager/test_file_service.py`

**Test Cases**:

- `ensure_storage_directory()`:
  - Directory creation
  - Idempotent behavior (multiple calls)
  - Parent directory creation
- `get_subtitle_file_path()`:
  - Path generation format
  - UUID and language code handling
  - Path object return type
- `save_subtitle_file()`:
  - File creation with content
  - Directory auto-creation
  - UTF-8 encoding
  - Return value (string path)
- `read_subtitle_file()`:
  - Successful file reading
  - FileNotFoundError for missing files
  - UTF-8 encoding handling
  - Content integrity

**Approach**:

- Use `tmp_path` fixture for isolated file system testing
- Mock `settings.subtitle_storage_path` for controlled testing
- Test file operations with various UUIDs and language codes
- Verify file content matches written content
- Test error cases (missing files, permission errors)

### 4. Enhance Existing Tests (Optional Improvements)

**Areas for enhancement**:

- Add more edge cases to existing test suites
- Increase parametrization coverage
- Add tests for error handling paths
- Test integration between modules

## Testing Best Practices

### Following pytest Best Practices

1. **Parametrization**: Use `@pytest.mark.parametrize` extensively for testing multiple scenarios
2. **Fixtures**: Leverage existing fixtures in `tests/conftest.py` and create module-specific fixtures as needed
3. **Async Testing**: Use `pytest.mark.asyncio` for async functions
4. **Mocking**: Use `unittest.mock` for external dependencies
5. **Isolation**: Each test should be independent and not rely on shared state
6. **Descriptive Names**: Test function names should clearly describe what is being tested
7. **Pure Functions**: Test helpers should be pure functions (no side effects)

### Test Structure

```python
class TestModuleName:
    """Test suite for module_name module."""
    
    @pytest.mark.parametrize("input,expected", [...])
    def test_function_name_scenario(self, input, expected):
        """Test description."""
        # Arrange
        # Act
        # Assert
```

### Markers

- Use `@pytest.mark.unit` for all unit tests (already configured in `pytest.ini`)
- Use `@pytest.mark.asyncio` for async tests
- Use `@pytest.mark.parametrize` for multiple test scenarios

## Files to Create

1. `tests/common/test_config.py` - Settings configuration tests
2. `tests/common/test_logging_config.py` - Logging configuration tests
3. `tests/manager/test_file_service.py` - File service tests

## Success Criteria

1. All new test files created with comprehensive coverage
2. All tests pass with `pytest -m unit -v`
3. Test coverage increases for target modules
4. Tests follow existing patterns and conventions
5. All tests use parametrization where appropriate
6. Tests are isolated and don't require external services (Docker, Redis, RabbitMQ)
7. Tests follow TDD principles (comprehensive test cases before implementation validation)

## Dependencies

- Existing test infrastructure (`tests/conftest.py`)
- pytest fixtures (fakeredis, mocks)
- Temporary file system (`tmp_path` fixture)
- Environment variable mocking (`monkeypatch`)

## Notes

- All tests should be marked with `@pytest.mark.unit`
- Tests should not require Docker or external services
- Use existing fixtures from `tests/conftest.py` where applicable
- Follow the existing test patterns in the codebase
- Ensure tests are fast and isolated

