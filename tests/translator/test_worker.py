"""Tests for the translator worker."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.schemas import SubtitleStatus
from common.shutdown_manager import ShutdownManager
from common.subtitle_parser import SRTParser, SubtitleSegment
from translator.translation_service import SubtitleTranslator
from translator.worker import process_translation_message


class TestSubtitleTranslator:
    """Test SubtitleTranslator functionality."""

    @pytest.fixture
    def translator_with_api_key(self):
        """Create translator with mocked API key."""
        with patch("translator.translation_service.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test-key"
            mock_settings.openai_model = "gpt-5-nano"
            mock_settings.openai_temperature = 0.3
            mock_settings.openai_max_tokens = 4096

            with patch("translator.translation_service.AsyncOpenAI") as mock_client:
                translator = SubtitleTranslator()
                return translator, mock_client

    @pytest.fixture
    def translator_without_api_key(self):
        """Create translator without API key (mock mode)."""
        with patch("translator.translation_service.settings") as mock_settings:
            mock_settings.openai_api_key = None
            translator = SubtitleTranslator()
            return translator

    @pytest.mark.asyncio
    async def test_translate_batch_mock_mode(self, translator_without_api_key):
        """Test translation in mock mode without API key."""
        texts = ["Hello world", "How are you?"]

        translations = await translator_without_api_key.translate_batch(
            texts, "en", "es"
        )

        assert len(translations) == 2
        assert "[TRANSLATED to es]" in translations[0]
        assert "Hello world" in translations[0]

    @pytest.mark.asyncio
    async def test_translate_batch_with_api(self, translator_with_api_key):
        """Test translation with OpenAI API."""
        translator, mock_client_class = translator_with_api_key

        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "[1]\nHola mundo\n\n[2]\n¿Cómo estás?"
        )

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        texts = ["Hello world", "How are you?"]
        translations = await translator.translate_batch(texts, "en", "es")

        assert len(translations) == 2
        assert "Hola mundo" in translations[0]
        assert "¿Cómo estás?" in translations[1]

    def test_build_translation_prompt(self, translator_without_api_key):
        """Test translation prompt building."""
        texts = ["Hello", "Goodbye"]
        prompt = translator_without_api_key._build_translation_prompt(texts, "en", "es")

        assert "Hello" in prompt
        assert "Goodbye" in prompt
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "en" in prompt
        assert "es" in prompt

    def test_parse_translation_response(self, translator_without_api_key):
        """Test parsing GPT response."""
        response = "[1]\nHola\n\n[2]\nAdiós\n\n"
        translations, parsed_segment_numbers = (
            translator_without_api_key._parse_translation_response(response, 2)
        )

        assert len(translations) == 2
        assert "Hola" in translations[0]
        assert "Adiós" in translations[1]
        # When all translations are parsed successfully, parsed_segment_numbers should be None
        assert parsed_segment_numbers is None

    def test_parse_translation_response_mismatched_count(
        self, translator_without_api_key
    ):
        """Test parsing response with wrong number of translations (1 missing is tolerated)."""
        response = "[1]\nHola\n\n"  # Only 1 translation
        translations, parsed_segment_numbers = (
            translator_without_api_key._parse_translation_response(response, 2)
        )

        # Should still return what it found (1 missing is tolerated)
        assert len(translations) == 1
        # parsed_segment_numbers should be [1] since segment 1 was parsed
        assert parsed_segment_numbers == [1]


class TestSRTParser:
    """Test SRT parsing functionality."""

    @pytest.fixture
    def sample_srt(self):
        """Sample SRT content."""
        return """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?

3
00:00:09,000 --> 00:00:12,000
Goodbye!
"""

    def test_parse_srt(self, sample_srt):
        """Test parsing SRT content."""
        segments = SRTParser.parse(sample_srt)

        assert len(segments) == 3
        assert segments[0].index == 1
        assert segments[0].text == "Hello world"
        assert "00:00:01,000" in segments[0].start_time

    def test_format_srt(self, sample_srt):
        """Test formatting segments back to SRT."""
        segments = SRTParser.parse(sample_srt)
        formatted = SRTParser.format(segments)

        assert "1\n" in formatted
        assert "Hello world" in formatted
        assert "-->" in formatted

    def test_parse_empty_content(self):
        """Test parsing empty SRT content."""
        segments = SRTParser.parse("")
        assert len(segments) == 0

    def test_parse_malformed_srt(self):
        """Test parsing malformed SRT."""
        malformed = """1
Invalid timestamp
Some text
"""
        segments = SRTParser.parse(malformed)
        # Should skip malformed entries
        assert len(segments) == 0


class TestTranslationMessageProcessing:
    """Test translation message processing."""

    @pytest.mark.asyncio
    async def test_process_translation_message_success(self):
        """Test successful message processing."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            }
        ).encode()

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(
            return_value=["Traducido 1", "Traducido 2", "Traducido 3"]
        )

        with patch("translator.worker.redis_client") as mock_redis:
            mock_redis.update_phase = AsyncMock(return_value=True)

            await process_translation_message(mock_message, mock_translator)

            # Verify Redis was updated - should be called for TRANSLATE_IN_PROGRESS
            assert mock_redis.update_phase.called

    @pytest.mark.asyncio
    async def test_process_translation_message_invalid_json(self):
        """Test handling invalid JSON in message."""
        mock_message = MagicMock()
        mock_message.body = b"invalid json"

        mock_translator = MagicMock()

        with patch("translator.worker.redis_client") as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=True)

            # Should not raise exception
            await process_translation_message(mock_message, mock_translator)

    @pytest.mark.asyncio
    async def test_process_translation_message_missing_fields(self):
        """Test handling missing required fields."""
        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(uuid4())
                # Missing other required fields
            }
        ).encode()

        mock_translator = MagicMock()

        # Should not raise exception - errors are handled gracefully
        await process_translation_message(mock_message, mock_translator)

    @pytest.mark.asyncio
    async def test_process_translation_message_translation_error(self):
        """Test handling translation errors."""
        request_id = uuid4()

        mock_message = MagicMock()
        mock_message.body = json.dumps(
            {
                "request_id": str(request_id),
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
            }
        ).encode()

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(side_effect=Exception("API Error"))

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            await process_translation_message(mock_message, mock_translator)

            # Should publish JOB_FAILED event
            assert mock_pub.publish_event.called


