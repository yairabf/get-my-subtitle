"""Tests for the translator worker."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from common.schemas import SubtitleStatus
from common.subtitle_parser import SRTParser, SubtitleSegment
from translator.worker import SubtitleTranslator, process_translation_message


class TestSubtitleTranslator:
    """Test SubtitleTranslator functionality."""

    @pytest.fixture
    def translator_with_api_key(self):
        """Create translator with mocked API key."""
        with patch("translator.worker.settings") as mock_settings:
            mock_settings.openai_api_key = "sk-test-key"
            mock_settings.openai_model = "gpt-5-nano"
            mock_settings.openai_temperature = 0.3
            mock_settings.openai_max_tokens = 4096

            with patch("translator.worker.AsyncOpenAI") as mock_client:
                translator = SubtitleTranslator()
                return translator, mock_client

    @pytest.fixture
    def translator_without_api_key(self):
        """Create translator without API key (mock mode)."""
        with patch("translator.worker.settings") as mock_settings:
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
        translations = translator_without_api_key._parse_translation_response(
            response, 2
        )

        assert len(translations) == 2
        assert "Hola" in translations[0]
        assert "Adiós" in translations[1]

    def test_parse_translation_response_mismatched_count(
        self, translator_without_api_key
    ):
        """Test parsing response with wrong number of translations."""
        response = "[1]\nHola\n\n"  # Only 1 translation
        translations = translator_without_api_key._parse_translation_response(
            response, 2
        )

        # Should still return what it found
        assert len(translations) == 1


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
            mock_redis.update_job_status = AsyncMock(return_value=True)

            await process_translation_message(mock_message, mock_translator)

            # Verify Redis was updated
            mock_redis.update_job_status.assert_called_once()
            call_args = mock_redis.update_job_status.call_args
            assert call_args[0][0] == request_id
            assert call_args[0][1] == SubtitleStatus.COMPLETED

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

        with patch("translator.worker.redis_client") as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=True)

            await process_translation_message(mock_message, mock_translator)

            # Should update status to FAILED
            assert mock_redis.update_job_status.called

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

        with patch("translator.worker.redis_client") as mock_redis:
            mock_redis.update_job_status = AsyncMock(return_value=True)

            await process_translation_message(mock_message, mock_translator)

            # Should update status to FAILED with error message
            assert mock_redis.update_job_status.called
            call_args = mock_redis.update_job_status.call_args
            assert call_args[0][1] == SubtitleStatus.FAILED
            assert "error_message" in call_args[1]


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
        from common.subtitle_parser import merge_translations

        segments = [SubtitleSegment(1, "00:00:01,000", "00:00:02,000", "Hello")]
        translations = ["Hola", "Extra"]

        with pytest.raises(ValueError):
            merge_translations(segments, translations)

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
