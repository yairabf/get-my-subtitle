"""Unit tests for retry behavior in OpenSubtitles client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from downloader.opensubtitles_client import (
    OpenSubtitlesAPIError,
    OpenSubtitlesAuthenticationError,
    OpenSubtitlesClient,
    OpenSubtitlesRateLimitError,
)


class TestOpenSubtitlesClientRetryBehavior:
    """Test cases for retry logic in OpenSubtitles client."""

    @pytest.mark.asyncio
    async def test_authentication_succeeds_on_first_attempt(self):
        """Should authenticate successfully on first attempt without retries."""
        # Arrange
        client = OpenSubtitlesClient()

        mock_result = {"status": "200 OK", "token": "test-token-123"}

        with patch.object(
            client, "_xmlrpc_login", return_value=mock_result
        ) as mock_login:
            # Act
            await client._authenticate_xmlrpc()

            # Assert
            assert client.token == "test-token-123"
            assert mock_login.call_count == 1

    @pytest.mark.asyncio
    async def test_authentication_retries_on_transient_error(self):
        """Should retry authentication on transient errors."""
        # Arrange
        client = OpenSubtitlesClient()

        # First two attempts fail with connection error, third succeeds
        mock_login_calls = [
            ConnectionError("Network error"),
            ConnectionError("Network error"),
            {"status": "200 OK", "token": "test-token-123"},
        ]

        def side_effect():
            result = mock_login_calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(
            client, "_xmlrpc_login", side_effect=side_effect
        ) as mock_login:
            # Act
            await client._authenticate_xmlrpc()

            # Assert
            assert client.token == "test-token-123"
            assert mock_login.call_count == 3

    @pytest.mark.asyncio
    async def test_authentication_fails_after_max_retries(self):
        """Should fail after exhausting retries on persistent errors."""
        # Arrange
        client = OpenSubtitlesClient()

        with patch.object(
            client, "_xmlrpc_login", side_effect=ConnectionError("Network error")
        ) as mock_login:
            # Act & Assert
            with pytest.raises(OpenSubtitlesAuthenticationError):
                await client._authenticate_xmlrpc()

            # Should try initial + max_retries times
            assert mock_login.call_count == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_authentication_fails_immediately_on_auth_error(self):
        """Should not retry on authentication errors (permanent)."""
        # Arrange
        client = OpenSubtitlesClient()

        mock_result = {"status": "401 Unauthorized"}

        with patch.object(
            client, "_xmlrpc_login", return_value=mock_result
        ) as mock_login:
            # Act & Assert
            with pytest.raises(OpenSubtitlesAuthenticationError):
                await client._authenticate_xmlrpc()

            # Should only try once (no retries for auth errors)
            assert mock_login.call_count == 1

    @pytest.mark.asyncio
    async def test_search_retries_on_connection_error(self):
        """Should retry search on connection errors."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        search_calls = [
            ConnectionError("Network error"),
            {"status": "200 OK", "data": [{"IDSubtitleFile": "123"}]},
        ]

        def side_effect(*args):
            result = search_calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(
            client, "_xmlrpc_search", side_effect=side_effect
        ) as mock_search:
            # Act
            results = await client._search_subtitles_xmlrpc(query="test movie")

            # Assert
            assert len(results) == 1
            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_search_retries_on_503_error(self):
        """Should retry search on 503 service unavailable."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        search_calls = [
            {"status": "503 Service Unavailable"},
            {"status": "200 OK", "data": [{"IDSubtitleFile": "123"}]},
        ]

        def side_effect(*args):
            result = search_calls.pop(0)
            if result["status"] != "200 OK":
                raise OpenSubtitlesAPIError(
                    f"XML-RPC search failed: {result['status']}"
                )
            return result

        with patch.object(
            client, "_xmlrpc_search", side_effect=side_effect
        ) as mock_search:
            # Act
            results = await client._search_subtitles_xmlrpc(query="test movie")

            # Assert
            assert len(results) == 1
            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_hash_search_retries_on_transient_error(self):
        """Should retry hash-based search on transient errors."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        search_calls = [
            TimeoutError("Request timeout"),
            {"status": "200 OK", "data": [{"IDSubtitleFile": "456"}]},
        ]

        def side_effect(*args):
            result = search_calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(
            client, "_xmlrpc_search", side_effect=side_effect
        ) as mock_search:
            # Act
            results = await client._search_subtitles_by_hash_xmlrpc(
                movie_hash="abc123", file_size=1024
            )

            # Assert
            assert len(results) == 1
            assert mock_search.call_count == 2

    @pytest.mark.asyncio
    async def test_download_retries_on_network_error(self):
        """Should retry download on network errors."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        import base64
        import gzip

        # Prepare valid subtitle data
        subtitle_content = b"1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n"
        compressed = gzip.compress(subtitle_content)
        encoded = base64.b64encode(compressed).decode()

        download_calls = [
            OSError("Network unreachable"),
            {"status": "200 OK", "data": [{"data": encoded}]},
        ]

        def side_effect(*args):
            result = download_calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(
            client, "_xmlrpc_download", side_effect=side_effect
        ) as mock_download:
            # Act
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test.srt"
                result_path = await client._download_subtitle_xmlrpc("123", output_path)

                # Assert
                assert result_path == output_path
                assert result_path.exists()
                assert mock_download.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_error_retries_with_backoff(self):
        """Should retry on rate limit errors with appropriate backoff."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        search_calls = [
            OpenSubtitlesRateLimitError("Rate limit exceeded"),
            {"status": "200 OK", "data": [{"IDSubtitleFile": "789"}]},
        ]

        def side_effect(*args):
            result = search_calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(
            client, "_xmlrpc_search", side_effect=side_effect
        ) as mock_search:
            # Act
            start_time = asyncio.get_event_loop().time()
            results = await client._search_subtitles_xmlrpc(query="test movie")
            end_time = asyncio.get_event_loop().time()
            elapsed = end_time - start_time

            # Assert
            assert len(results) == 1
            assert mock_search.call_count == 2
            # Should have waited at least the initial delay
            assert elapsed >= 1.0

    @pytest.mark.asyncio
    async def test_logs_retry_attempts(self):
        """Should log retry attempts with appropriate messages."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        search_calls = [
            ConnectionError("Network error"),
            {"status": "200 OK", "data": [{"IDSubtitleFile": "123"}]},
        ]

        def side_effect(*args):
            result = search_calls.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(client, "_xmlrpc_search", side_effect=side_effect):
            with patch("common.retry_utils.logger") as mock_logger:
                # Act
                await client._search_subtitles_xmlrpc(query="test movie")

                # Assert - Should log retry warning
                assert mock_logger.warning.called
                warning_message = str(mock_logger.warning.call_args[0][0])
                assert "Transient error" in warning_message
                assert "Retry" in warning_message

    @pytest.mark.asyncio
    async def test_permanent_error_does_not_retry(self):
        """Should not retry on permanent errors like 404."""
        # Arrange
        client = OpenSubtitlesClient()
        client.token = "test-token"

        # Permanent error - malformed request
        with patch.object(
            client,
            "_xmlrpc_search",
            side_effect=OpenSubtitlesAPIError("Invalid request: 400 Bad Request"),
        ) as mock_search:
            # Act & Assert
            with pytest.raises(OpenSubtitlesAPIError):
                await client._search_subtitles_xmlrpc(query="test movie")

            # Should only try once (no retries for permanent errors)
            assert mock_search.call_count == 1