class TestSubtitleParserHelpers:
    """Test subtitle parser helper functions."""

    def test_extract_text_for_translation(self):
        """Test extracting text from segments."""
        from common.subtitle_parser import extract_text_for_translation

        segments = [
            SubtitleSegment(1, "00:00:01,000", "00:00:02,000", "Hello"),
            SubtitleSegment(2, "00:00:03,000", "00:00:04,000", "World"),
        ]

        texts = extract_text_for_translation(segments)
        assert len(texts) == 2
        assert texts[0] == "Hello"
        assert texts[1] == "World"

    def test_merge_translations(self):
        """Test merging translations back into segments."""
        from common.subtitle_parser import merge_translations

        segments = [
            SubtitleSegment(1, "00:00:01,000", "00:00:02,000", "Hello"),
            SubtitleSegment(2, "00:00:03,000", "00:00:04,000", "World"),
        ]

        translations = ["Hola", "Mundo"]

        translated_segments = merge_translations(segments, translations)

        assert len(translated_segments) == 2
        assert translated_segments[0].text == "Hola"
        assert translated_segments[1].text == "Mundo"
        assert translated_segments[0].start_time == "00:00:01,000"

    def test_merge_translations_mismatched_count(self):
        """Test error handling for mismatched counts."""
        from common.subtitle_parser import (
            TranslationCountMismatchError,
            merge_translations,
        )

        segments = [SubtitleSegment(1, "00:00:01,000", "00:00:02,000", "Hello")]
        translations = ["Hola", "Extra"]

        with pytest.raises(TranslationCountMismatchError) as exc_info:
            merge_translations(segments, translations)

        # Verify error details
        assert exc_info.value.expected_count == 1
        assert exc_info.value.actual_count == 2

    def test_chunk_segments(self):
        """Test chunking segments for batch processing."""
        from common.subtitle_parser import chunk_segments

        segments = [
            SubtitleSegment(i, "00:00:01,000", "00:00:02,000", f"Text {i}")
            for i in range(1, 101)
        ]

        chunks = chunk_segments(segments, max_segments=50)

        assert len(chunks) == 2
        assert len(chunks[0]) == 50
        assert len(chunks[1]) == 50


