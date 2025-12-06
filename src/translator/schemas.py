"""Data structures for translation task processing."""

from typing import List, Optional
from uuid import UUID

from common.schemas import TranslationCheckpoint
from common.subtitle_parser import SubtitleSegment


class TranslationTaskData:
    """Data structure for parsed translation task."""

    def __init__(
        self,
        request_id: UUID,
        subtitle_file_path: str,
        source_language: str,
        target_language: str,
    ):
        self.request_id = request_id
        self.subtitle_file_path = subtitle_file_path
        self.source_language = source_language
        self.target_language = target_language


class CheckpointState:
    """State information for checkpoint resumption."""

    def __init__(
        self,
        checkpoint: Optional[TranslationCheckpoint],
        all_translated_segments: List[SubtitleSegment],
        start_chunk_idx: int,
    ):
        self.checkpoint = checkpoint
        self.all_translated_segments = all_translated_segments
        self.start_chunk_idx = start_chunk_idx
