"""Tests for SRT subtitle parser."""

import pytest

from common.subtitle_parser import (
    DEFAULT_MAX_SEGMENTS_PER_CHUNK,
    SRTParser,
    SubtitleSegment,
    chunk_segments,
    extract_text_for_translation,
    merge_translations,
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


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling for subtitle parser."""

    def test_extract_text_none_input(self):
        """Test that extract_text_for_translation raises ValueError for None input."""
        with pytest.raises(ValueError, match="cannot be None"):
            extract_text_for_translation(None)

    def test_merge_translations_none_segments(self):
        """Test that merge_translations raises ValueError for None segments."""
        translations = ["Hola", "Mundo"]
        with pytest.raises(ValueError, match="cannot be None"):
            merge_translations(None, translations)

    def test_merge_translations_none_translations(self):
        """Test that merge_translations raises ValueError for None translations."""
        segments = [
            SubtitleSegment(1, "00:00:01,000", "00:00:04,000", "Hello"),
            SubtitleSegment(2, "00:00:04,500", "00:00:08,000", "World"),
        ]
        with pytest.raises(ValueError, match="cannot be None"):
            merge_translations(segments, None)

    def test_chunk_segments_none_input(self):
        """Test that chunk_segments raises ValueError for None input."""
        with pytest.raises(ValueError, match="cannot be None"):
            chunk_segments(None)

    @pytest.mark.parametrize("max_segments", [0, -1, -100])
    def test_chunk_segments_invalid_max_segments(self, max_segments):
        """Test that chunk_segments raises ValueError for invalid max_segments."""
        segments = [
            SubtitleSegment(1, "00:00:00,000", "00:00:01,000", "Test")
        ]
        with pytest.raises(ValueError, match="must be at least 1"):
            chunk_segments(segments, max_segments=max_segments)

    def test_parse_srt_missing_index_numbers(self):
        """Test parsing SRT with missing or non-numeric index numbers."""
        content = """not_a_number
00:00:01,000 --> 00:00:04,000
This should be skipped

2
00:00:04,500 --> 00:00:08,000
This should work
"""
        segments = SRTParser.parse(content)
        # Should skip malformed segment and parse valid one
        assert len(segments) == 1
        assert segments[0].index == 2
        assert segments[0].text == "This should work"

    def test_parse_srt_timestamps_without_text(self):
        """Test parsing SRT with valid timestamps but no text following."""
        content = """1
00:00:01,000 --> 00:00:04,000

2
00:00:04,500 --> 00:00:08,000
Valid text here
"""
        segments = SRTParser.parse(content)
        # Should skip empty text segment
        assert len(segments) == 1
        assert segments[0].index == 2

    def test_parse_srt_mixed_line_endings(self):
        """Test parsing SRT with mixed Windows (CRLF) and Unix (LF) line endings."""
        # Simulate mixed line endings
        content = "1\r\n00:00:01,000 --> 00:00:04,000\r\nWindows line ending\n\n2\n00:00:04,500 --> 00:00:08,000\nUnix line ending\n"
        segments = SRTParser.parse(content)
        # Should handle both line ending types
        assert len(segments) == 2
        assert segments[0].text == "Windows line ending"
        assert segments[1].text == "Unix line ending"

    def test_parse_srt_unicode_and_special_characters(self):
        """Test parsing SRT with unicode characters, emojis, and special symbols."""
        content = """1
00:00:01,000 --> 00:00:04,000
Hello 世界 🌍

2
00:00:04,500 --> 00:00:08,000
Café ñoño © ® € £ ¥

3
00:00:08,500 --> 00:00:12,000
Emoji test: 😀 🎉 ❤️ 🚀
"""
        segments = SRTParser.parse(content)
        assert len(segments) == 3
        assert "世界" in segments[0].text
        assert "🌍" in segments[0].text
        assert "ñoño" in segments[1].text
        assert "€" in segments[1].text
        assert "😀" in segments[2].text
        assert "🚀" in segments[2].text

    def test_parse_large_subtitle_file(self):
        """Test parsing a large SRT file with 1000+ segments for performance."""
        # Generate a large SRT file
        segments_count = 1000
        content_parts = []
        for i in range(1, segments_count + 1):
            minutes = i // 60
            seconds = i % 60
            content_parts.append(
                f"{i}\n"
                f"00:{minutes:02d}:{seconds:02d},000 --> 00:{minutes:02d}:{seconds:02d},500\n"
                f"Subtitle text for segment {i}\n"
            )
        content = "\n".join(content_parts)

        # Parse and verify
        segments = SRTParser.parse(content)
        assert len(segments) == segments_count
        assert segments[0].index == 1
        assert segments[-1].index == segments_count
        assert "segment 1" in segments[0].text
        assert f"segment {segments_count}" in segments[-1].text