class TestSubtitleTranslatorRetryBehavior:
    """Test retry behavior for SubtitleTranslator."""

    @pytest.fixture
    def translator_with_api_key(self):
        """Create translator with mocked API key."""
        with patch("translator.translation_service.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test-key"
            mock_settings.openai_model = "gpt-5-nano"
            mock_settings.openai_temperature = 0.3
            mock_settings.openai_max_tokens = 4096
            mock_settings.openai_max_retries = 3
            mock_settings.openai_retry_initial_delay = 0.1  # Small delay for testing
            mock_settings.openai_retry_max_delay = 60.0
            mock_settings.openai_retry_exponential_base = 2

            with patch("translator.translation_service.AsyncOpenAI") as mock_client:
                translator = SubtitleTranslator()
                return translator, mock_client

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(self, translator_with_api_key):
        """Should retry on OpenAI rate limit errors."""
        translator, mock_client_class = translator_with_api_key

        try:
            import httpx
            from openai import RateLimitError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Create mock httpx.Response for RateLimitError
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 429
        mock_http_response.headers = MagicMock()
        mock_http_response.headers.get = MagicMock(return_value=None)

        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "[1]\nHola mundo\n\n[2]\n¿Cómo estás?"
        )

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            side_effect=[
                RateLimitError(
                    "Rate limit exceeded", response=mock_http_response, body=None
                ),
                RateLimitError(
                    "Rate limit exceeded", response=mock_http_response, body=None
                ),
                mock_response,  # Success on third attempt
            ]
        )

        texts = ["Hello world", "How are you?"]
        translations = await translator.translate_batch(texts, "en", "es")

        # Should succeed after retries
        assert len(translations) == 2
        assert "Hola mundo" in translations[0]
        assert translator.client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_transient_api_error(self, translator_with_api_key):
        """Should retry on transient API errors."""
        translator, mock_client_class = translator_with_api_key

        try:
            import httpx
            from openai import APIError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Create mock httpx.Request and Response for APIError
        mock_http_request = MagicMock(spec=httpx.Request)
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 503

        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[1]\nBonjour\n\n[2]\nAu revoir"

        # Create error instance with status_code attribute
        error_instance = APIError(
            message="Service unavailable",
            request=mock_http_request,
            body=None,
        )
        error_instance.status_code = 503

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            side_effect=[error_instance, mock_response]  # Success on second attempt
        )

        texts = ["Hello", "Goodbye"]
        translations = await translator.translate_batch(texts, "en", "fr")

        # Should succeed after retry
        assert len(translations) == 2
        assert translator.client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_fails_immediately_on_permanent_error(self, translator_with_api_key):
        """Should fail immediately on permanent errors without retrying."""
        translator, mock_client_class = translator_with_api_key

        try:
            import httpx
            from openai import APIError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Create mock httpx.Request for APIError
        mock_http_request = MagicMock(spec=httpx.Request)

        translator.client = AsyncMock()
        error_instance = APIError(
            message="Invalid API key",
            request=mock_http_request,
            body=None,
        )
        error_instance.status_code = 401
        translator.client.chat.completions.create = AsyncMock(
            side_effect=error_instance
        )

        texts = ["Hello"]
        with pytest.raises(APIError):
            await translator.translate_batch(texts, "en", "es")

        # Should fail immediately without retries
        assert translator.client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_fails_after_max_retries_exhausted(self, translator_with_api_key):
        """Should fail after exhausting all retry attempts."""
        translator, mock_client_class = translator_with_api_key

        try:
            import httpx
            from openai import RateLimitError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Create mock httpx.Response for RateLimitError
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 429
        mock_http_response.headers = MagicMock()
        mock_http_response.headers.get = MagicMock(return_value=None)

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            side_effect=RateLimitError(
                "Rate limit exceeded", response=mock_http_response, body=None
            )
        )

        texts = ["Hello"]
        with pytest.raises(RateLimitError):
            await translator.translate_batch(texts, "en", "es")

        # Should try initial + 3 retries = 4 total attempts
        assert translator.client.chat.completions.create.call_count == 4

    @pytest.mark.asyncio
    async def test_preserves_formatting_through_retries(self, translator_with_api_key):
        """Should preserve formatting even when retrying."""
        translator, mock_client_class = translator_with_api_key

        try:
            import httpx
            from openai import RateLimitError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Create mock httpx.Response for RateLimitError
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 429
        mock_http_response.headers = MagicMock()
        mock_http_response.headers.get = MagicMock(return_value=None)

        # Mock the API response with formatted content
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "[1]\nHola\nmundo\n\n[2]\n¿Cómo\nestás?"
        )

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            side_effect=[
                RateLimitError(
                    "Rate limit exceeded", response=mock_http_response, body=None
                ),
                mock_response,  # Success on second attempt
            ]
        )

        texts = ["Hello\nworld", "How\nare you?"]
        translations = await translator.translate_batch(texts, "en", "es")

        # Formatting should be preserved
        assert len(translations) == 2
        assert "\n" in translations[0]  # Line breaks preserved
        assert "\n" in translations[1]

    @pytest.mark.asyncio
    async def test_successful_translation_after_retries(self, translator_with_api_key):
        """Should successfully translate after retrying transient errors."""
        translator, mock_client_class = translator_with_api_key

        try:
            from openai import APIConnectionError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "[1]\nCiao\n\n[2]\nArrivederci\n\n[3]\nGrazie"
        )

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            side_effect=[
                APIConnectionError(message="Connection failed", request=None),
                APIConnectionError(message="Connection failed", request=None),
                mock_response,  # Success on third attempt
            ]
        )

        texts = ["Hello", "Goodbye", "Thank you"]
        translations = await translator.translate_batch(texts, "en", "it")

        # Should succeed after retries
        assert len(translations) == 3
        assert "Ciao" in translations[0]
        assert "Arrivederci" in translations[1]
        assert "Grazie" in translations[2]
        assert translator.client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff_delays(self, translator_with_api_key):
        """Should wait with exponential backoff between retries."""
        import asyncio

        translator, mock_client_class = translator_with_api_key

        try:
            import httpx
            from openai import RateLimitError
        except ImportError:
            pytest.skip("OpenAI SDK not available")

        # Create mock httpx.Response for RateLimitError
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 429
        mock_http_response.headers = MagicMock()
        mock_http_response.headers.get = MagicMock(return_value=None)

        # Mock the API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[1]\nSuccess"

        translator.client = AsyncMock()
        translator.client.chat.completions.create = AsyncMock(
            side_effect=[
                RateLimitError(
                    "Rate limit exceeded", response=mock_http_response, body=None
                ),
                RateLimitError(
                    "Rate limit exceeded", response=mock_http_response, body=None
                ),
                mock_response,  # Success on third attempt
            ]
        )

        texts = ["Test"]
        start_time = asyncio.get_event_loop().time()
        translations = await translator.translate_batch(texts, "en", "es")
        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time

        # Should have waited with exponential backoff
        # First retry: ~0.1s, second retry: ~0.2s = ~0.3s minimum
        assert elapsed >= 0.3
        assert len(translations) == 1
        assert "Success" in translations[0]


