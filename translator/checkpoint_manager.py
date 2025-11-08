"""Checkpoint manager for saving and resuming translation progress."""

import json
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from common.config import settings
from common.schemas import TranslationCheckpoint
from common.subtitle_parser import SubtitleSegment
from common.utils import DateTimeUtils

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoint save/load/cleanup operations for translation resumption."""

    def __init__(self):
        """Initialize the checkpoint manager."""
        self._checkpoint_dir = self._get_checkpoint_directory()

    def _get_checkpoint_directory(self) -> Path:
        """
        Get the checkpoint storage directory path.

        Returns:
            Path to checkpoint directory
        """
        if settings.checkpoint_storage_path:
            checkpoint_path = Path(settings.checkpoint_storage_path)
        else:
            storage_path = Path(settings.subtitle_storage_path)
            checkpoint_path = storage_path / "checkpoints"

        # Ensure directory exists
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        return checkpoint_path

    def get_checkpoint_path(self, request_id: UUID, target_language: str) -> Path:
        """
        Generate checkpoint file path for a translation request.

        Args:
            request_id: Unique identifier for the translation request
            target_language: Target language code

        Returns:
            Path to checkpoint file
        """
        filename = f"{request_id}.{target_language}.checkpoint.json"
        return self._checkpoint_dir / filename

    def checkpoint_exists(self, request_id: UUID, target_language: str) -> bool:
        """
        Check if a checkpoint exists for the given request.

        Args:
            request_id: Unique identifier for the translation request
            target_language: Target language code

        Returns:
            True if checkpoint exists, False otherwise
        """
        checkpoint_path = self.get_checkpoint_path(request_id, target_language)
        return checkpoint_path.exists()

    def _serialize_segments(self, segments: List[SubtitleSegment]) -> List[dict]:
        """
        Serialize SubtitleSegment objects to dictionaries.

        Args:
            segments: List of SubtitleSegment objects

        Returns:
            List of dictionaries representing segments
        """
        return [
            {
                "index": segment.index,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "text": segment.text,
            }
            for segment in segments
        ]

    def _deserialize_segments(self, segment_dicts: List[dict]) -> List[SubtitleSegment]:
        """
        Deserialize dictionaries back to SubtitleSegment objects.

        Args:
            segment_dicts: List of dictionaries representing segments

        Returns:
            List of SubtitleSegment objects

        Raises:
            ValueError: If segment data is invalid
        """
        segments = []
        for segment_dict in segment_dicts:
            try:
                segment = SubtitleSegment(
                    index=segment_dict["index"],
                    start_time=segment_dict["start_time"],
                    end_time=segment_dict["end_time"],
                    text=segment_dict["text"],
                )
                segments.append(segment)
            except (KeyError, TypeError) as e:
                raise ValueError(f"Invalid segment data: {e}") from e
        return segments

    async def save_checkpoint(
        self,
        request_id: UUID,
        subtitle_file_path: str,
        source_language: str,
        target_language: str,
        total_chunks: int,
        completed_chunks: List[int],
        translated_segments: List[SubtitleSegment],
    ) -> TranslationCheckpoint:
        """
        Save checkpoint after successful chunk translation.

        Args:
            request_id: Unique identifier for the translation request
            subtitle_file_path: Path to source subtitle file
            source_language: Source language code
            target_language: Target language code
            total_chunks: Total number of chunks
            completed_chunks: List of completed chunk indices (0-based)
            translated_segments: List of translated segments

        Returns:
            TranslationCheckpoint object

        Raises:
            IOError: If checkpoint file cannot be written
        """
        checkpoint_path = self.get_checkpoint_path(request_id, target_language)

        # Check if checkpoint exists to preserve created_at
        existing_checkpoint = None
        if checkpoint_path.exists():
            try:
                existing_checkpoint = await self.load_checkpoint(
                    request_id, target_language
                )
            except Exception as e:
                logger.warning(
                    f"Could not load existing checkpoint to preserve created_at: {e}"
                )

        # Serialize segments
        segment_dicts = self._serialize_segments(translated_segments)

        # Create checkpoint
        checkpoint = TranslationCheckpoint(
            request_id=request_id,
            subtitle_file_path=subtitle_file_path,
            source_language=source_language,
            target_language=target_language,
            total_chunks=total_chunks,
            completed_chunks=completed_chunks,
            translated_segments=segment_dicts,
            checkpoint_path=str(checkpoint_path),
            created_at=(
                existing_checkpoint.created_at
                if existing_checkpoint
                else DateTimeUtils.get_current_utc_datetime()
            ),
            updated_at=DateTimeUtils.get_current_utc_datetime(),
        )

        # Write checkpoint file
        try:
            checkpoint_path.write_text(
                checkpoint.model_dump_json(indent=2), encoding="utf-8"
            )
            logger.info(
                f"✅ Saved checkpoint: {checkpoint_path} "
                f"({len(completed_chunks)}/{total_chunks} chunks completed)"
            )
        except Exception as e:
            logger.error(f"❌ Failed to save checkpoint: {e}")
            raise IOError(f"Failed to save checkpoint: {e}") from e

        return checkpoint

    async def load_checkpoint(
        self, request_id: UUID, target_language: str
    ) -> Optional[TranslationCheckpoint]:
        """
        Load existing checkpoint if available.

        Args:
            request_id: Unique identifier for the translation request
            target_language: Target language code

        Returns:
            TranslationCheckpoint object if found, None otherwise

        Raises:
            FileNotFoundError: If checkpoint file doesn't exist
            ValueError: If checkpoint data is invalid or corrupted
        """
        checkpoint_path = self.get_checkpoint_path(request_id, target_language)

        if not checkpoint_path.exists():
            return None

        try:
            # Read checkpoint file
            checkpoint_data = checkpoint_path.read_text(encoding="utf-8")
            checkpoint_dict = json.loads(checkpoint_data)

            # Validate and create checkpoint object
            checkpoint = TranslationCheckpoint.model_validate(checkpoint_dict)

            logger.info(
                f"✅ Loaded checkpoint: {checkpoint_path} "
                f"({len(checkpoint.completed_chunks)}/{checkpoint.total_chunks} chunks completed)"
            )

            return checkpoint

        except json.JSONDecodeError as e:
            logger.error(f"❌ Corrupted checkpoint file: {checkpoint_path} - {e}")
            raise ValueError(f"Corrupted checkpoint file: {e}") from e
        except Exception as e:
            logger.error(f"❌ Failed to load checkpoint: {checkpoint_path} - {e}")
            raise ValueError(f"Failed to load checkpoint: {e}") from e

    def deserialize_segments_from_checkpoint(
        self, checkpoint: TranslationCheckpoint
    ) -> List[SubtitleSegment]:
        """
        Deserialize segments from checkpoint.

        Args:
            checkpoint: TranslationCheckpoint object

        Returns:
            List of SubtitleSegment objects

        Raises:
            ValueError: If segment data is invalid
        """
        return self._deserialize_segments(checkpoint.translated_segments)

    async def cleanup_checkpoint(self, request_id: UUID, target_language: str) -> bool:
        """
        Remove checkpoint file after successful completion.

        Args:
            request_id: Unique identifier for the translation request
            target_language: Target language code

        Returns:
            True if checkpoint was removed, False if it didn't exist
        """
        checkpoint_path = self.get_checkpoint_path(request_id, target_language)

        if not checkpoint_path.exists():
            logger.debug(f"Checkpoint file does not exist: {checkpoint_path}")
            return False

        try:
            checkpoint_path.unlink()
            logger.info(f"✅ Cleaned up checkpoint: {checkpoint_path}")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Failed to cleanup checkpoint: {checkpoint_path} - {e}")
            return False
