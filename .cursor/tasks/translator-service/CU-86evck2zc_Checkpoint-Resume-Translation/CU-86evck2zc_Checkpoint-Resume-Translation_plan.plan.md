---
epic: translator-service
task: CU-86evck2zc_Checkpoint-Resume-Translation
created: 2025-11-08
---

# Checkpoint & Resume Translation

## Overview

Implement a checkpoint system that saves partial translation progress to disk, enabling resumption after failures or interruptions. This prevents loss of work when translating large subtitle files or encountering transient errors.

## Problem Statement

Currently, if translation fails mid-process (e.g., API timeout, worker restart, network interruption), all progress is lost and the entire translation must restart from the beginning. This is inefficient for:
- Large subtitle files with many chunks
- Expensive API calls that have already succeeded
- Long-running translations that may be interrupted

The system needs to:
- Save progress after each successfully translated chunk
- Resume from the last completed chunk on restart
- Handle partial files gracefully
- Clean up checkpoint files after successful completion

## Architecture

### New Components

1. **Checkpoint Manager** (`translator/checkpoint_manager.py`)
   - Save checkpoint after each successful chunk translation
   - Load existing checkpoint on translation start
   - Clean up checkpoint files after completion
   - Store checkpoint metadata (request_id, chunks completed, remaining chunks, etc.)

2. **Checkpoint Data Model** (`common/schemas.py`)
   - `TranslationCheckpoint` Pydantic model
   - Fields: request_id, source_language, target_language, completed_chunks, total_chunks, translated_segments, checkpoint_path, created_at, updated_at

3. **Enhanced Translation Worker** (`translator/worker.py`)
   - Check for existing checkpoint before starting translation
   - Resume from checkpoint if found
   - Save checkpoint after each chunk completion
   - Merge checkpoint data with new translations
   - Clean up checkpoint on successful completion

### Checkpoint File Structure

Checkpoints stored in: `{subtitle_storage_path}/checkpoints/{request_id}.{target_language}.checkpoint.json`

Format:
```json
{
  "request_id": "uuid-string",
  "subtitle_file_path": "/path/to/source.srt",
  "source_language": "en",
  "target_language": "es",
  "total_chunks": 10,
  "completed_chunks": [0, 1, 2, 3],
  "translated_segments": [...],  // List of SubtitleSegment dicts
  "checkpoint_path": "/path/to/checkpoint.json",
  "created_at": "2025-01-27T10:00:00Z",
  "updated_at": "2025-01-27T10:05:00Z"
}
```

### Key Files

- `translator/checkpoint_manager.py` - New checkpoint management module
- `common/schemas.py` - Add `TranslationCheckpoint` model
- `translator/worker.py` - Integrate checkpoint save/load/resume logic
- `common/config.py` - Add checkpoint configuration (enable/disable, cleanup settings)
- `tests/translator/test_checkpoint_manager.py` - Checkpoint manager tests
- `tests/translator/test_worker.py` - Update with checkpoint/resume tests

## Implementation Steps

### Phase 1: Checkpoint Data Model

Add `TranslationCheckpoint` to `common/schemas.py`:
- Use Pydantic BaseModel for validation
- Include all necessary fields for resumption
- Add serialization methods for SubtitleSegment lists

### Phase 2: Checkpoint Manager

Create `translator/checkpoint_manager.py` with:

1. **CheckpointManager Class**:
   - `save_checkpoint()` - Save checkpoint after chunk completion
   - `load_checkpoint()` - Load existing checkpoint if available
   - `get_checkpoint_path()` - Generate checkpoint file path
   - `cleanup_checkpoint()` - Remove checkpoint file after completion
   - `checkpoint_exists()` - Check if checkpoint exists for request

2. **Checkpoint Operations**:
   - Serialize translated segments to JSON-compatible format
   - Deserialize segments back to SubtitleSegment objects
   - Handle file I/O with proper error handling
   - Ensure checkpoint directory exists

### Phase 3: Integration with Translation Worker

Update `translator/worker.py`:

1. **Before Translation**:
   - Check for existing checkpoint using `CheckpointManager.load_checkpoint()`
   - If checkpoint exists:
     - Load completed segments
     - Determine remaining chunks to process
     - Log resumption information

2. **During Translation**:
   - After each successful chunk translation:
     - Append translated segments to checkpoint
     - Update completed_chunks list
     - Save checkpoint using `CheckpointManager.save_checkpoint()`
   - Continue processing remaining chunks

3. **After Translation**:
   - On successful completion:
     - Clean up checkpoint file
     - Log completion
   - On failure:
     - Checkpoint already saved (last successful chunk)
     - Log failure for manual resume

### Phase 4: Configuration

Add to `common/config.py`:
- `checkpoint_enabled: bool = True` - Enable/disable checkpointing
- `checkpoint_cleanup_on_success: bool = True` - Auto-cleanup on completion
- `checkpoint_storage_path: Optional[str] = None` - Override checkpoint location (defaults to `{subtitle_storage_path}/checkpoints`)

### Phase 5: Error Handling

- Handle corrupted checkpoint files gracefully
- Validate checkpoint data before resuming
- Fall back to full translation if checkpoint invalid
- Log warnings for checkpoint issues

### Phase 6: Testing

1. **Unit Tests** (`test_checkpoint_manager.py`):
   - Test checkpoint save/load operations
   - Test checkpoint file path generation
   - Test cleanup operations
   - Test serialization/deserialization of segments
   - Test error handling (corrupted files, missing files)

2. **Integration Tests** (`test_worker.py`):
   - Test full translation with checkpoint saves
   - Test resume from checkpoint after interruption
   - Test resume with partial progress
   - Test cleanup after successful completion
   - Test checkpoint persistence across worker restarts
   - Test error recovery with checkpoint

## API Changes

None - internal enhancement only. Translation API remains unchanged.

## Testing Strategy

### Unit Tests

1. **CheckpointManager Tests**:
   - Save checkpoint with valid data
   - Load checkpoint successfully
   - Handle missing checkpoint file
   - Handle corrupted checkpoint file
   - Cleanup checkpoint file
   - Serialize/deserialize SubtitleSegment objects

2. **Worker Integration Tests**:
   - Translation with checkpoint saves after each chunk
   - Resume from checkpoint mid-translation
   - Complete translation after resume
   - Cleanup checkpoint on completion
   - Handle checkpoint errors gracefully

### Integration Considerations

- Checkpoint files stored alongside subtitle files
- Checkpoint directory created automatically
- Checkpoint cleanup prevents disk space issues
- Redis status updates continue to work
- Event publishing unchanged
- RabbitMQ message processing unchanged

## Success Criteria

- ✅ Checkpoint saved after each successfully translated chunk
- ✅ Translation resumes from last completed chunk on restart
- ✅ Checkpoint files cleaned up after successful completion
- ✅ Corrupted checkpoint files handled gracefully
- ✅ Checkpoint system configurable (enable/disable)
- ✅ No loss of translation progress on worker restart
- ✅ Checkpoint data validated before resumption
- ✅ 100% test coverage for checkpoint functionality
- ✅ All existing tests pass
- ✅ Checkpoint files stored in organized directory structure
- ✅ Performance impact minimal (async file I/O)

## Design Patterns Used

- **Memento Pattern**: Checkpoint acts as memento storing translation state
- **Strategy Pattern**: Configurable checkpoint behavior (enabled/disabled)
- **Facade Pattern**: CheckpointManager provides simple interface to complex checkpoint operations