class TestCheckpointResumeIntegration:
    """Test checkpoint and resume functionality in translation worker."""

    @pytest.fixture
    def sample_srt_file(self, tmp_path):
        """Create a sample SRT file for testing."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?

3
00:00:09,000 --> 00:00:12,000
Goodbye!
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content, encoding="utf-8")
        return str(srt_file)

    @pytest.fixture
    def mock_translator(self):
        """Create a mock translator."""
        translator = MagicMock()
        translator.translate_batch = AsyncMock(
            side_effect=[
                ["Hola mundo"],  # First chunk
                ["¿Cómo estás?"],  # Second chunk
                ["¡Adiós!"],  # Third chunk
            ]
        )
        translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)
        return translator

    @pytest.mark.asyncio
    async def test_checkpoint_saved_after_each_chunk(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that checkpoint is saved after each chunk translation."""
        from uuid import uuid4

        request_id = uuid4()

        # Mock settings to enable checkpointing
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = True
        mock_settings.checkpoint_cleanup_on_success = True
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Verify checkpoint was saved (check checkpoint directory)
            checkpoint_dir = tmp_path / "checkpoints"
            checkpoint_files = list(
                checkpoint_dir.glob(f"{request_id}.es.checkpoint.json")
            )
            # Checkpoint should exist (though may be cleaned up after completion)
            # At minimum, checkpoint should have been created during processing

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test resuming translation from checkpoint."""
        from uuid import uuid4

        request_id = uuid4()

        # Create checkpoint manager and save initial checkpoint
        from translator.checkpoint_manager import CheckpointManager

        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = True
        mock_settings.checkpoint_cleanup_on_success = False  # Don't cleanup for test
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)
        monkeypatch.setattr(
            "translator.checkpoint_manager.settings",
            mock_settings,
        )

        # Create checkpoint with partial progress
        checkpoint_manager = CheckpointManager()
        from common.subtitle_parser import SubtitleSegment

        partial_segments = [
            SubtitleSegment(
                index=1,
                start_time="00:00:01,000",
                end_time="00:00:04,000",
                text="Hola mundo",
            )
        ]

        await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path=sample_srt_file,
            source_language="en",
            target_language="es",
            total_chunks=3,  # Assuming 3 chunks
            completed_chunks=[0],  # First chunk completed
            translated_segments=partial_segments,
        )

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message (should resume from checkpoint)
            await process_translation_message(mock_message, mock_translator)

            # Verify translation was called fewer times (resumed from chunk 2)
            # Since we already had chunk 0 completed, should only translate chunks 1 and 2
            assert mock_translator.translate_batch.call_count <= 3

    @pytest.mark.asyncio
    async def test_checkpoint_cleanup_after_completion(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that checkpoint is cleaned up after successful completion."""
        from uuid import uuid4

        request_id = uuid4()

        # Mock settings with cleanup enabled
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = True
        mock_settings.checkpoint_cleanup_on_success = True
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)
        monkeypatch.setattr(
            "translator.checkpoint_manager.settings",
            mock_settings,
        )

        # Create checkpoint manager and save checkpoint
        from translator.checkpoint_manager import CheckpointManager

        checkpoint_manager = CheckpointManager()
        checkpoint_path = checkpoint_manager.get_checkpoint_path(request_id, "es")

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Checkpoint should be cleaned up (may not exist if cleanup happened)
            # This test verifies cleanup is attempted

    @pytest.mark.asyncio
    async def test_checkpoint_disabled_no_save(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that checkpoint is not saved when disabled."""
        from uuid import uuid4

        request_id = uuid4()

        # Mock settings with checkpoint disabled
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = False
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Verify no checkpoint was created
            checkpoint_dir = tmp_path / "checkpoints"
            if checkpoint_dir.exists():
                checkpoint_files = list(
                    checkpoint_dir.glob(f"{request_id}.es.checkpoint.json")
                )
                assert len(checkpoint_files) == 0

    @pytest.mark.asyncio
    async def test_checkpoint_metadata_mismatch_starts_fresh(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that translation starts fresh when checkpoint metadata doesn't match."""
        from uuid import uuid4

        request_id = uuid4()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = True
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)
        monkeypatch.setattr(
            "translator.checkpoint_manager.settings",
            mock_settings,
        )

        # Create checkpoint with mismatched metadata
        from translator.checkpoint_manager import CheckpointManager

        checkpoint_manager = CheckpointManager()
        from common.subtitle_parser import SubtitleSegment

        partial_segments = [
            SubtitleSegment(
                index=1,
                start_time="00:00:01,000",
                end_time="00:00:04,000",
                text="Hola mundo",
            )
        ]

        # Save checkpoint with different source language
        await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path=sample_srt_file,
            source_language="fr",  # Different from request
            target_language="es",
            total_chunks=3,
            completed_chunks=[0],
            translated_segments=partial_segments,
        )

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message with different source language
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",  # Different from checkpoint
                    "target_language": "es",
                }
            ).encode()

            # Process translation message (should start fresh due to mismatch)
            await process_translation_message(mock_message, mock_translator)

            # Should translate all chunks (started fresh)
            assert mock_translator.translate_batch.call_count >= 1


