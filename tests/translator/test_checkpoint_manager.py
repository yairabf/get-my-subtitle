"""Tests for checkpoint manager functionality."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from common.schemas import TranslationCheckpoint
from common.subtitle_parser import SubtitleSegment
from translator.checkpoint_manager import CheckpointManager


class TestCheckpointManager:
    """Test CheckpointManager functionality."""

    @pytest.fixture
    def checkpoint_manager(self, tmp_path, monkeypatch):
        """Create CheckpointManager with temporary storage."""
        # Override storage path to use temporary directory
        monkeypatch.setattr(
            "translator.checkpoint_manager.settings",
            type(
                "obj",
                (object,),
                {
                    "checkpoint_storage_path": None,
                    "subtitle_storage_path": str(tmp_path),
                },
            )(),
        )
        return CheckpointManager()

    @pytest.fixture
    def sample_segments(self):
        """Create sample subtitle segments for testing."""
        return [
            SubtitleSegment(
                index=1,
                start_time="00:00:01,000",
                end_time="00:00:04,000",
                text="Hello world",
            ),
            SubtitleSegment(
                index=2,
                start_time="00:00:05,000",
                end_time="00:00:08,000",
                text="How are you?",
            ),
            SubtitleSegment(
                index=3,
                start_time="00:00:09,000",
                end_time="00:00:12,000",
                text="Goodbye!",
            ),
        ]

    @pytest.fixture
    def request_id(self):
        """Generate a test request ID."""
        return uuid4()

    def test_get_checkpoint_path(self, checkpoint_manager, request_id):
        """Test checkpoint path generation."""
        target_language = "es"
        checkpoint_path = checkpoint_manager.get_checkpoint_path(
            request_id, target_language
        )

        assert checkpoint_path.name == f"{request_id}.{target_language}.checkpoint.json"
        assert checkpoint_path.parent.exists()

    def test_checkpoint_exists_false(self, checkpoint_manager, request_id):
        """Test checkpoint_exists returns False when checkpoint doesn't exist."""
        assert checkpoint_manager.checkpoint_exists(request_id, "es") is False

    def test_checkpoint_exists_true(
        self, checkpoint_manager, request_id, sample_segments
    ):
        """Test checkpoint_exists returns True when checkpoint exists."""
        # Create a checkpoint first
        checkpoint_path = checkpoint_manager.get_checkpoint_path(request_id, "es")
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Save checkpoint
        import asyncio

        async def save():
            return await checkpoint_manager.save_checkpoint(
                request_id=request_id,
                subtitle_file_path="/path/to/subtitle.srt",
                source_language="en",
                target_language="es",
                total_chunks=5,
                completed_chunks=[0, 1],
                translated_segments=sample_segments[:2],
            )

        asyncio.run(save())

        # Check existence
        assert checkpoint_manager.checkpoint_exists(request_id, "es") is True

    def test_serialize_segments(self, checkpoint_manager, sample_segments):
        """Test serialization of SubtitleSegment objects."""
        serialized = checkpoint_manager._serialize_segments(sample_segments)

        assert len(serialized) == 3
        assert serialized[0]["index"] == 1
        assert serialized[0]["text"] == "Hello world"
        assert serialized[0]["start_time"] == "00:00:01,000"
        assert serialized[0]["end_time"] == "00:00:04,000"

    def test_deserialize_segments(self, checkpoint_manager, sample_segments):
        """Test deserialization of segment dictionaries."""
        serialized = checkpoint_manager._serialize_segments(sample_segments)
        deserialized = checkpoint_manager._deserialize_segments(serialized)

        assert len(deserialized) == 3
        assert deserialized[0].index == 1
        assert deserialized[0].text == "Hello world"
        assert deserialized[0].start_time == "00:00:01,000"
        assert deserialized[0].end_time == "00:00:04,000"

    def test_deserialize_segments_invalid_data(self, checkpoint_manager):
        """Test deserialization with invalid segment data."""
        invalid_data = [{"index": 1, "text": "Missing fields"}]

        with pytest.raises(ValueError, match="Invalid segment data"):
            checkpoint_manager._deserialize_segments(invalid_data)

    @pytest.mark.asyncio
    async def test_save_checkpoint(
        self, checkpoint_manager, request_id, sample_segments
    ):
        """Test saving a checkpoint."""
        checkpoint = await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=5,
            completed_chunks=[0, 1],
            translated_segments=sample_segments[:2],
        )

        assert checkpoint.request_id == request_id
        assert checkpoint.source_language == "en"
        assert checkpoint.target_language == "es"
        assert checkpoint.total_chunks == 5
        assert checkpoint.completed_chunks == [0, 1]
        assert len(checkpoint.translated_segments) == 2

        # Verify file was created
        checkpoint_path = checkpoint_manager.get_checkpoint_path(request_id, "es")
        assert checkpoint_path.exists()

        # Verify file content
        file_content = checkpoint_path.read_text(encoding="utf-8")
        loaded_data = json.loads(file_content)
        assert loaded_data["request_id"] == str(request_id)
        assert loaded_data["total_chunks"] == 5
        assert len(loaded_data["translated_segments"]) == 2

    @pytest.mark.asyncio
    async def test_save_checkpoint_preserves_created_at(
        self, checkpoint_manager, request_id, sample_segments
    ):
        """Test that saving checkpoint preserves created_at from existing checkpoint."""
        # Save initial checkpoint
        checkpoint1 = await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=5,
            completed_chunks=[0],
            translated_segments=sample_segments[:1],
        )

        original_created_at = checkpoint1.created_at

        # Save updated checkpoint
        checkpoint2 = await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=5,
            completed_chunks=[0, 1],
            translated_segments=sample_segments[:2],
        )

        # Created_at should be preserved
        assert checkpoint2.created_at == original_created_at
        # Updated_at should be different
        assert checkpoint2.updated_at != checkpoint1.updated_at

    @pytest.mark.asyncio
    async def test_load_checkpoint(
        self, checkpoint_manager, request_id, sample_segments
    ):
        """Test loading an existing checkpoint."""
        # Save checkpoint first
        await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=5,
            completed_chunks=[0, 1],
            translated_segments=sample_segments[:2],
        )

        # Load checkpoint
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(request_id, "es")

        assert loaded_checkpoint is not None
        assert loaded_checkpoint.request_id == request_id
        assert loaded_checkpoint.source_language == "en"
        assert loaded_checkpoint.target_language == "es"
        assert loaded_checkpoint.total_chunks == 5
        assert loaded_checkpoint.completed_chunks == [0, 1]
        assert len(loaded_checkpoint.translated_segments) == 2

    @pytest.mark.asyncio
    async def test_load_checkpoint_not_found(self, checkpoint_manager, request_id):
        """Test loading non-existent checkpoint."""
        loaded_checkpoint = await checkpoint_manager.load_checkpoint(request_id, "es")

        assert loaded_checkpoint is None

    @pytest.mark.asyncio
    async def test_load_checkpoint_corrupted_file(self, checkpoint_manager, request_id):
        """Test loading corrupted checkpoint file."""
        checkpoint_path = checkpoint_manager.get_checkpoint_path(request_id, "es")
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        checkpoint_path.write_text("invalid json content", encoding="utf-8")

        with pytest.raises(ValueError, match="Corrupted checkpoint file"):
            await checkpoint_manager.load_checkpoint(request_id, "es")

    @pytest.mark.asyncio
    async def test_deserialize_segments_from_checkpoint(
        self, checkpoint_manager, request_id, sample_segments
    ):
        """Test deserializing segments from checkpoint."""
        # Save checkpoint
        checkpoint = await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=5,
            completed_chunks=[0, 1],
            translated_segments=sample_segments[:2],
        )

        # Deserialize segments
        deserialized_segments = checkpoint_manager.deserialize_segments_from_checkpoint(
            checkpoint
        )

        assert len(deserialized_segments) == 2
        assert deserialized_segments[0].index == 1
        assert deserialized_segments[0].text == "Hello world"
        assert deserialized_segments[1].index == 2
        assert deserialized_segments[1].text == "How are you?"

    @pytest.mark.asyncio
    async def test_cleanup_checkpoint(
        self, checkpoint_manager, request_id, sample_segments
    ):
        """Test cleaning up checkpoint file."""
        # Save checkpoint first
        await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path="/path/to/subtitle.srt",
            source_language="en",
            target_language="es",
            total_chunks=5,
            completed_chunks=[0, 1],
            translated_segments=sample_segments[:2],
        )

        checkpoint_path = checkpoint_manager.get_checkpoint_path(request_id, "es")
        assert checkpoint_path.exists()

        # Cleanup checkpoint
        result = await checkpoint_manager.cleanup_checkpoint(request_id, "es")

        assert result is True
        assert not checkpoint_path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_checkpoint_not_found(self, checkpoint_manager, request_id):
        """Test cleaning up non-existent checkpoint."""
        result = await checkpoint_manager.cleanup_checkpoint(request_id, "es")

        assert result is False

    def test_get_checkpoint_directory_uses_custom_path(self, tmp_path, monkeypatch):
        """Test that custom checkpoint storage path is used when configured."""
        custom_path = tmp_path / "custom_checkpoints"
        monkeypatch.setattr(
            "translator.checkpoint_manager.settings",
            type(
                "obj",
                (object,),
                {
                    "checkpoint_storage_path": str(custom_path),
                    "subtitle_storage_path": str(tmp_path),
                },
            )(),
        )

        manager = CheckpointManager()
        checkpoint_path = manager.get_checkpoint_path(uuid4(), "es")

        assert custom_path in checkpoint_path.parents
        assert custom_path.exists()

    def test_get_checkpoint_directory_uses_default_path(self, tmp_path, monkeypatch):
        """Test that default checkpoint path is used when custom path not configured."""
        storage_path = tmp_path / "subtitles"
        monkeypatch.setattr(
            "translator.checkpoint_manager.settings",
            type(
                "obj",
                (object,),
                {
                    "checkpoint_storage_path": None,
                    "subtitle_storage_path": str(storage_path),
                },
            )(),
        )

        manager = CheckpointManager()
        checkpoint_path = manager.get_checkpoint_path(uuid4(), "es")

        expected_checkpoint_dir = storage_path / "checkpoints"
        assert expected_checkpoint_dir in checkpoint_path.parents
        assert expected_checkpoint_dir.exists()
