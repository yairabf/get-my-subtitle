"""
Production test cases for GPT JSON parsing failures.

These tests capture actual malformed JSON patterns observed in production logs.
"""

import pytest

from common.gpt_utils import GPTJSONParsingError, parse_json_robustly


class TestProductionJSONParsingCases:
    """Test actual production JSON parsing failures."""

    def test_parse_production_case_double_braces_missing_comma(self):
        """Test actual production case with double braces and missing commas."""
        # Real pattern from production logs (line 601 in terminal)
        # {"id":6,"text":"...""}},{"id":7,"text":"..."}
        json_text = (
            '[{"id":1,"text":"test1"},'
            '{"id":2,"text":"test2\\nline2"},'
            '{"id":3,"text":"ש""}},{"id":4,"text":"test4"}]'
        )

        result = parse_json_robustly(json_text)
        assert len(result) == 4
        assert result[0]["id"] == 1
        assert result[3]["id"] == 4

    def test_parse_production_case_middle_truncation(self):
        """Test production case where text is truncated mid-sentence."""
        # Pattern from line 620: text cuts off with "}},{"
        json_text = (
            '[{"id":1,"text":"complete"},'
            '{"id":2,"text":"also complete"}},'
            '{"id":3,"text":"next item"}]'
        )

        result = parse_json_robustly(json_text)
        assert len(result) == 3

    def test_parse_production_case_hebrew_with_double_braces(self):
        """Test Hebrew text with double braces pattern."""
        # Real pattern with Hebrew text
        json_text = (
            '[{"id":1,"text":"אני רוצה"},'
            '{"id":2,"text":"במשחק"}},{"id":3,"text":"רודפים אחרי פושע."}]'
        )

        result = parse_json_robustly(json_text)
        assert len(result) >= 2  # At least first 2 should parse

    def test_parse_production_case_multiple_double_braces(self):
        """Test multiple double braces in sequence."""
        json_text = (
            '[{"id":1,"text":"test1"}},'
            '{"id":2,"text":"test2"}},{"id":3,"text":"test3"}}]'
        )

        result = parse_json_robustly(json_text)
        assert len(result) == 3

    def test_parse_production_truncated_at_end(self):
        """Test JSON truncated at the end (incomplete last object)."""
        # Real pattern from line 836: {"id": 24, "text": "לטובתך.
        json_text = (
            '[{"id":1,"text":"complete"},'
            '{"id":2,"text":"also complete"},'
            '{"id":3,"text":"incomp'
        )

        # Should recover the first 2 complete objects
        result = parse_json_robustly(json_text)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_parse_production_truncated_after_complete_objects(self):
        """Test JSON truncated but with some complete objects."""
        # Pattern from line 836/844: valid objects but truncated at id 24
        json_text = (
            '[{"id":1,"text":"גברות."},'
            '{"id":2,"text":"מריאן!"},'
            '{"id":3,"text":"מה את עושה כאן?"},'
            '{"id":4,"text":"נהנית מהכוכבים."},'
            '{"id":5,"text":"ובכן..."},'
            '{"id":6,"text":"יש בהחלט דברים\\nיותר מעניינים"},'
            '{"id":7,"text":"להנות מהם"},'
            '{"id":8,"text":"באמת?"},'
            '{"id":9,"text":"כמו לשדוד"},'
            '{"id":10,"text":"ולרדוף"},'
            '{"id":11,"text":"תן לי לנחש."},'
            '{"id":12,"text":"אתה מתגעגע"},'
            '{"id":13,"text":"לא כולם"},'
            '{"id":14,"text":"כמו שאתה"},'
            '{"id":15,"text":"ובכן, זה"},'
            '{"id":16,"text":"מה שחשוב"},'
            '{"id":17,"text":"נוטינגהאם"},'
            '{"id":18,"text":"אבל אני"},'
            '{"id":19,"text":"שאתה ואני"},'
            '{"id":20,"text":"לא היינו"},'
            '{"id":21,"text":"ועדיין הלב"},'
            '{"id":22,"text":"אמרתי לך"},'
            '{"id":23,"text":"שיהיה לך"},'
            '{"id":24,"text":"לטובתך.'
        )

        # Should recover the first 23 complete objects
        result = parse_json_robustly(json_text)
        assert len(result) == 23
        assert result[0]["id"] == 1
        assert result[22]["id"] == 23