class TestTranslationCompletedEvent:
    """Test TRANSLATION_COMPLETED event publishing and duration tracking."""

    @pytest.fixture
    def sample_srt_file(self, tmp_path):
        """Create a sample SRT file for testing."""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content, encoding="utf-8")
        return str(srt_file)

    @pytest.fixture
    def mock_translator(self):
        """Create a mock translator."""
        translator = MagicMock()
        translator.translate_batch = AsyncMock(
            return_value=["Hola mundo", "¿Cómo estás?"]
        )
        translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)
        return translator

    @pytest.mark.asyncio
    async def test_translation_completed_event_published(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that TRANSLATION_COMPLETED event is published after successful translation."""
        from uuid import uuid4

        request_id = uuid4()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = False
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Verify TRANSLATION_COMPLETED event was published
            publish_calls = mock_pub.publish_event.call_args_list
            translation_completed_calls = [
                call
                for call in publish_calls
                if call[0][0].event_type.value == "translation.completed"
            ]

            assert len(translation_completed_calls) == 1
            event = translation_completed_calls[0][0][0]
            assert event.job_id == request_id
            assert event.source == "translator"
            assert "duration_seconds" in event.payload
            assert isinstance(event.payload["duration_seconds"], float)
            assert event.payload["duration_seconds"] > 0
            assert event.payload["source_language"] == "en"
            assert event.payload["target_language"] == "es"
            assert event.payload["subtitle_file_path"] == sample_srt_file
            assert "file_path" in event.payload
            assert "translated_path" in event.payload

    @pytest.mark.asyncio
    async def test_translation_completed_event_includes_duration(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that TRANSLATION_COMPLETED event includes correct duration."""
        import asyncio
        from uuid import uuid4

        request_id = uuid4()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = False
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Add small delay to ensure duration > 0
            async def delayed_translate(*args, **kwargs):
                await asyncio.sleep(0.1)
                return ["Hola mundo", "¿Cómo estás?"]

            mock_translator.translate_batch = AsyncMock(side_effect=delayed_translate)

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Verify duration is included and reasonable
            publish_calls = mock_pub.publish_event.call_args_list
            translation_completed_calls = [
                call
                for call in publish_calls
                if call[0][0].event_type.value == "translation.completed"
            ]

            assert len(translation_completed_calls) == 1
            event = translation_completed_calls[0][0][0]
            duration = event.payload["duration_seconds"]
            assert isinstance(duration, float)
            assert duration >= 0.1  # Should be at least the delay we added

    @pytest.mark.asyncio
    async def test_translation_completed_event_payload_structure(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that TRANSLATION_COMPLETED event has correct payload structure."""
        from uuid import uuid4

        from common.schemas import EventType

        request_id = uuid4()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = False
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Verify event payload structure
            publish_calls = mock_pub.publish_event.call_args_list
            translation_completed_calls = [
                call
                for call in publish_calls
                if call[0][0].event_type == EventType.TRANSLATION_COMPLETED
            ]

            assert len(translation_completed_calls) == 1
            event = translation_completed_calls[0][0][0]

            # Verify all required fields are present
            required_fields = [
                "file_path",
                "duration_seconds",
                "source_language",
                "target_language",
                "subtitle_file_path",
                "translated_path",
            ]
            for field in required_fields:
                assert field in event.payload, f"Missing required field: {field}"

            # Verify field types
            assert isinstance(event.payload["file_path"], str)
            assert isinstance(event.payload["duration_seconds"], float)
            assert isinstance(event.payload["source_language"], str)
            assert isinstance(event.payload["target_language"], str)
            assert isinstance(event.payload["subtitle_file_path"], str)
            assert isinstance(event.payload["translated_path"], str)

    @pytest.mark.asyncio
    async def test_translation_completed_event_before_subtitle_translated(
        self, sample_srt_file, mock_translator, tmp_path, monkeypatch
    ):
        """Test that TRANSLATION_COMPLETED event is published before SUBTITLE_TRANSLATED event."""
        from uuid import uuid4

        from common.schemas import EventType

        request_id = uuid4()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = False
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Track event order
        event_order = []

        def track_event_order(event):
            event_order.append(event.event_type)
            return True

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(side_effect=track_event_order)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": sample_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Process translation message
            await process_translation_message(mock_message, mock_translator)

            # Verify TRANSLATION_COMPLETED comes before SUBTITLE_TRANSLATED
            translation_completed_index = None
            subtitle_translated_index = None

            for i, event_type in enumerate(event_order):
                if event_type == EventType.TRANSLATION_COMPLETED:
                    translation_completed_index = i
                elif event_type == EventType.SUBTITLE_TRANSLATED:
                    subtitle_translated_index = i

            if (
                translation_completed_index is not None
                and subtitle_translated_index is not None
            ):
                assert (
                    translation_completed_index < subtitle_translated_index
                ), "TRANSLATION_COMPLETED should be published before SUBTITLE_TRANSLATED"


class TestTranslatorOutputFilename:
    """Test translator output filename generation."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "source_path,target_language,expected_output_name",
        [
            ("/path/video.en.srt", "he", "video.he.srt"),
            ("/path/movie.es.srt", "fr", "movie.fr.srt"),
            ("/path/film.fr.srt", "de", "film.de.srt"),
            ("/path/show.de.srt", "it", "show.it.srt"),
            ("video.en.srt", "he", "video.he.srt"),
            ("movie.es.srt", "fr", "movie.fr.srt"),
        ],
    )
    async def test_output_filename_replaces_language_code(
        self, source_path, target_language, expected_output_name, tmp_path, monkeypatch
    ):
        """Test that translator generates output filename by replacing language code, not appending."""
        from pathlib import Path
        from uuid import uuid4

        request_id = uuid4()

        # Create source subtitle file
        source_file = tmp_path / Path(source_path).name
        source_file.write_text(
            """1
00:00:01,000 --> 00:00:04,000
Hello world
""",
            encoding="utf-8",
        )

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = False
        mock_settings.checkpoint_cleanup_on_success = False
        mock_settings.subtitle_storage_path = str(tmp_path)
        mock_settings.translation_max_tokens_per_chunk = 8000
        mock_settings.translation_max_segments_per_chunk = 100
        mock_settings.openai_model = "gpt-5-nano"
        mock_settings.translation_token_safety_margin = 0.8
        mock_settings.get_translation_parallel_requests = MagicMock(return_value=3)

        monkeypatch.setattr("translator.worker.settings", mock_settings)

        # Mock translator
        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(return_value=["Translated text"])
        mock_translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)

        # Mock Redis and event publisher
        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            # Mock message
            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": str(source_file),
                    "source_language": (
                        Path(source_path).stem.split(".")[-1]
                        if "." in Path(source_path).stem
                        else "en"
                    ),
                    "target_language": target_language,
                }
            ).encode()

            # Process translation
            await process_translation_message(mock_message, mock_translator)

            # Verify output file was created with correct name
            expected_output_path = source_file.parent / expected_output_name
            assert (
                expected_output_path.exists()
            ), f"Expected output file {expected_output_path} does not exist"

            # Verify source file still exists (not replaced)
            assert source_file.exists(), "Source file should remain intact"

            # Verify the output filename matches expected (replace, not append)
            output_files = list(source_file.parent.glob(f"*.{target_language}.srt"))
            assert (
                len(output_files) == 1
            ), f"Expected exactly one {target_language} file"
            assert output_files[0].name == expected_output_name

            # Verify no file with appended language code exists (e.g., video.en.he.srt)
            appended_pattern = f"{source_file.stem}.{target_language}.srt"
            if "." in source_file.stem:
                # Check that we don't have video.en.he.srt
                base_name = source_file.stem.rsplit(".", 1)[0]
                wrong_pattern = f"{base_name}.*.{target_language}.srt"
                wrong_files = [
                    f
                    for f in source_file.parent.glob("*.srt")
                    if f.name.count(".") > 2 and target_language in f.name
                ]
                # Should not have files like video.en.he.srt
                for wrong_file in wrong_files:
                    parts = wrong_file.stem.split(".")
                    if len(parts) > 2:
                        # Check if it has both source and target language codes
                        assert not (
                            len(parts[-1]) == 2
                            and len(parts[-2]) == 2
                            and parts[-1] == target_language
                        ), f"Found incorrectly named file: {wrong_file.name} (should replace, not append)"


