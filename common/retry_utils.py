"""Retry utility with exponential backoff for handling transient API errors."""

import asyncio
import functools
import logging
import random
from typing import Any, Callable, Type, TypeVar

logger = logging.getLogger(__name__)

# Type variable for generic function return type
T = TypeVar("T")


def calculate_exponential_backoff_delay(
    initial_delay: float,
    attempt: int,
    exponential_base: int,
    max_delay: float,
) -> float:
    """
    Calculate delay with exponential backoff and jitter.

    Args:
        initial_delay: Initial delay in seconds
        attempt: Current attempt number (0-indexed)
        exponential_base: Base for exponential calculation (e.g., 2)
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter applied
    """
    # Calculate exponential delay: initial_delay * base^attempt
    delay = initial_delay * (exponential_base**attempt)

    # Cap at maximum delay
    delay = min(delay, max_delay)

    # Add jitter (0-50% of delay) to prevent thundering herd
    jitter = random.uniform(0, delay * 0.5)
    final_delay = delay + jitter

    return final_delay


def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient (should retry) or permanent (should not retry).
    
    Checks both the error itself and its __cause__ chain for transient indicators.

    Args:
        error: Exception to check

    Returns:
        True if error is transient and should be retried, False otherwise
    """
    # Import here to avoid circular dependencies
    try:
        from downloader.opensubtitles_client import (
            OpenSubtitlesAPIError,
            OpenSubtitlesAuthenticationError,
            OpenSubtitlesRateLimitError,
        )

        # Permanent errors - should NOT retry
        # Authentication errors with "401" or "Unauthorized" in message are permanent
        if isinstance(error, OpenSubtitlesAuthenticationError):
            error_msg = str(error).lower()
            # Check if it's truly an auth error (not a wrapped network error)
            if "401" in error_msg or "unauthorized" in error_msg or "invalid credentials" in error_msg:
                return False
            # If it's wrapping a transient error, check the cause
            if error.__cause__:
                return is_transient_error(error.__cause__)
            return False

        # Transient errors - should retry
        if isinstance(error, OpenSubtitlesRateLimitError):
            return True

        # Generic API errors - check message and cause
        if isinstance(error, OpenSubtitlesAPIError):
            error_msg = str(error).lower()
            # Transient HTTP status codes
            transient_indicators = ["503", "502", "504", "500", "timeout", "unavailable"]
            if any(indicator in error_msg for indicator in transient_indicators):
                return True
            
            # Check if wrapping a transient error
            if error.__cause__:
                return is_transient_error(error.__cause__)
            
            # Default: treat as permanent
            return False

    except ImportError:
        pass

    # Network-related errors - transient
    if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True

    # OSError subtypes that are transient
    if isinstance(error, OSError):
        # Connection refused, network unreachable, etc.
        return True

    # Default: treat unknown errors as permanent to avoid infinite retries
    return False


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: int = 2,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that adds retry logic with exponential backoff to async functions.

    Only retries on transient errors (connection issues, rate limits, etc.).
    Permanent errors (authentication failures, invalid requests) fail immediately.

    Args:
        max_retries: Maximum number of retry attempts (after initial try)
        initial_delay: Initial delay in seconds before first retry
        exponential_base: Base for exponential backoff calculation
        max_delay: Maximum delay in seconds between retries

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_exponential_backoff(max_retries=3, initial_delay=1)
        async def fetch_data():
            return await api_call()
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            # Initial attempt + retries
            for attempt in range(max_retries + 1):
                try:
                    # Execute the function
                    result = await func(*args, **kwargs)
                    return result

                except Exception as e:
                    last_exception = e

                    # Check if error is transient
                    if not is_transient_error(e):
                        # Permanent error - fail immediately
                        logger.error(
                            f"❌ Permanent error in {func.__name__}: {e}. Not retrying."
                        )
                        raise

                    # Check if we have retries left
                    if attempt >= max_retries:
                        # Exhausted retries
                        logger.error(
                            f"❌ Max retries ({max_retries}) exceeded for {func.__name__}. Last error: {e}"
                        )
                        raise

                    # Calculate backoff delay
                    delay = calculate_exponential_backoff_delay(
                        initial_delay=initial_delay,
                        attempt=attempt,
                        exponential_base=exponential_base,
                        max_delay=max_delay,
                    )

                    # Log retry attempt
                    logger.warning(
                        f"⚠️  Transient error in {func.__name__}: {e}. "
                        f"Retry {attempt + 1}/{max_retries} in {delay:.2f}s..."
                    )

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # Should not reach here, but raise last exception if we do
            if last_exception:
                raise last_exception

        return wrapper

    return decorator

