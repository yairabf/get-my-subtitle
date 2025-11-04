"""Tests for token counter utility."""

import pytest

from common.token_counter import TokenCounter, count_tokens, estimate_tokens


class TestEstimateTokens:
    """Test simple token estimation fallback."""

    @pytest.mark.parametrize(
        "text,expected_min,expected_max",
        [
            ("", 0, 0),  # Empty text
            ("Hello world", 2, 4),  # Simple text (~2-3 tokens)
            ("A" * 100, 20, 30),  # 100 chars ≈ 25 tokens
            ("Hello, how are you today?", 5, 8),  # Question
            ("This is a longer sentence with more words.", 8, 12),  # Longer text
        ],
    )
    def test_estimate_tokens_range(self, text, expected_min, expected_max):
        """Test token estimation is within expected range."""
        result = estimate_tokens(text)
        assert expected_min <= result <= expected_max

    def test_estimate_tokens_uses_4_chars_per_token_rule(self):
        """Test that estimation uses ~4 characters per token rule."""
        text = "x" * 400  # 400 characters
        result = estimate_tokens(text)
        # Should be around 100 tokens (400 / 4)
        assert 90 <= result <= 110


class TestTokenCounter:
    """Test TokenCounter class."""

    @pytest.fixture
    def counter(self):
        """Provide TokenCounter instance."""
        return TokenCounter()

    def test_count_tokens_with_tiktoken_available(self, counter):
        """Test token counting when tiktoken is available."""
        text = "Hello, how are you?"
        model = "gpt-4"

        try:
            import tiktoken

            # If tiktoken is available, should use it
            result = counter.count_tokens(text, model)
            assert result > 0
            assert isinstance(result, int)

            # Verify it matches direct tiktoken call
            encoding = tiktoken.encoding_for_model(model)
            expected = len(encoding.encode(text))
            assert result == expected
        except ImportError:
            # If tiktoken not available, should fall back to estimation
            result = counter.count_tokens(text, model)
            assert result > 0
            assert isinstance(result, int)

    def test_count_tokens_caches_encoding(self, counter):
        """Test that encodings are cached for performance."""
        text = "Test text"
        model = "gpt-4"

        # First call
        result1 = counter.count_tokens(text, model)

        # Second call should use cached encoding
        result2 = counter.count_tokens(text, model)

        assert result1 == result2
        # Cache should contain the model
        assert model in counter._encoding_cache or not counter.tiktoken_available

    @pytest.mark.parametrize(
        "model",
        [
            "gpt-4",
            "gpt-4o",
            "gpt-3.5-turbo",
            "gpt-4-turbo",
        ],
    )
    def test_count_tokens_supports_common_models(self, counter, model):
        """Test that common OpenAI models are supported."""
        text = "This is a test sentence."
        result = counter.count_tokens(text, model)
        assert result > 0
        assert isinstance(result, int)

    def test_count_tokens_empty_text(self, counter):
        """Test counting tokens for empty text."""
        result = counter.count_tokens("", "gpt-4")
        assert result == 0

    def test_count_tokens_multiline_text(self, counter):
        """Test counting tokens for multiline text."""
        text = """Line 1
Line 2
Line 3"""
        result = counter.count_tokens(text, "gpt-4")
        assert result > 0

    def test_count_tokens_unicode_text(self, counter):
        """Test counting tokens for unicode text."""
        text = "Hello 世界! 🌍"
        result = counter.count_tokens(text, "gpt-4")
        assert result > 0

    def test_count_tokens_unsupported_model_falls_back(self, counter):
        """Test that unsupported models fall back to estimation."""
        text = "Test text"
        model = "unsupported-model-xyz"

        # Should not raise, should fall back to estimation
        result = counter.count_tokens(text, model)
        assert result > 0
        assert isinstance(result, int)


class TestCountTokensFunction:
    """Test the convenience count_tokens function."""

    def test_count_tokens_function(self):
        """Test the module-level count_tokens function."""
        text = "Hello, world!"
        result = count_tokens(text, "gpt-4")
        assert result > 0
        assert isinstance(result, int)

    def test_count_tokens_function_uses_singleton(self):
        """Test that function uses singleton instance."""
        text = "Test"
        result1 = count_tokens(text, "gpt-4")
        result2 = count_tokens(text, "gpt-4")
        assert result1 == result2


class TestTokenCounterIntegration:
    """Integration tests for token counter."""

    def test_count_tokens_for_subtitle_text(self):
        """Test counting tokens for typical subtitle text."""
        subtitle_text = """Welcome to this video
Today we're going to learn something new"""

        result = count_tokens(subtitle_text, "gpt-4")
        assert result > 0
        # Typical subtitle should be reasonable number of tokens
        assert result < 100

    def test_count_tokens_for_batch_of_subtitles(self):
        """Test counting tokens for batch of subtitle segments."""
        subtitles = [
            "Hello, world!",
            "This is subtitle number 2",
            "And this is the third one",
        ]

        total_tokens = sum(count_tokens(text, "gpt-4") for text in subtitles)
        assert total_tokens > 0
        assert isinstance(total_tokens, int)

    def test_count_tokens_for_translation_prompt(self):
        """Test counting tokens for full translation prompt."""
        prompt = """Translate the following 3 subtitle segments from en to es.

Return ONLY the translations, numbered the same way.

[1]
Hello, world!

[2]
This is subtitle number 2

[3]
And this is the third one"""

        result = count_tokens(prompt, "gpt-4")
        assert result > 0
        # Full prompt should be more tokens than individual subtitles
        assert result > 20


class TestTokenCounterEdgeCases:
    """Test edge cases for token counter."""

    @pytest.fixture
    def counter(self):
        """Provide TokenCounter instance."""
        return TokenCounter()

    def test_very_long_text(self, counter):
        """Test counting tokens for very long text."""
        text = "word " * 10000  # Very long text
        result = counter.count_tokens(text, "gpt-4")
        assert result > 0
        # Should be roughly 10000 tokens (one word per token)
        # With estimation fallback, could be slightly higher
        assert 8000 <= result <= 13000

    def test_special_characters(self, counter):
        """Test counting tokens with special characters."""
        text = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        result = counter.count_tokens(text, "gpt-4")
        assert result > 0

    def test_mixed_languages(self, counter):
        """Test counting tokens with mixed languages."""
        text = "Hello 你好 Bonjour Hola こんにちは"
        result = counter.count_tokens(text, "gpt-4")
        assert result > 0

    def test_whitespace_handling(self, counter):
        """Test token counting handles whitespace correctly."""
        text1 = "Hello world"
        text2 = "Hello  world"  # Extra space
        text3 = "Hello\nworld"  # Newline

        result1 = counter.count_tokens(text1, "gpt-4")
        result2 = counter.count_tokens(text2, "gpt-4")
        result3 = counter.count_tokens(text3, "gpt-4")

        # All should be counted
        assert result1 > 0
        assert result2 > 0
        assert result3 > 0

