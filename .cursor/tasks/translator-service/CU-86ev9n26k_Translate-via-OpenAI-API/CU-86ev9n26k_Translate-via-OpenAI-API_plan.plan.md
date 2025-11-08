---
epic: translator-service
task: CU-86ev9n26k_Translate-via-OpenAI-API
created: 2025-01-27
---

# Translate via OpenAI API with Rate Limit Handling

## Overview

Enhance the existing `SubtitleTranslator.translate_batch` method to properly handle OpenAI API rate limits and transient failures using the existing retry utility with exponential backoff. The implementation will maintain subtitle formatting and reliably process batches/chunks.

## Problem Statement

Current implementation has basic retry logic (`max_retries=2` on AsyncOpenAI client) but:
- Doesn't specifically detect OpenAI rate limit errors (429, RateLimitError)
- Doesn't use the existing retry utility with exponential backoff
- Doesn't distinguish between transient and permanent errors
- Lacks configurable retry settings for translation service

This can cause translation failures when hitting rate limits or experiencing temporary API issues.

## Architecture

### Components to Enhance

1. **Retry Utility** (`common/retry_utils.py`)
   - Add OpenAI error detection to `is_transient_error()`
   - Detect `RateLimitError`, `APIError` with 429 status, and other transient OpenAI errors
   - Handle error cause chains for wrapped exceptions

2. **Configuration** (`common/config.py`)
   - Add OpenAI-specific retry configuration:
     - `openai_max_retries`: Default 3
     - `openai_retry_initial_delay`: Default 2.0 seconds
     - `openai_retry_max_delay`: Default 60.0 seconds
     - `openai_retry_exponential_base`: Default 2

3. **SubtitleTranslator** (`translator/worker.py`)
   - Apply retry decorator to `translate_batch()` method
   - Use configurable retry settings from config
   - Maintain existing formatting preservation via prompt
   - Keep existing batch/chunk processing logic

### Key Files

- `common/retry_utils.py` - Enhance error detection for OpenAI errors
- `common/config.py` - Add OpenAI retry configuration
- `translator/worker.py` - Apply retry logic to translate_batch
- `env.template` - Document new configuration options
- `tests/common/test_retry_utils.py` - Add OpenAI error detection tests
- `tests/translator/test_worker.py` - Add retry behavior tests

## Implementation Steps

### Phase 1: Enhance Error Detection

Update `common/retry_utils.py`:
- Import OpenAI error types (`RateLimitError`, `APIError`, `APIConnectionError`, `APITimeoutError`)
- Add detection logic in `is_transient_error()`:
  - `RateLimitError` → transient (retry)
  - `APIError` with status 429, 500, 502, 503, 504 → transient
  - `APIConnectionError`, `APITimeoutError` → transient
  - `APIError` with status 400, 401, 403, 404 → permanent (no retry)
- Check error cause chains for wrapped exceptions

### Phase 2: Add Configuration

Update `common/config.py`:
```python
# OpenAI Retry Configuration
openai_max_retries: int = Field(default=3, env="OPENAI_MAX_RETRIES")
openai_retry_initial_delay: float = Field(default=2.0, env="OPENAI_RETRY_INITIAL_DELAY")
openai_retry_max_delay: float = Field(default=60.0, env="OPENAI_RETRY_MAX_DELAY")
openai_retry_exponential_base: int = Field(default=2, env="OPENAI_RETRY_EXPONENTIAL_BASE")
```

Update `env.template` with documentation for new settings.

### Phase 3: Apply Retry Logic

Update `translator/worker.py`:
- Import retry decorator from `common.retry_utils`
- Create helper method `_create_retry_decorator()` that uses config settings
- Apply retry decorator to `translate_batch()` method
- Remove `max_retries=2` from AsyncOpenAI client initialization (let decorator handle retries)
- Keep existing error logging and formatting preservation

### Phase 4: Testing

Add comprehensive tests:

1. **test_retry_utils.py** (additions):
   - Test OpenAI RateLimitError detection
   - Test OpenAI APIError with various status codes
   - Test APIConnectionError and APITimeoutError
   - Test error cause chain analysis for OpenAI errors

2. **test_worker.py** (additions):
   - Test retry on rate limit errors
   - Test retry on transient API errors
   - Test immediate failure on permanent errors
   - Test retry exhaustion handling
   - Test successful translation after retries
   - Verify formatting preservation during retries

## API Changes

None - internal enhancement only. Existing `translate_batch()` signature unchanged.

## Testing Strategy

### Unit Tests

1. **Error Detection Tests** (`test_retry_utils.py`):
   - OpenAI RateLimitError → transient
   - APIError 429 → transient
   - APIError 500/502/503/504 → transient
   - APIError 400/401/403/404 → permanent
   - Wrapped errors in cause chain

2. **Translation Retry Tests** (`test_worker.py`):
   - Successful retry after rate limit
   - Successful retry after transient error
   - Immediate failure on permanent error
   - Retry exhaustion after max attempts
   - Formatting preserved through retries

### Integration Considerations

- Existing chunk processing logic remains unchanged
- Batch translation flow unchanged
- Event publishing unchanged
- Redis status updates unchanged

## Success Criteria

- ✅ OpenAI rate limit errors detected and retried with exponential backoff
- ✅ Transient API errors (500, 502, 503, 504) retried automatically
- ✅ Permanent errors (400, 401, 403, 404) fail immediately without retries
- ✅ Retry configuration configurable via environment variables
- ✅ Formatting preservation maintained during retries
- ✅ Batch/chunk processing unaffected
- ✅ 100% test coverage for new error detection logic
- ✅ All existing tests pass
- ✅ Configuration documented in env.template
- ✅ Retry delays follow exponential backoff with jitter

