"""Unit tests for retry utility with exponential backoff."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.retry_utils import (
    calculate_exponential_backoff_delay,
    is_transient_error,
    retry_with_exponential_backoff,
)


class TestCalculateExponentialBackoffDelay:
    """Test cases for exponential backoff delay calculation."""

    def test_calculates_delay_with_exponential_base_2(self):
        """Should calculate delay with exponential base 2."""
        # Arrange
        initial_delay = 1
        attempt = 0
        exponential_base = 2
        max_delay = 60

        # Act
        delay = calculate_exponential_backoff_delay(
            initial_delay=initial_delay,
            attempt=attempt,
            exponential_base=exponential_base,
            max_delay=max_delay,
        )

        # Assert - First attempt: 1 * 2^0 = 1
        assert delay >= 1.0
        assert delay <= 1.5  # With jitter

    def test_calculates_delay_for_multiple_attempts(self):
        """Should calculate increasing delays for multiple attempts."""
        # Arrange
        initial_delay = 1
        exponential_base = 2
        max_delay = 60

        # Act & Assert
        # Attempt 0: 1 * 2^0 = 1 second
        delay_0 = calculate_exponential_backoff_delay(
            initial_delay, 0, exponential_base, max_delay
        )
        assert 1.0 <= delay_0 <= 1.5

        # Attempt 1: 1 * 2^1 = 2 seconds
        delay_1 = calculate_exponential_backoff_delay(
            initial_delay, 1, exponential_base, max_delay
        )
        assert 2.0 <= delay_1 <= 3.0

        # Attempt 2: 1 * 2^2 = 4 seconds
        delay_2 = calculate_exponential_backoff_delay(
            initial_delay, 2, exponential_base, max_delay
        )
        assert 4.0 <= delay_2 <= 6.0

    def test_respects_max_delay_cap(self):
        """Should cap delay at maximum value."""
        # Arrange
        initial_delay = 1
        attempt = 10  # Would be 1024 seconds without cap
        exponential_base = 2
        max_delay = 60

        # Act
        delay = calculate_exponential_backoff_delay(
            initial_delay, attempt, exponential_base, max_delay
        )

        # Assert - Should be capped at max_delay
        assert delay <= max_delay * 1.5  # Allow for jitter

    def test_adds_jitter_for_randomization(self):
        """Should add random jitter to prevent thundering herd."""
        # Arrange
        initial_delay = 10
        attempt = 0
        exponential_base = 2
        max_delay = 60

        # Act - Calculate multiple times
        delays = [
            calculate_exponential_backoff_delay(
                initial_delay, attempt, exponential_base, max_delay
            )
            for _ in range(10)
        ]

        # Assert - Should have variation due to jitter
        unique_delays = set(delays)
        assert len(unique_delays) > 1  # Should have different values


class TestIsTransientError:
    """Test cases for transient error detection."""

    def test_identifies_connection_error_as_transient(self):
        """Should identify connection errors as transient."""
        # Arrange
        error = ConnectionError("Connection failed")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_identifies_timeout_error_as_transient(self):
        """Should identify timeout errors as transient."""
        # Arrange
        error = TimeoutError("Request timed out")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_identifies_rate_limit_error_as_transient(self):
        """Should identify rate limit errors as transient."""
        # Arrange
        from downloader.opensubtitles_client import OpenSubtitlesRateLimitError

        error = OpenSubtitlesRateLimitError("Rate limit exceeded")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_identifies_authentication_error_as_permanent(self):
        """Should identify authentication errors as permanent."""
        # Arrange
        from downloader.opensubtitles_client import OpenSubtitlesAuthenticationError

        error = OpenSubtitlesAuthenticationError("Invalid credentials")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is False

    def test_identifies_generic_api_error_with_status_503_as_transient(self):
        """Should identify 503 errors as transient."""
        # Arrange
        from downloader.opensubtitles_client import OpenSubtitlesAPIError

        error = OpenSubtitlesAPIError("Service unavailable: 503")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is True

    def test_identifies_generic_api_error_without_status_as_permanent(self):
        """Should identify generic API errors as permanent."""
        # Arrange
        from downloader.opensubtitles_client import OpenSubtitlesAPIError

        error = OpenSubtitlesAPIError("Invalid request")

        # Act
        result = is_transient_error(error)

        # Assert
        assert result is False

    def test_identifies_openai_rate_limit_error_as_transient(self):
        """Should identify OpenAI RateLimitError as transient."""
        try:
            import httpx
            from openai import RateLimitError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(429, request=mock_request)
            mock_response.headers = httpx.Headers()
            error = RateLimitError(
                "Rate limit exceeded", response=mock_response, body=None
            )

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_connection_error_as_transient(self):
        """Should identify OpenAI APIConnectionError as transient."""
        try:
            from openai import APIConnectionError

            # Arrange
            error = APIConnectionError(message="Connection failed", request=None)

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_timeout_error_as_transient(self):
        """Should identify OpenAI APITimeoutError as transient."""
        try:
            import httpx
            from openai import APITimeoutError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            error = APITimeoutError(request=mock_request)

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_429_status_as_transient(self):
        """Should identify OpenAI APIError with 429 status as transient."""
        try:
            import httpx
            from openai import APIError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(429, request=mock_request)
            mock_response.headers = httpx.Headers()
            error = APIError(
                message="Rate limit exceeded",
                request=mock_request,
                body=None,
            )
            error.status_code = 429

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_500_status_as_transient(self):
        """Should identify OpenAI APIError with 500 status as transient."""
        try:
            import httpx
            from openai import APIError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(500, request=mock_request)
            mock_response.headers = httpx.Headers()
            error = APIError(
                message="Internal server error",
                request=mock_request,
                body=None,
            )
            error.status_code = 500

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_503_status_as_transient(self):
        """Should identify OpenAI APIError with 503 status as transient."""
        try:
            import httpx
            from openai import APIError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(503, request=mock_request)
            mock_response.headers = httpx.Headers()
            error = APIError(
                message="Service unavailable",
                request=mock_request,
                body=None,
            )
            error.status_code = 503

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_400_status_as_permanent(self):
        """Should identify OpenAI APIError with 400 status as permanent."""
        try:
            import httpx
            from openai import APIError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(400, request=mock_request)
            mock_response.headers = httpx.Headers()
            error = APIError(
                message="Bad request",
                request=mock_request,
                body=None,
            )
            error.status_code = 400

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is False
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_401_status_as_permanent(self):
        """Should identify OpenAI APIError with 401 status as permanent."""
        try:
            import httpx
            from openai import APIError

            # Arrange - Create mock httpx objects
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(401, request=mock_request)
            mock_response.headers = httpx.Headers()
            error = APIError(
                message="Unauthorized",
                request=mock_request,
                body=None,
            )
            error.status_code = 401

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is False
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_rate_limit_message_as_transient(self):
        """Should identify OpenAI APIError with rate limit message as transient."""
        try:
            from openai import APIError

            # Arrange - APIError without status_code but with rate limit message
            error = APIError(
                message="Rate limit exceeded. Please try again later.",
                request=None,
                body=None,
            )

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_openai_api_error_with_overloaded_message_as_transient(self):
        """Should identify OpenAI APIError with overloaded message as transient."""
        try:
            from openai import APIError

            # Arrange
            error = APIError(
                message="The API is currently overloaded",
                request=None,
                body=None,
            )

            # Act
            result = is_transient_error(error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")

    def test_identifies_wrapped_openai_error_in_cause_chain(self):
        """Should identify OpenAI errors wrapped in cause chain."""
        try:
            import httpx
            from openai import RateLimitError

            # Arrange - Wrap RateLimitError in a generic Exception
            mock_request = httpx.Request(
                "POST", "https://api.openai.com/v1/chat/completions"
            )
            mock_response = httpx.Response(429, request=mock_request)
            mock_response.headers = httpx.Headers()
            rate_limit_error = RateLimitError(
                "Rate limit", response=mock_response, body=None
            )
            wrapped_error = Exception("Wrapper error")
            wrapped_error.__cause__ = rate_limit_error

            # Act
            result = is_transient_error(wrapped_error)

            # Assert
            assert result is True
        except ImportError:
            pytest.skip("OpenAI SDK not available")


class TestRetryWithExponentialBackoff:
    """Test cases for retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """Should return result on first successful attempt."""
        # Arrange
        mock_func = AsyncMock(return_value="success")
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=1,
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act
        result = await decorated_func()

        # Assert
        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self):
        """Should retry on transient errors."""
        # Arrange
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Failed"),
                ConnectionError("Failed"),
                "success",
            ]
        )
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=0.1,  # Small delay for testing
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act
        result = await decorated_func()

        # Assert
        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self):
        """Should raise error after exhausting retries."""
        # Arrange
        mock_func = AsyncMock(side_effect=ConnectionError("Failed"))
        decorated_func = retry_with_exponential_backoff(
            max_retries=2,
            initial_delay=0.1,
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act & Assert
        with pytest.raises(ConnectionError):
            await decorated_func()

        # Should try initial + 2 retries = 3 total attempts
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_does_not_retry_on_permanent_error(self):
        """Should not retry on permanent errors."""
        # Arrange
        from downloader.opensubtitles_client import OpenSubtitlesAuthenticationError

        mock_func = AsyncMock(
            side_effect=OpenSubtitlesAuthenticationError("Invalid credentials")
        )
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=0.1,
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act & Assert
        with pytest.raises(OpenSubtitlesAuthenticationError):
            await decorated_func()

        # Should fail immediately without retries
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_logs_retry_attempts(self):
        """Should log retry attempts with details."""
        # Arrange
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Failed"),
                "success",
            ]
        )
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=0.1,
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act
        with patch("common.retry_utils.logger") as mock_logger:
            result = await decorated_func()

        # Assert
        assert result == "success"
        # Should log retry warning
        assert mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_waits_between_retries(self):
        """Should wait with exponential backoff between retries."""
        # Arrange
        mock_func = AsyncMock(
            side_effect=[
                ConnectionError("Failed"),
                ConnectionError("Failed"),
                "success",
            ]
        )
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=0.1,
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act
        start_time = asyncio.get_event_loop().time()
        result = await decorated_func()
        end_time = asyncio.get_event_loop().time()
        elapsed = end_time - start_time

        # Assert
        assert result == "success"
        # Should have waited at least 0.1 + 0.2 = 0.3 seconds
        assert elapsed >= 0.3

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs_to_function(self):
        """Should pass arguments and keyword arguments to wrapped function."""
        # Arrange
        mock_func = AsyncMock(return_value="success")
        decorated_func = retry_with_exponential_backoff(
            max_retries=3,
            initial_delay=0.1,
            exponential_base=2,
            max_delay=60,
        )(mock_func)

        # Act
        result = await decorated_func("arg1", "arg2", kwarg1="value1", kwarg2="value2")

        # Assert
        assert result == "success"
        mock_func.assert_called_once_with(
            "arg1", "arg2", kwarg1="value1", kwarg2="value2"
        )