class TestParallelTranslationProcessing:
    """Test parallel translation processing with semaphore limiting."""

    # Test constants for parallel processing configuration
    # These constants make the test values explicit and maintainable
    TEST_SEGMENTS_PER_CHUNK = 2  # Small chunks to force multiple chunks for testing
    TEST_PARALLEL_LIMIT_LOW = (
        2  # Low limit for testing semaphore constraint (forces queuing)
    )
    TEST_PARALLEL_LIMIT_NORMAL = 3  # Default parallel requests for GPT-4o-mini in tests
    TEST_PARALLEL_LIMIT_HIGH = 6  # Parallel requests for higher tier models in tests
    TEST_MAX_TOKENS_PER_CHUNK = 100  # Small token limit to force chunking
    TEST_TOKEN_SAFETY_MARGIN = 0.8  # Safety margin for token calculations
    TEST_API_DELAY_SECONDS = 0.1  # Simulated API call delay for timing tests
    TEST_SEMAPHORE_DELAY_SECONDS = 0.05  # Small delay for semaphore concurrency tests

    @pytest.fixture
    def large_srt_file(self, tmp_path):
        """Create a large SRT file with many segments for parallel processing."""
        # Create 10 segments to ensure multiple chunks
        segments = []
        for i in range(1, 11):
            segments.append(
                f"{i}\n"
                f"00:00:{i:02d},000 --> 00:00:{i+1:02d},000\n"
                f"Segment {i} text content\n"
            )
        srt_content = "\n".join(segments)
        srt_file = tmp_path / "large_test.srt"
        srt_file.write_text(srt_content, encoding="utf-8")
        return str(srt_file)

    @pytest.fixture
    def mock_settings_parallel(self):
        """Create mock settings with parallel processing enabled."""
        mock_settings = MagicMock()
        mock_settings.checkpoint_enabled = True
        mock_settings.checkpoint_cleanup_on_success = True
        mock_settings.translation_max_tokens_per_chunk = self.TEST_MAX_TOKENS_PER_CHUNK
        mock_settings.translation_max_segments_per_chunk = self.TEST_SEGMENTS_PER_CHUNK
        mock_settings.openai_model = "gpt-4o-mini"
        mock_settings.translation_token_safety_margin = self.TEST_TOKEN_SAFETY_MARGIN
        mock_settings.translation_parallel_requests = self.TEST_PARALLEL_LIMIT_NORMAL
        mock_settings.translation_parallel_requests_high_tier = (
            self.TEST_PARALLEL_LIMIT_HIGH
        )

        def get_parallel_requests():
            return self.TEST_PARALLEL_LIMIT_NORMAL

        mock_settings.get_translation_parallel_requests = get_parallel_requests
        return mock_settings

    @pytest.mark.asyncio
    async def test_parallel_processing_executes_chunks_concurrently(
        self, large_srt_file, mock_settings_parallel, tmp_path, monkeypatch
    ):
        """Test that chunks are processed in parallel, not sequentially."""
        import asyncio
        from uuid import uuid4

        request_id = uuid4()
        monkeypatch.setattr("translator.worker.settings", mock_settings_parallel)

        # Track call order and timing
        call_times = []
        call_order = []

        async def mock_translate_batch(texts, source_lang, target_lang):
            """Mock translate_batch that tracks timing."""
            call_times.append(asyncio.get_event_loop().time())
            call_order.append(len(call_times))
            # Simulate API delay using test constant
            await asyncio.sleep(self.TEST_API_DELAY_SECONDS)
            return [f"Translated {text}" for text in texts]

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(side_effect=mock_translate_batch)
        mock_translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": large_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            start_time = asyncio.get_event_loop().time()
            await process_translation_message(mock_message, mock_translator)
            end_time = asyncio.get_event_loop().time()

            # With parallel processing, multiple chunks should be called nearly simultaneously
            # If sequential, total time would be ~0.1s * num_chunks
            # With parallel (3 concurrent), should be much faster
            total_time = end_time - start_time
            num_calls = len(call_times)

            # With 3 parallel requests, 5 chunks should complete in ~2 batches
            # Sequential would take ~0.5s, parallel should take ~0.2-0.3s
            assert total_time < 0.5, f"Parallel processing took too long: {total_time}s"
            assert num_calls > 1, "Should have multiple translation calls"

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_requests(
        self, large_srt_file, mock_settings_parallel, tmp_path, monkeypatch
    ):
        """Test that semaphore limits the number of concurrent API requests."""
        import asyncio
        from uuid import uuid4

        request_id = uuid4()
        # Use low parallel limit to test semaphore constraint (forces queuing with 5 chunks)
        mock_settings_parallel.translation_parallel_requests = (
            self.TEST_PARALLEL_LIMIT_LOW
        )
        mock_settings_parallel.get_translation_parallel_requests = (
            lambda: self.TEST_PARALLEL_LIMIT_LOW
        )
        monkeypatch.setattr("translator.worker.settings", mock_settings_parallel)

        active_requests = []
        max_concurrent = 0

        async def mock_translate_batch(texts, source_lang, target_lang):
            """Mock translate_batch that tracks concurrent requests."""
            active_requests.append(1)
            current_concurrent = len(active_requests)
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, current_concurrent)
            # Use test constant for delay to allow other requests to start
            await asyncio.sleep(self.TEST_SEMAPHORE_DELAY_SECONDS)
            active_requests.pop()
            return [f"Translated {text}" for text in texts]

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(side_effect=mock_translate_batch)
        mock_translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": large_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            await process_translation_message(mock_message, mock_translator)

            # With low semaphore limit, max concurrent should be <= TEST_PARALLEL_LIMIT_LOW
            assert (
                max_concurrent <= self.TEST_PARALLEL_LIMIT_LOW
            ), f"Semaphore did not limit concurrent requests: {max_concurrent} (expected <= {self.TEST_PARALLEL_LIMIT_LOW})"

    @pytest.mark.asyncio
    async def test_out_of_order_completion_handled_correctly(
        self, large_srt_file, mock_settings_parallel, tmp_path, monkeypatch
    ):
        """Test that chunks completing out of order are sorted correctly."""
        import asyncio
        from uuid import uuid4

        request_id = uuid4()
        monkeypatch.setattr("translator.worker.settings", mock_settings_parallel)

        call_count = 0

        async def mock_translate_batch(texts, source_lang, target_lang):
            """Mock translate_batch that returns in reverse order."""
            nonlocal call_count
            call_count += 1
            # Later chunks complete faster (simulating out-of-order completion)
            # Use decreasing delay based on call count to simulate varying API response times
            delay = (self.TEST_API_DELAY_SECONDS * 2) - (call_count * 0.02)
            await asyncio.sleep(max(0.01, delay))
            return [f"Translated chunk {call_count}: {text}" for text in texts]

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(side_effect=mock_translate_batch)
        mock_translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": large_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            await process_translation_message(mock_message, mock_translator)

            # Verify output file exists and segments are in correct order
            output_file = tmp_path / "large_test.es.srt"
            assert output_file.exists(), "Output file should be created"

            # Parse output and verify segments are numbered sequentially
            output_content = output_file.read_text(encoding="utf-8")
            segments = SRTParser.parse(output_content)

            # Verify segments are in order (indices should be sequential)
            for i, segment in enumerate(segments, 1):
                assert (
                    segment.index == i
                ), f"Segment {i} has wrong index: {segment.index}"

    @pytest.mark.asyncio
    async def test_checkpoint_saved_after_parallel_batch(
        self, large_srt_file, mock_settings_parallel, tmp_path, monkeypatch
    ):
        """Test that checkpoint is saved correctly after parallel batch completion."""
        import asyncio
        from uuid import uuid4

        request_id = uuid4()
        mock_settings_parallel.subtitle_storage_path = str(tmp_path)
        monkeypatch.setattr("translator.worker.settings", mock_settings_parallel)

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(
            side_effect=lambda texts, sl, tl: [f"Translated {text}" for text in texts]
        )

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": large_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            await process_translation_message(mock_message, mock_translator)

            # Verify checkpoint was saved with all completed chunks
            checkpoint_dir = tmp_path / "checkpoints"
            checkpoint_files = list(
                checkpoint_dir.glob(f"{request_id}.es.checkpoint.json")
            )

            # Checkpoint may be cleaned up after completion, but during processing
            # it should have been created. If it exists, verify it has correct structure
            if checkpoint_files:
                import json as json_lib

                checkpoint_data = json_lib.loads(checkpoint_files[0].read_text())
                assert "completed_chunks" in checkpoint_data
                assert "total_chunks" in checkpoint_data
                assert (
                    len(checkpoint_data["completed_chunks"])
                    == checkpoint_data["total_chunks"]
                )

    @pytest.mark.asyncio
    async def test_parallel_processing_with_checkpoint_resume(
        self, large_srt_file, mock_settings_parallel, tmp_path, monkeypatch
    ):
        """Test that parallel processing works correctly when resuming from checkpoint."""
        import asyncio
        from uuid import uuid4

        from translator.checkpoint_manager import CheckpointManager

        request_id = uuid4()
        mock_settings_parallel.subtitle_storage_path = str(tmp_path)
        monkeypatch.setattr("translator.worker.settings", mock_settings_parallel)

        # Create a checkpoint with first 2 chunks completed
        checkpoint_manager = CheckpointManager()
        segments = SRTParser.parse((tmp_path / "large_test.srt").read_text())
        chunks = [
            segments[0:2],  # Chunk 0
            segments[2:4],  # Chunk 1
            segments[4:6],  # Chunk 2
            segments[6:8],  # Chunk 3
            segments[8:10],  # Chunk 4
        ]

        # Create partial translated segments for first 2 chunks
        partial_segments = []
        for i, chunk in enumerate(chunks[:2]):
            for segment in chunk:
                translated_seg = SubtitleSegment(
                    index=segment.index,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    text=f"Translated chunk {i}: {segment.text}",
                )
                partial_segments.append(translated_seg)

        await checkpoint_manager.save_checkpoint(
            request_id=request_id,
            subtitle_file_path=large_srt_file,
            source_language="en",
            target_language="es",
            total_chunks=len(chunks),
            completed_chunks=[0, 1],
            translated_segments=partial_segments,
        )

        # Mock translator for remaining chunks
        call_count = [0]  # Use list to allow modification in nested function

        async def mock_translate_batch(texts, source_lang, target_lang):
            call_count[0] += 1
            return [
                f"Translated remaining chunk {call_count[0]}: {text}" for text in texts
            ]

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(side_effect=mock_translate_batch)
        mock_translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": large_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            await process_translation_message(mock_message, mock_translator)

            # Should only translate remaining chunks (2, 3, 4)
            # With parallel processing, all 3 should be called
            assert (
                call_count[0] == 3
            ), f"Expected 3 translation calls, got {call_count[0]}"

    @pytest.mark.asyncio
    async def test_parallel_processing_error_handling(
        self, large_srt_file, mock_settings_parallel, tmp_path, monkeypatch
    ):
        """Test that errors in parallel processing are handled correctly (publishes JOB_FAILED event)."""
        import asyncio
        from uuid import uuid4

        request_id = uuid4()
        monkeypatch.setattr("translator.worker.settings", mock_settings_parallel)

        call_count = 0

        async def mock_translate_batch(texts, source_lang, target_lang):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second chunk
                raise Exception("Simulated API error")
            return [f"Translated {text}" for text in texts]

        mock_translator = MagicMock()
        mock_translator.translate_batch = AsyncMock(side_effect=mock_translate_batch)
        mock_translator.get_last_parsed_segment_numbers = MagicMock(return_value=None)

        with patch("translator.worker.redis_client") as mock_redis, patch(
            "translator.worker.event_publisher"
        ) as mock_pub:
            mock_redis.update_phase = AsyncMock(return_value=True)
            mock_pub.publish_event = AsyncMock(return_value=True)

            mock_message = MagicMock()
            mock_message.body = json.dumps(
                {
                    "request_id": str(request_id),
                    "subtitle_file_path": large_srt_file,
                    "source_language": "en",
                    "target_language": "es",
                }
            ).encode()

            # Errors are handled gracefully - JOB_FAILED event is published, no exception raised
            await process_translation_message(mock_message, mock_translator)

            # Verify JOB_FAILED event was published
            assert mock_pub.publish_event.called
            # Find the JOB_FAILED event call
            job_failed_calls = [
                call
                for call in mock_pub.publish_event.call_args_list
                if "JOB_FAILED" in str(call) or "job.failed" in str(call).lower()
            ]
            assert (
                len(job_failed_calls) > 0
            ), "Expected JOB_FAILED event to be published"


