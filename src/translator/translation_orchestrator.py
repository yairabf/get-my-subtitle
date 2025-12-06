"""Translation orchestration logic with checkpoint support."""

import asyncio
import logging
from typing import List
from uuid import UUID

from common.config import settings
from common.subtitle_parser import (
    SubtitleSegment,
    extract_text_for_translation,
    merge_translated_chunks,
    merge_translations,
    split_subtitle_content,
)
from translator.checkpoint_manager import CheckpointManager
from translator.schemas import CheckpointState, TranslationTaskData
from translator.translation_service import SubtitleTranslator

logger = logging.getLogger(__name__)


async def load_checkpoint_state(
    request_id: UUID,
    subtitle_file_path: str,
    source_language: str,
    target_language: str,
) -> CheckpointState:
    """
    Load checkpoint state if available and valid.

    Args:
        request_id: Unique identifier for the translation request
        subtitle_file_path: Path to source subtitle file
        source_language: Source language code
        target_language: Target language code

    Returns:
        CheckpointState object with checkpoint information
    """
    from translator.message_handler import validate_checkpoint_metadata

    checkpoint_manager = CheckpointManager()
    checkpoint = None
    all_translated_segments = []
    start_chunk_idx = 0

    if settings.checkpoint_enabled:
        try:
            checkpoint = await checkpoint_manager.load_checkpoint(
                request_id, target_language
            )
            if checkpoint:
                logger.info(
                    f"📂 Found checkpoint: {len(checkpoint.completed_chunks)}/"
                    f"{checkpoint.total_chunks} chunks completed"
                )

                # Validate checkpoint matches current request
                if validate_checkpoint_metadata(
                    checkpoint, subtitle_file_path, source_language, target_language
                ):
                    # Deserialize segments from checkpoint
                    all_translated_segments = (
                        checkpoint_manager.deserialize_segments_from_checkpoint(
                            checkpoint
                        )
                    )
                    start_chunk_idx = len(checkpoint.completed_chunks)
                    logger.info(
                        f"🔄 Resuming translation from chunk {start_chunk_idx + 1}"
                    )
                else:
                    logger.warning(
                        "⚠️  Checkpoint metadata mismatch, starting fresh translation"
                    )
                    checkpoint = None
        except Exception as e:
            logger.warning(
                f"⚠️  Failed to load checkpoint, starting fresh translation: {e}"
            )
            checkpoint = None

    return CheckpointState(
        checkpoint=checkpoint,
        all_translated_segments=all_translated_segments,
        start_chunk_idx=start_chunk_idx,
    )


