"""Token counter utility for estimating and counting tokens in text.

This module provides accurate token counting using tiktoken for OpenAI models,
with a fallback to simple estimation when tiktoken is unavailable.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using simple heuristic.

    Uses the rule of thumb: ~4 characters per token for English text.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0

    # Simple estimation: ~4 characters per token
    return max(1, len(text) // 4)


class TokenCounter:
    """Token counter with tiktoken integration and estimation fallback."""

    def __init__(self):
        """Initialize token counter and attempt to load tiktoken."""
        self.tiktoken_available = False
        self.tiktoken = None
        self._encoding_cache: Dict[str, any] = {}

        try:
            import tiktoken

            self.tiktoken = tiktoken
            self.tiktoken_available = True
            logger.info("tiktoken loaded successfully - using accurate token counting")
        except ImportError:
            logger.warning(
                "tiktoken not available - falling back to estimation "
                "(~4 chars per token)"
            )

    def count_tokens(self, text: str, model: str) -> int:
        """
        Count tokens in text for specified model.

        Uses tiktoken for accurate counting when available, falls back to
        estimation otherwise.

        Args:
            text: Text to count tokens for
            model: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')

        Returns:
            Number of tokens in text
        """
        if not text:
            return 0

        if not self.tiktoken_available:
            return estimate_tokens(text)

        try:
            # Get or create encoding for model
            encoding = self._get_encoding(model)
            tokens = encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(
                f"Error counting tokens with tiktoken for model {model}: {e}. "
                f"Falling back to estimation."
            )
            return estimate_tokens(text)

    def _get_encoding(self, model: str):
        """
        Get encoding for model, using cache when possible.

        Args:
            model: Model name

        Returns:
            Encoding instance

        Raises:
            Exception: If encoding cannot be loaded
        """
        if model not in self._encoding_cache:
            self._encoding_cache[model] = self.tiktoken.encoding_for_model(model)
            logger.debug(f"Loaded and cached encoding for model: {model}")

        return self._encoding_cache[model]


# Singleton instance for convenience
_token_counter_instance: Optional[TokenCounter] = None


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text for specified model.

    Convenience function that uses a singleton TokenCounter instance.

    Args:
        text: Text to count tokens for
        model: Model name (default: 'gpt-4')

    Returns:
        Number of tokens in text
    """
    global _token_counter_instance

    if _token_counter_instance is None:
        _token_counter_instance = TokenCounter()

    return _token_counter_instance.count_tokens(text, model)
