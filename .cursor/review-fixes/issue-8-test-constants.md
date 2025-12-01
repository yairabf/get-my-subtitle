# Issue #8 Fix: Test Magic Numbers → Named Constants

## Summary
Addressed Issue #8 from the code review by replacing magic numbers in parallel translation tests with descriptive named constants at the class level.

## Changes Made

### File: `tests/translator/test_worker.py`

#### Added Test Constants (Lines 1398-1407)
```python
class TestParallelTranslationProcessing:
    """Test parallel translation processing with semaphore limiting."""

    # Test constants for parallel processing configuration
    # These constants make the test values explicit and maintainable
    TEST_SEGMENTS_PER_CHUNK = 2  # Small chunks to force multiple chunks for testing
    TEST_PARALLEL_LIMIT_LOW = 2  # Low limit for testing semaphore constraint (forces queuing)
    TEST_PARALLEL_LIMIT_NORMAL = 3  # Default parallel requests for GPT-4o-mini in tests
    TEST_PARALLEL_LIMIT_HIGH = 6  # Parallel requests for higher tier models in tests
    TEST_MAX_TOKENS_PER_CHUNK = 100  # Small token limit to force chunking
    TEST_TOKEN_SAFETY_MARGIN = 0.8  # Safety margin for token calculations
    TEST_API_DELAY_SECONDS = 0.1  # Simulated API call delay for timing tests
    TEST_SEMAPHORE_DELAY_SECONDS = 0.05  # Small delay for semaphore concurrency tests
```

#### Updated Fixture to Use Constants
**Before:**
```python
mock_settings.translation_max_tokens_per_chunk = 100  # Small chunks to force multiple chunks
mock_settings.translation_max_segments_per_chunk = 2  # 2 segments per chunk
mock_settings.translation_token_safety_margin = 0.8
mock_settings.translation_parallel_requests = 3
mock_settings.translation_parallel_requests_high_tier = 6
```

**After:**
```python
mock_settings.translation_max_tokens_per_chunk = self.TEST_MAX_TOKENS_PER_CHUNK
mock_settings.translation_max_segments_per_chunk = self.TEST_SEGMENTS_PER_CHUNK
mock_settings.translation_token_safety_margin = self.TEST_TOKEN_SAFETY_MARGIN
mock_settings.translation_parallel_requests = self.TEST_PARALLEL_LIMIT_NORMAL
mock_settings.translation_parallel_requests_high_tier = self.TEST_PARALLEL_LIMIT_HIGH
```

#### Updated Semaphore Test
**Before:**
```python
mock_settings_parallel.translation_parallel_requests = 2  # Limit to 2 concurrent
await asyncio.sleep(0.05)  # Small delay to allow other requests to start
assert max_concurrent <= 2
```

**After:**
```python
# Use low parallel limit to test semaphore constraint (forces queuing with 5 chunks)
mock_settings_parallel.translation_parallel_requests = self.TEST_PARALLEL_LIMIT_LOW
mock_settings_parallel.get_translation_parallel_requests = lambda: self.TEST_PARALLEL_LIMIT_LOW
# Use test constant for delay to allow other requests to start
await asyncio.sleep(self.TEST_SEMAPHORE_DELAY_SECONDS)
assert max_concurrent <= self.TEST_PARALLEL_LIMIT_LOW
```

#### Updated Timing Tests
**Before:**
```python
await asyncio.sleep(0.1)  # Simulate API delay
delay = 0.2 - (call_count * 0.02)
```

**After:**
```python
# Simulate API delay using test constant
await asyncio.sleep(self.TEST_API_DELAY_SECONDS)
# Use decreasing delay based on call count to simulate varying API response times
delay = (self.TEST_API_DELAY_SECONDS * 2) - (call_count * 0.02)
```

## Benefits

### 1. **Improved Readability**
   - Constants have descriptive names that explain their purpose
   - Comments clarify the intent of each constant
   - Easy to understand what each value represents

### 2. **Better Maintainability**
   - Single source of truth for test configuration values
   - Easy to adjust test parameters in one place
   - Reduces risk of inconsistent values across tests

### 3. **Self-Documenting Code**
   - Constant names explain why specific values are used
   - Clear distinction between different test scenarios (LOW vs NORMAL vs HIGH limits)
   - Comments provide additional context

### 4. **Easier Test Tuning**
   - Can adjust timing constants if tests become flaky
   - Can modify parallel limits to test different scenarios
   - Clear separation between configuration and test logic

## Test Results

✅ All modified tests pass successfully:
- `test_parallel_processing_executes_chunks_concurrently` - PASSED
- `test_semaphore_limits_concurrent_requests` - PASSED (fixed with lambda update)
- `test_out_of_order_completion_handled_correctly` - PASSED
- `test_checkpoint_saved_after_parallel_batch` - PASSED
- `test_parallel_processing_with_checkpoint_resume` - PASSED

## Compliance with Coding Standards

✅ **Rule #3**: Centralize common operations in utilities
   - Test constants centralized at class level
   - Reused across multiple test methods

✅ **Rule #4**: Choose expressive variable names
   - `TEST_PARALLEL_LIMIT_LOW` is self-explanatory
   - `TEST_SEMAPHORE_DELAY_SECONDS` clearly indicates purpose and units

✅ **Rule #6**: Document behaviors with language-appropriate comments
   - Each constant has inline comment explaining its purpose
   - Test methods have comments explaining why specific constants are used

## Example Usage

```python
# Before (Magic Number)
mock_settings.translation_parallel_requests = 2  # Limit to 2 concurrent

# After (Named Constant)
mock_settings.translation_parallel_requests = self.TEST_PARALLEL_LIMIT_LOW  # Forces queuing
```

## Related Issues

This fix addresses **Issue #8** from the code review:
> "Magic Numbers in Configuration - The parallel request count uses magic number 2 without explanation in test mocks. Add named constants for test magic numbers."

The fix improves code quality by eliminating magic numbers and making test configuration explicit and maintainable.
