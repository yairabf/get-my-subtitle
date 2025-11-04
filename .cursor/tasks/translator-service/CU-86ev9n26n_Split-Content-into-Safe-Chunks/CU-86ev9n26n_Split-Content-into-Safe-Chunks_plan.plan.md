---
epic: translator-service
task: CU-86ev9n26n_Split-Content-into-Safe-Chunks
created: 2025-11-04
---

# Split Subtitle Content into Token-Safe Chunks

## Overview

Split subtitle segments into token-safe chunks that fit model limits without breaking subtitle block boundaries. This ensures translation requests stay within API limits while maintaining subtitle integrity.

## Problem Statement

Current `chunk_segments()` function splits by segment count (default 50), but doesn't account for:
- Actual token consumption of subtitle text
- Model-specific token limits
- System prompt overhead
- Variable subtitle text length

This can cause API failures when subtitles contain long text segments.

## Architecture

### New Components

1. **Token Counter Module** (`common/token_counter.py`)
   - Uses tiktoken for accurate GPT model token counting
   - Falls back to estimation (~4 chars/token) if tiktoken unavailable
   - Caches encoding instances for performance

2. **Enhanced Configuration** (`common/config.py`)
   - `translation_max_tokens_per_chunk`: Default 8000
   - `translation_token_safety_margin`: Default 0.8 (80%)
   - Model-specific overrides possible

3. **Token-Aware Chunking** (`common/subtitle_parser.py`)
   - New `split_subtitle_content()` function
   - Keeps existing `chunk_segments()` for backward compatibility
   - Respects subtitle block boundaries (never splits mid-segment)

### Key Files

- `common/token_counter.py` - New utility for token counting
- `common/config.py` - Add token limit configuration
- `common/subtitle_parser.py` - Add `split_subtitle_content()`
- `tests/common/test_token_counter.py` - Token counter tests
- `tests/common/test_subtitle_parser.py` - Update with token-aware tests
- `translator/worker.py` - Integrate token-aware chunking

## Implementation Steps

### Phase 1: Token Counter Utility

Create `common/token_counter.py` with:
- `count_tokens(text: str, model: str)` - Primary interface
- `TokenCounter` class with encoding caching
- Tiktoken integration with fallback to estimation
- Support for common OpenAI models (gpt-4, gpt-3.5-turbo, gpt-4o)

### Phase 2: Configuration Updates

Add to `common/config.py`:
```python
translation_max_tokens_per_chunk: int = 8000
translation_token_safety_margin: float = 0.8
```

Update `env.template` with new settings.

### Phase 3: Token-Aware Chunking

Add to `common/subtitle_parser.py`:
- `split_subtitle_content(segments, max_tokens, model, safety_margin)` 
- Iterate through segments, accumulate until token limit reached
- Create new chunk when adding next segment would exceed limit
- Never split individual subtitle segments

### Phase 4: Integration

Update `translator/worker.py`:
- Replace `chunk_segments()` call with `split_subtitle_content()`
- Pass model and token limits from config
- Add logging for chunk statistics (segment count, token count per chunk)

### Phase 5: Testing

Comprehensive test coverage:
- Token counter accuracy vs tiktoken baseline
- Fallback estimation behavior
- Chunking respects token limits
- Chunks never split subtitle segments
- Edge cases: empty segments, very long segments, single segment exceeding limit
- Integration test with actual subtitle file

## API Changes

None - internal refactoring only.

## Testing Strategy

### Unit Tests

1. **test_token_counter.py**
   - Accurate counting with tiktoken
   - Fallback estimation
   - Model-specific encoding
   - Caching behavior

2. **test_subtitle_parser.py** (additions)
   - Token-aware chunking stays under limit
   - Segments remain intact
   - Handles edge cases (oversized segments)
   - Comparison with simple chunking

### Integration Tests

- Process real subtitle file with token-aware chunking
- Verify all chunks fit within limits
- Verify reconstruction matches original

## Success Criteria

- ✅ Token counting accurate within 5% of tiktoken for supported models
- ✅ Chunks never exceed configured token limit
- ✅ Subtitle segments never split across chunks
- ✅ Graceful handling of segments larger than chunk limit
- ✅ 100% test coverage for new code
- ✅ Backward compatibility: existing `chunk_segments()` unchanged
- ✅ Configuration documented in env.template
- ✅ Integration test validates end-to-end behavior

