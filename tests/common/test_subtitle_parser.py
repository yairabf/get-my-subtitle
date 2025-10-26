"""Tests for SRT subtitle parser."""

import pytest
from common.subtitle_parser import (
    SubtitleSegment,
    SRTParser,
    extract_text_for_translation,
    merge_translations,
    chunk_segments,
    DEFAULT_MAX_SEGMENTS_PER_CHUNK,
)


class TestSubtitleSegment:
    """Test SubtitleSegment dataclass."""

    def test_subtitle_segment_str(self):
        """Test string representation of subtitle segment."""
        segment = SubtitleSegment(
            index=1,
            start_time="00:00:01,000",
            end_time="00:00:04,000",
            text="Hello, world!",
        )

        result = str(segment)
        expected = "1\n00:00:01,000 --> 00:00:04,000\nHello, world!\n"

        assert result == expected


class TestSRTParser:
    """Test SRT parser functionality."""

    @pytest.fixture
    def simple_srt_content(self):
        """Provide simple SRT content for testing."""
        return """1
00:00:01,000 --> 00:00:04,000
Welcome to this video

2
00:00:04,500 --> 00:00:08,000
Today we're going to learn something new

3
00:00:08,500 --> 00:00:12,000
Let's get started!
"""

    @pytest.fixture
    def multiline_srt_content(self):
        """Provide SRT content with multiline subtitles."""
        return """1
00:00:01,000 --> 00:00:04,000
This is a subtitle
with multiple lines

2
00:00:04,500 --> 00:00:08,000
Another one
also with
multiple lines
"""

    def test_parse_simple_srt(self, simple_srt_content):
        """Test parsing simple SRT content."""
        segments = SRTParser.parse(simple_srt_content)

        assert len(segments) == 3
        assert segments[0].index == 1
        assert segments[0].start_time == "00:00:01,000"
        assert segments[0].end_time == "00:00:04,000"
        assert segments[0].text == "Welcome to this video"

    def test_parse_multiline_srt(self, multiline_srt_content):
        """Test parsing SRT content with multiline subtitles."""
        segments = SRTParser.parse(multiline_srt_content)

        assert len(segments) == 2
        assert "multiple lines" in segments[0].text
        assert "\n" in segments[0].text

    @pytest.mark.parametrize(
        "content,expected_count",
        [
            ("", 0),  # Empty content
            ("\n\n\n", 0),  # Only newlines
            ("1\n00:00:01,000 --> 00:00:04,000\nText\n", 1),  # Single segment
        ],
    )
    def test_parse_edge_cases(self, content, expected_count):
        """Test parsing edge cases."""
        segments = SRTParser.parse(content)
        assert len(segments) == expected_count

    def test_parse_invalid_timestamp(self):
        """Test parsing with invalid timestamp format."""
        content = """1
invalid timestamp
Some text
"""
        segments = SRTParser.parse(content)
        assert len(segments) == 0  # Should skip invalid entries

    def test_format_segments(self, simple_srt_content):
        """Test formatting segments back to SRT."""
        segments = SRTParser.parse(simple_srt_content)
        formatted = SRTParser.format(segments)

        assert isinstance(formatted, str)
        assert "00:00:01,000 --> 00:00:04,000" in formatted
        assert "Welcome to this video" in formatted


class TestTextExtractionAndMerging:
    """Test text extraction and translation merging."""

    @pytest.fixture
    def sample_segments(self):
        """Provide sample subtitle segments."""
        return [
            SubtitleSegment(1, "00:00:01,000", "00:00:04,000", "Hello"),
            SubtitleSegment(2, "00:00:04,500", "00:00:08,000", "World"),
            SubtitleSegment(3, "00:00:08,500", "00:00:12,000", "Test"),
        ]

    def test_extract_text_for_translation(self, sample_segments):
        """Test extracting text from segments."""
        texts = extract_text_for_translation(sample_segments)

        assert len(texts) == 3
        assert texts[0] == "Hello"
        assert texts[1] == "World"
        assert texts[2] == "Test"

    def test_merge_translations(self, sample_segments):
        """Test merging translations back into segments."""
        translations = ["Hola", "Mundo", "Prueba"]

        translated_segments = merge_translations(sample_segments, translations)

        assert len(translated_segments) == 3
        assert translated_segments[0].text == "Hola"
        assert translated_segments[1].text == "Mundo"
        assert translated_segments[2].text == "Prueba"
        # Original timing should be preserved
        assert translated_segments[0].start_time == "00:00:01,000"
        assert translated_segments[0].index == 1

    def test_merge_translations_mismatched_count(self, sample_segments):
        """Test merging with mismatched segment and translation counts."""
        translations = ["Hola", "Mundo"]  # Only 2 translations for 3 segments

        with pytest.raises(ValueError, match="doesn't match"):
            merge_translations(sample_segments, translations)

    def test_merge_translations_strips_whitespace(self, sample_segments):
        """Test that merge strips whitespace from translations."""
        translations = ["  Hola  ", "\nMundo\n", "\t\tPrueba\t\t"]

        translated_segments = merge_translations(sample_segments, translations)

        assert translated_segments[0].text == "Hola"
        assert translated_segments[1].text == "Mundo"
        assert translated_segments[2].text == "Prueba"


class TestChunkSegments:
    """Test segment chunking functionality."""

    @pytest.fixture
    def many_segments(self):
        """Provide many subtitle segments for chunking."""
        return [
            SubtitleSegment(i, "00:00:00,000", "00:00:01,000", f"Text {i}")
            for i in range(1, 101)  # 100 segments
        ]

    @pytest.mark.parametrize(
        "total_segments,max_segments,expected_chunks",
        [
            (10, 5, 2),
            (50, 50, 1),
            (51, 50, 2),
            (100, 25, 4),
            (75, 20, 4),
            (1, 50, 1),
            (0, 50, 0),
        ],
    )
    def test_chunk_segments_various_sizes(
        self, total_segments, max_segments, expected_chunks
    ):
        """Test chunking with various segment counts and chunk sizes."""
        segments = [
            SubtitleSegment(i, "00:00:00,000", "00:00:01,000", f"Text {i}")
            for i in range(1, total_segments + 1)
        ]

        chunks = chunk_segments(segments, max_segments=max_segments)

        assert len(chunks) == expected_chunks

        # Verify all segments are included
        total_in_chunks = sum(len(chunk) for chunk in chunks)
        assert total_in_chunks == total_segments

    def test_chunk_segments_default_size(self, many_segments):
        """Test chunking with default max segments."""
        chunks = chunk_segments(many_segments)

        # With 100 segments and default 50 max, should have 2 chunks
        assert len(chunks) == 2
        assert len(chunks[0]) == DEFAULT_MAX_SEGMENTS_PER_CHUNK
        assert len(chunks[1]) == DEFAULT_MAX_SEGMENTS_PER_CHUNK

    def test_chunk_segments_preserves_order(self):
        """Test that chunking preserves segment order."""
        segments = [
            SubtitleSegment(i, "00:00:00,000", "00:00:01,000", f"Text {i}")
            for i in range(1, 11)
        ]

        chunks = chunk_segments(segments, max_segments=3)

        # Verify order is preserved
        reconstructed = []
        for chunk in chunks:
            reconstructed.extend(chunk)

        for i, segment in enumerate(reconstructed):
            assert segment.index == i + 1

    def test_chunk_segments_empty_list(self):
        """Test chunking with empty segment list."""
        chunks = chunk_segments([])
        assert len(chunks) == 0