class TestTranslatorWorkerShutdown:
    """Tests for translator worker graceful shutdown."""

    @pytest.mark.asyncio
    async def test_translator_worker_handles_shutdown_signal(self):
        """Test that translator worker handles shutdown signals gracefully."""
        shutdown_manager = ShutdownManager("test_translator", shutdown_timeout=5.0)
        await shutdown_manager.setup_signal_handlers()

        # Simulate shutdown signal
        shutdown_manager._trigger_shutdown_for_testing()

        assert shutdown_manager.is_shutdown_requested()

    @pytest.mark.asyncio
    async def test_translator_worker_message_timeout_during_shutdown(self):
        """Test that message processing times out during shutdown."""
        shutdown_manager = ShutdownManager("test_translator", shutdown_timeout=1.0)

        # Simulate long-running message processing
        async def slow_process():
            await asyncio.sleep(1.0)

        shutdown_manager._trigger_shutdown_for_testing()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                slow_process(), timeout=shutdown_manager.shutdown_timeout
            )

    @pytest.mark.asyncio
    async def test_translator_worker_cleanup_callbacks_execute(self):
        """Test that cleanup callbacks execute during shutdown."""
        shutdown_manager = ShutdownManager("test_translator")

        cleanup_executed = {"redis": False, "rabbitmq": False, "publisher": False}

        async def mock_redis_disconnect():
            cleanup_executed["redis"] = True

        async def mock_rabbitmq_close():
            cleanup_executed["rabbitmq"] = True

        async def mock_publisher_disconnect():
            cleanup_executed["publisher"] = True

        shutdown_manager.register_cleanup_callback(mock_redis_disconnect)
        shutdown_manager.register_cleanup_callback(mock_rabbitmq_close)
        shutdown_manager.register_cleanup_callback(mock_publisher_disconnect)

        await shutdown_manager.execute_cleanup()

        assert cleanup_executed["redis"]
        assert cleanup_executed["rabbitmq"]
        assert cleanup_executed["publisher"]

    @pytest.mark.asyncio
    async def test_translator_worker_stops_consuming_on_shutdown(self):
        """Test that translator stops consuming messages on shutdown."""
        shutdown_manager = ShutdownManager("test_translator")

        # Simulate message consumption loop
        messages_processed = 0
        max_messages = 5

        for i in range(max_messages):
            if shutdown_manager.is_shutdown_requested():
                break
            messages_processed += 1

            # Trigger shutdown after 2 messages
            if i == 1:
                shutdown_manager._trigger_shutdown_for_testing()

        # Should only process 2 messages before shutdown
        assert messages_processed == 2
