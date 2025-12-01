"""Tests for string utility functions."""

import pytest

from common.string_utils import truncate_for_logging


class TestTruncateForLogging:
    """Test text truncation for logging."""

    @pytest.mark.parametrize(
        "description,text,max_length,edge_length,should_truncate",
        [
            ("short text unchanged", "Hello", 100, 10, False),
            ("text at max length", "x" * 100, 100, 10, False),
            ("text over max length", "x" * 2000, 1000, 500, True),
            ("empty string", "", 100, 10, False),
            ("exactly max length", "x" * 50, 50, 10, False),
        ],
    )
    def test_truncate_for_logging_various_lengths(
        self, description, text, max_length, edge_length, should_truncate
    ):
        """Test truncation behavior with various text lengths."""
        result = truncate_for_logging(text, max_length, edge_length)

        if should_truncate:
            assert len(result) < len(text)
            assert "..." in result
            # Check that beginning and end are present
            assert result.startswith(text[:edge_length])
            assert result.endswith(text[-edge_length:])
        else:
            assert result == text
            assert "..." not in result

    def test_truncate_preserves_start_and_end(self):
        """Test that truncation preserves specified edge lengths."""
        text = "START" + ("x" * 1000) + "END"
        edge_length = 5

        result = truncate_for_logging(text, max_length=100, edge_length=edge_length)

        assert result.startswith("START")
        assert result.endswith("END")
        assert "..." in result

    def test_truncate_with_custom_edge_length(self):
        """Test truncation with custom edge length."""
        text = "x" * 2000
        edge_length = 100

        result = truncate_for_logging(text, max_length=1000, edge_length=edge_length)

        # Result should contain first 100 chars + ellipsis + last 100 chars
        expected_min_length = edge_length * 2 + len("...\n...")
        assert len(result) >= expected_min_length
        assert len(result) < len(text)

    def test_truncate_default_parameters(self):
        """Test truncation with default parameters."""
        text = "x" * 2000

        result = truncate_for_logging(text)  # Uses defaults: max=1000, edge=500

        assert len(result) < len(text)
        assert "..." in result
        # With edge_length=500, should have ~1000 chars (500 start + 500 end + ellipsis)
        assert len(result) > 1000  # More than 1000 due to ellipsis

    def test_truncate_with_newlines(self):
        """Test that truncation works correctly with newlines in text."""
        text = "Line1\n" + ("x" * 1000) + "\nLastLine"

        result = truncate_for_logging(text, max_length=100, edge_length=10)

        assert "Line1" in result
        assert "LastLine" in result
        assert "..." in result

    def test_truncate_unicode_characters(self):
        """Test truncation with unicode characters."""
        text = "🔥" * 1000

        result = truncate_for_logging(text, max_length=500, edge_length=50)

        assert len(result) < len(text)
        assert "..." in result
        # Verify emoji characters are preserved
        assert "🔥" in result