async def translate_segments_with_checkpoint(
    segments: List[SubtitleSegment],
    task_data: TranslationTaskData,
    translator: SubtitleTranslator,
    checkpoint_state: CheckpointState,
) -> List[SubtitleSegment]:
    """
    Translate subtitle segments, resuming from checkpoint if available.

    Args:
        segments: List of subtitle segments to translate
        task_data: Translation task data
        translator: SubtitleTranslator instance
        checkpoint_state: Checkpoint state information

    Returns:
        List of translated subtitle segments

    Raises:
        Exception: If translation fails for any chunk
    """
    # Split into token-aware chunks for API limits
    chunks = split_subtitle_content(
        segments,
        max_tokens=settings.translation_max_tokens_per_chunk,
        model=settings.openai_model,
        safety_margin=settings.translation_token_safety_margin,
        max_segments_per_chunk=settings.translation_max_segments_per_chunk,
    )

    # If checkpoint exists, validate total chunks match
    if (
        checkpoint_state.checkpoint
        and checkpoint_state.checkpoint.total_chunks != len(chunks)
    ):
        logger.warning(
            f"⚠️  Checkpoint total_chunks ({checkpoint_state.checkpoint.total_chunks}) doesn't match "
            f"current chunks ({len(chunks)}), starting fresh translation"
        )
        checkpoint_state.checkpoint = None
        checkpoint_state.all_translated_segments = []
        checkpoint_state.start_chunk_idx = 0

    # Translate remaining chunks in parallel
    parallel_requests = settings.get_translation_parallel_requests()
    semaphore = asyncio.Semaphore(parallel_requests)

    logger.info(
        f"🚀 Starting parallel translation of {len(chunks) - checkpoint_state.start_chunk_idx} chunks "
        f"with {parallel_requests} concurrent requests"
    )

    async def _translate_chunk_parallel(
        chunk_idx: int,
        chunk: List[SubtitleSegment],
        semaphore: asyncio.Semaphore,
    ) -> tuple[int, List[SubtitleSegment]]:
        """
        Translate a single chunk with semaphore-controlled concurrency.

        Args:
            chunk_idx: Index of the chunk being translated
            chunk: List of SubtitleSegment objects to translate
            semaphore: Semaphore to limit concurrent API requests

        Returns:
            Tuple of (chunk_idx, translated_chunk) for ordering
        """
        async with semaphore:
            logger.info(
                f"🔄 Translating chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} segments)"
            )

            # Extract text from segments
            texts = extract_text_for_translation(chunk)

            # Translate
            translations = await translator.translate_batch(
                texts, task_data.source_language, task_data.target_language
            )

            # Get parsed segment numbers if available (for accurate missing segment identification)
            parsed_segment_numbers = translator.get_last_parsed_segment_numbers()

            # Merge translations back (with chunk context for better error messages)
            translated_chunk = merge_translations(
                chunk,
                translations,
                chunk_index=chunk_idx,
                total_chunks=len(chunks),
                parsed_segment_numbers=parsed_segment_numbers,
            )

            logger.info(
                f"✅ Completed chunk {chunk_idx + 1}/{len(chunks)} "
                f"({len(translated_chunk)} segments translated)"
            )

            return chunk_idx, translated_chunk

    # Create tasks for all remaining chunks
    tasks = [
        _translate_chunk_parallel(chunk_idx, chunk, semaphore)
        for chunk_idx, chunk in enumerate(
            chunks[checkpoint_state.start_chunk_idx :], checkpoint_state.start_chunk_idx
        )
    ]

    # Execute all chunks in parallel (results may complete out of order)
    logger.info(f"⚡ Executing {len(tasks)} translation tasks in parallel...")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results and handle any exceptions
    valid_results = []
    failed_chunks = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            chunk_idx = checkpoint_state.start_chunk_idx + i
            logger.error(
                f"❌ Chunk {chunk_idx + 1}/{len(chunks)} translation failed: {result}"
            )
            failed_chunks.append((chunk_idx, result))
        else:
            valid_results.append(result)

    # If any chunks failed, raise an error with context about which chunks failed
    if failed_chunks:
        failed_indices = [idx for idx, _ in failed_chunks]
        error_msg = (
            f"Translation failed for {len(failed_chunks)} chunk(s): "
            f"{', '.join(f'chunk {idx + 1}' for idx in failed_indices)}. "
            f"First error: {failed_chunks[0][1]}"
        )
        logger.error(f"❌ {error_msg}")
        # Raise the first exception to maintain backward compatibility
        raise failed_chunks[0][1]

    # Sort by chunk_idx to ensure segments are in correct order
    valid_results.sort(key=lambda x: x[0])

    # Extend segments in correct order
    completed_chunk_indices = []
    for chunk_idx, translated_chunk in valid_results:
        checkpoint_state.all_translated_segments.extend(translated_chunk)
        completed_chunk_indices.append(chunk_idx)

    if completed_chunk_indices:
        chunk_range = (
            f"{min(completed_chunk_indices) + 1}-{max(completed_chunk_indices) + 1}"
        )
        logger.info(
            f"✅ Completed parallel translation batch: "
            f"{len(completed_chunk_indices)} chunks ({chunk_range})"
        )
    else:
        logger.info("✅ No chunks to translate")

    # Save checkpoint after parallel batch completion
    if settings.checkpoint_enabled:
        try:
            checkpoint_manager = CheckpointManager()
            # Include all previously completed chunks plus newly completed ones
            all_completed_chunks = (
                list(range(checkpoint_state.start_chunk_idx)) + completed_chunk_indices
            )
            await checkpoint_manager.save_checkpoint(
                request_id=task_data.request_id,
                subtitle_file_path=task_data.subtitle_file_path,
                source_language=task_data.source_language,
                target_language=task_data.target_language,
                total_chunks=len(chunks),
                completed_chunks=all_completed_chunks,
                translated_segments=checkpoint_state.all_translated_segments,
            )
            logger.info(
                f"💾 Saved checkpoint: {len(all_completed_chunks)}/{len(chunks)} chunks completed"
            )
        except Exception as e:
            logger.warning(
                f"⚠️  Failed to save checkpoint after parallel batch: {e}"
            )
            # Continue translation even if checkpoint save fails

    # Merge and renumber translated segments
    merged_segments = merge_translated_chunks(checkpoint_state.all_translated_segments)
    logger.info(
        f"✅ Merged {len(checkpoint_state.all_translated_segments)} segments into "
        f"{len(merged_segments)} sequentially numbered segments"
    )

    return merged_segments

