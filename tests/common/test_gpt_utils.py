"""Tests for GPT utility functions."""

import pytest

from common.gpt_utils import (
    GPTJSONParsingError,
    clean_markdown_code_fences,
    parse_json_robustly,
)


class TestCleanMarkdownCodeFences:
    """Test markdown code fence cleaning functionality."""

    @pytest.mark.parametrize(
        "description,input_text,expected_output",
        [
            (
                "plain JSON without fences",
                '{"key": "value"}',
                '{"key": "value"}',
            ),
            (
                "JSON with markdown fences",
                '```\n{"key": "value"}\n```',
                '{"key": "value"}',
            ),
            (
                "JSON with json language tag",
                '```json\n{"key": "value"}\n```',
                '{"key": "value"}',
            ),
            (
                "JSON array with fences",
                '```\n[{"id": 1}, {"id": 2}]\n```',
                '[{"id": 1}, {"id": 2}]',
            ),
            (
                "multiline JSON with fences",
                '```json\n{\n  "key": "value",\n  "nested": {\n    "data": 123\n  }\n}\n```',
                '{\n  "key": "value",\n  "nested": {\n    "data": 123\n  }\n}',
            ),
            (
                "JSON with only opening fence",
                '```\n{"key": "value"}',
                '{"key": "value"}',
            ),
            (
                "empty fenced block",
                "```\n```",
                "",
            ),
            (
                "whitespace around fences",
                '  ```json\n{"key": "value"}\n```  ',
                '{"key": "value"}',
            ),
        ],
    )
    def test_clean_markdown_code_fences(self, description, input_text, expected_output):
        """Test cleaning various markdown fence formats."""
        result = clean_markdown_code_fences(input_text)
        assert result == expected_output

    def test_clean_preserves_newlines_in_content(self):
        """Test that newlines within JSON content are preserved."""
        input_text = '```\n{\n  "line1": "value1",\n  "line2": "value2"\n}\n```'
        result = clean_markdown_code_fences(input_text)
        assert "\n" in result
        assert result.count("\n") == 3  # Three newlines in the JSON content

    def test_clean_handles_fence_without_content(self):
        """Test handling of fence with no content between markers."""
        input_text = "```\n\n```"
        result = clean_markdown_code_fences(input_text)
        assert result == ""

    def test_clean_handles_json_tag_without_fence(self):
        """Test that content starting with 'json' is handled correctly."""
        input_text = 'json\n{"key": "value"}'
        result = clean_markdown_code_fences(input_text)
        assert result == '{"key": "value"}'


class TestParseJsonRobustly:
    """Test robust JSON parsing functionality."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON."""
        json_text = '[{"id": 1, "text": "Hello"}, {"id": 2, "text": "World"}]'
        result = parse_json_robustly(json_text)
        assert result == [{"id": 1, "text": "Hello"}, {"id": 2, "text": "World"}]

    def test_parse_json_with_missing_commas(self):
        """Test parsing JSON with missing commas between objects."""
        # Missing comma between objects - common GPT error
        json_text = '[{"id": 1, "text": "Hello"}{"id": 2, "text": "World"}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_parse_json_with_invalid_escape(self):
        """Test parsing JSON with invalid escape sequences."""
        # Invalid escape sequence \x - should be fixed to \\x
        json_text = '[{"id": 1, "text": "Test\\xBB"}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 1
        # The text should have the escape properly handled
        assert result[0]["id"] == 1

    def test_parse_json_with_valid_escapes_preserved(self):
        """Test that valid JSON escapes are preserved."""
        json_text = '[{"id": 1, "text": "Line1\\nLine2\\tTabbed"}]'
        result = parse_json_robustly(json_text)
        assert result[0]["text"] == "Line1\nLine2\tTabbed"

    def test_parse_json_array_extraction(self):
        """Test extracting array from malformed wrapper."""
        # Array wrapped in extra text
        json_text = 'Here is the result: [{"id": 1, "text": "Hello"}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_parse_json_combined_issues(self):
        """Test parsing JSON with multiple issues."""
        # Missing comma + whitespace
        json_text = '[{"id": 1, "text": "Hello"}  {"id": 2, "text": "World"}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 2

    def test_parse_json_completely_invalid(self):
        """Test that completely invalid JSON raises error."""
        json_text = "This is not JSON at all {invalid}"
        with pytest.raises(GPTJSONParsingError, match="Failed to parse JSON"):
            parse_json_robustly(json_text)

    def test_parse_json_empty_array(self):
        """Test parsing empty array."""
        json_text = "[]"
        result = parse_json_robustly(json_text)
        assert result == []

    def test_parse_json_with_unicode(self):
        """Test parsing JSON with unicode characters."""
        json_text = '[{"id": 1, "text": "שלום עולם"}]'  # Hebrew text
        result = parse_json_robustly(json_text)
        assert result[0]["text"] == "שלום עולם"

    def test_parse_json_with_double_closing_braces(self):
        """Test parsing JSON with double closing braces (GPT truncation)."""
        # GPT sometimes adds extra closing braces
        json_text = '[{"id": 1, "text": "test"}},{"id": 2, "text": "test2"}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_parse_json_with_double_braces_at_end(self):
        """Test parsing JSON with double braces at end of array."""
        json_text = '[{"id": 1, "text": "test"}}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_parse_json_with_missing_comma_and_double_braces(self):
        """Test parsing JSON with both missing commas and double braces."""
        # Multiple issues: missing comma AND double braces
        json_text = '[{"id": 1, "text": "test"}} {"id": 2, "text": "test2"}]'
        result = parse_json_robustly(json_text)
        assert len(result) == 2
