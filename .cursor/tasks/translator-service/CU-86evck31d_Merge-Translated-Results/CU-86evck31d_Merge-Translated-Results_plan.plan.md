---
epic: translator-service
task: CU-86evck31d_Merge-Translated-Results
created: 2025-01-08
---

# Merge Translated Results

## Overview

Recombine translated chunks into a single subtitle file, restoring original numbering, timestamps, and spacing. This ensures that when subtitle segments are translated in chunks, the final merged file maintains proper SRT format with sequential numbering and correct spacing between entries.

## Problem Statement

Currently, when subtitle files are translated in chunks:
- Translated segments are merged using `extend()` which preserves original indices
- The `SRTParser.format()` method may not ensure proper SRT spacing
- Segments might not be in sequential order after merging chunks
- Numbering might not be sequential (1, 2, 3...) if original indices were non-sequential

This can result in:
- SRT files with incorrect numbering
- Missing or incorrect spacing between subtitle entries
- Segments out of chronological order
- Non-standard SRT format that may not work with all video players

## Architecture

### Components

1. **Merge Function** (`common/subtitle_parser.py`)
   - New `merge_translated_chunks()` function
   - Combines translated segments from multiple chunks
   - Ensures sequential ordering by original index or timestamp
   - Renumbers segments sequentially starting from 1
   - Preserves all timestamps and translated text

2. **Enhanced Formatting** (`common/subtitle_parser.py`)
   - Update `SRTParser.format()` method
   - Ensure proper SRT spacing (one blank line between entries)
   - Handle edge cases (empty segments, single segment)
   - No trailing blank lines at end of file

3. **Integration** (`translator/worker.py`)
   - Use merge function before final formatting
   - Ensure segments are properly merged and renumbered
   - Maintain backward compatibility

### Key Files

- `common/subtitle_parser.py` - Add `merge_translated_chunks()` and enhance `format()`
- `translator/worker.py` - Integrate merge function
- `tests/common/test_subtitle_parser.py` - Add comprehensive tests for merging

## Implementation Steps

### Phase 1: Merge Function Implementation

Create `merge_translated_chunks()` in `common/subtitle_parser.py`:

```python
def merge_translated_chunks(
    translated_segments: List[SubtitleSegment]
) -> List[SubtitleSegment]:
    """
    Merge translated segments from multiple chunks into a single list.
    
    Ensures:
    - Segments are sorted by original index (chronological order)
    - Sequential numbering starting from 1
    - All timestamps and text preserved
    
    Args:
        translated_segments: List of translated SubtitleSegment objects
        
    Returns:
        List of SubtitleSegment objects with sequential numbering
    """
```

Implementation details:
- Sort segments by original index to ensure chronological order
- Renumber sequentially (1, 2, 3...)
- Preserve all timestamps and text content
- Handle edge cases (empty list, single segment)

### Phase 2: Enhanced SRT Formatting

Update `SRTParser.format()` method:

```python
@staticmethod
def format(segments: List[SubtitleSegment]) -> str:
    """
    Format subtitle segments back to SRT format with proper spacing.
    
    Ensures:
    - One blank line between subtitle entries
    - No trailing blank lines at end of file
    - Proper newline handling
    
    Args:
        segments: List of SubtitleSegment objects
        
    Returns:
        Formatted SRT content string
    """
```

Implementation details:
- Join segments with double newline (`\n\n`) for proper spacing
- Remove trailing newlines from final output
- Handle empty segment list gracefully
- Ensure each entry ends with single newline, followed by blank line

### Phase 3: Integration

Update `translator/worker.py`:

```python
# After all chunks are translated
# Merge and renumber segments
merged_segments = merge_translated_chunks(all_translated_segments)

# Format back to SRT
translated_srt = SRTParser.format(merged_segments)
```

### Phase 4: Testing

Comprehensive test coverage:

1. **Test merge_translated_chunks()**:
   - Merge segments from multiple chunks
   - Verify sequential numbering (1, 2, 3...)
   - Verify chronological order preserved
   - Verify timestamps preserved
   - Test with empty list
   - Test with single segment
   - Test with segments out of order

2. **Test enhanced format()**:
   - Verify proper spacing between entries
   - Verify no trailing blank lines
   - Verify correct SRT format
   - Test with empty list
   - Test with single segment
   - Test with multiline text

3. **Integration tests**:
   - End-to-end translation with chunking
   - Verify final SRT file format
   - Verify sequential numbering
   - Verify proper spacing

## API Changes

### New Function

- `common.subtitle_parser.merge_translated_chunks()` - Public function for merging translated segments

### Modified Function

- `common.subtitle_parser.SRTParser.format()` - Enhanced to ensure proper SRT spacing

## Testing Strategy

### Unit Tests

1. **test_merge_translated_chunks()**:
   - Test merging segments from multiple chunks
   - Test sequential numbering
   - Test chronological ordering
   - Test timestamp preservation
   - Test edge cases (empty, single segment, out of order)

2. **test_format_with_spacing()**:
   - Test proper spacing between entries
   - Test no trailing blank lines
   - Test SRT format compliance
   - Test edge cases

### Integration Tests

- Process real subtitle file with chunking
- Verify final merged file format
- Verify sequential numbering
- Verify proper spacing
- Verify all segments present

## Success Criteria

- ✅ `merge_translated_chunks()` correctly merges segments from multiple chunks
- ✅ Segments are numbered sequentially (1, 2, 3...)
- ✅ Segments are in chronological order
- ✅ All timestamps preserved correctly
- ✅ `SRTParser.format()` produces proper SRT format with spacing
- ✅ No trailing blank lines in formatted output
- ✅ 100% test coverage for new code
- ✅ Integration test validates end-to-end behavior
- ✅ Backward compatibility maintained
- ✅ Final SRT file works with standard video players

## Context7 Best Practices

Based on pysrt library documentation:
- SRT format requires one blank line between subtitle entries
- Sequential numbering starting from 1 is standard
- Timestamps must be preserved exactly
- Proper formatting ensures compatibility with video players

## References

- SRT format specification
- pysrt library documentation
- Current implementation in `translator/worker.py`
- Current `SRTParser.format()` implementation

