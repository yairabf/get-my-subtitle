"""Tests for OpenSubtitles API client."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from xmlrpc.client import ServerProxy

import httpx
import pytest

from downloader.opensubtitles_client import (
    OpenSubtitlesAPIError,
    OpenSubtitlesAuthenticationError,
    OpenSubtitlesClient,
    OpenSubtitlesRateLimitError,
)


class TestOpenSubtitlesAuthentication:
    """Test OpenSubtitles authentication flows."""

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key_success(self):
        """Test successful authentication with REST API key."""
        client = OpenSubtitlesClient()
        client.api_key = "test-api-key"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test-token", "user": {}}
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_response)
            
            await client._authenticate_rest()
            
            assert client.token == "test-token"
            mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_with_api_key_failure(self):
        """Test authentication failure with invalid API key."""
        client = OpenSubtitlesClient()
        client.api_key = "invalid-key"
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_response)
            
            with pytest.raises(OpenSubtitlesAuthenticationError, match="Invalid API key"):
                await client._authenticate_rest()

    @pytest.mark.asyncio
    async def test_authenticate_with_username_password_success(self):
        """Test successful authentication with XML-RPC username/password."""
        client = OpenSubtitlesClient()
        client.username = "test-user"
        client.password = "test-pass"
        
        mock_result = {"status": "200 OK", "token": "xmlrpc-token"}
        
        with patch.object(client, "_xmlrpc_login", return_value=mock_result):
            await client._authenticate_xmlrpc()
            
            assert client.token == "xmlrpc-token"

    @pytest.mark.asyncio
    async def test_authenticate_with_username_password_failure(self):
        """Test authentication failure with invalid username/password."""
        client = OpenSubtitlesClient()
        client.username = "invalid-user"
        client.password = "invalid-pass"
        
        mock_result = {"status": "401 Unauthorized"}
        
        with patch.object(client, "_xmlrpc_login", return_value=mock_result):
            with pytest.raises(OpenSubtitlesAuthenticationError, match="XML-RPC authentication failed"):
                await client._authenticate_xmlrpc()

    @pytest.mark.asyncio
    async def test_authenticate_fallback_to_xmlrpc(self):
        """Test fallback from REST API to XML-RPC when API key fails."""
        client = OpenSubtitlesClient()
        client.api_key = "invalid-key"
        client.username = "test-user"
        client.password = "test-pass"
        
        # Mock REST API failure
        mock_rest_response = MagicMock()
        mock_rest_response.status_code = 401
        
        # Mock XML-RPC success
        mock_xmlrpc_result = {"status": "200 OK", "token": "xmlrpc-token"}
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_rest_response)
            
            with patch.object(client, "_xmlrpc_login", return_value=mock_xmlrpc_result):
                await client.authenticate()
                
                assert client.auth_method == "xmlrpc"
                assert client.token == "xmlrpc-token"

    @pytest.mark.asyncio
    async def test_authenticate_no_credentials(self):
        """Test authentication fails when no credentials provided."""
        client = OpenSubtitlesClient()
        client.api_key = None
        client.username = None
        client.password = None
        
        with pytest.raises(OpenSubtitlesAuthenticationError, match="No valid credentials"):
            await client.authenticate()


class TestOpenSubtitlesSearch:
    """Test OpenSubtitles subtitle search."""

    @pytest.mark.asyncio
    async def test_search_subtitles_rest_api_found(self):
        """Test successful subtitle search with REST API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "rest"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "123",
                    "attributes": {
                        "language": "en",
                        "files": [{"file_id": 456}],
                    },
                }
            ]
        }
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.get = AsyncMock(return_value=mock_response)
            
            results = await client.search_subtitles(
                imdb_id="tt1234567",
                query="Test Movie",
                languages=["en"],
            )
            
            assert len(results) == 1
            assert results[0]["id"] == "123"

    @pytest.mark.asyncio
    async def test_search_subtitles_rest_api_not_found(self):
        """Test subtitle search returns empty when nothing found."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "rest"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.get = AsyncMock(return_value=mock_response)
            
            results = await client.search_subtitles(query="Nonexistent Movie")
            
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_subtitles_xmlrpc_found(self):
        """Test successful subtitle search with XML-RPC API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "xmlrpc"
        
        mock_result = {
            "status": "200 OK",
            "data": [
                {
                    "IDSubtitleFile": "789",
                    "SubLanguageID": "eng",
                }
            ],
        }
        
        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            results = await client.search_subtitles(
                imdb_id="1234567",
                query="Test Movie",
                languages=["en"],
            )
            
            assert len(results) == 1
            assert results[0]["IDSubtitleFile"] == "789"

    @pytest.mark.asyncio
    async def test_search_subtitles_token_expired_refresh(self):
        """Test token refresh when expired during search."""
        client = OpenSubtitlesClient()
        client.token = "expired-token"
        client.auth_method = "rest"
        client.api_key = "test-api-key"
        
        # First call returns 401, second call succeeds
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"data": [{"id": "123"}]}
        
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "new-token"}
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.get = AsyncMock(side_effect=[mock_response_401, mock_response_200])
            mock_http.post = AsyncMock(return_value=mock_auth_response)
            
            results = await client.search_subtitles(query="Test Movie")
            
            assert client.token == "new-token"
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_subtitles_rate_limit(self):
        """Test rate limit error handling."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "rest"
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.get = AsyncMock(return_value=mock_response)
            
            with pytest.raises(OpenSubtitlesRateLimitError):
                await client.search_subtitles(query="Test Movie")

    @pytest.mark.asyncio
    async def test_search_subtitles_not_authenticated(self):
        """Test search fails when not authenticated."""
        client = OpenSubtitlesClient()
        client.token = None
        
        with pytest.raises(OpenSubtitlesAPIError, match="Not authenticated"):
            await client.search_subtitles(query="Test Movie")


class TestOpenSubtitlesDownload:
    """Test OpenSubtitles subtitle download."""

    @pytest.mark.asyncio
    async def test_download_subtitle_rest_api_success(self, tmp_path):
        """Test successful subtitle download with REST API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "rest"
        
        # Mock download link response
        mock_link_response = MagicMock()
        mock_link_response.status_code = 200
        mock_link_response.json.return_value = {"link": "https://example.com/subtitle.srt"}
        
        # Mock actual subtitle file download
        mock_file_response = MagicMock()
        mock_file_response.status_code = 200
        mock_file_response.content = b"1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n"
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_link_response)
            mock_http.get = AsyncMock(return_value=mock_file_response)
            
            output_path = tmp_path / "test.srt"
            result_path = await client.download_subtitle(
                subtitle_id="123",
                file_id="456",
                output_path=output_path,
            )
            
            assert result_path.exists()
            assert result_path.read_text().startswith("1\n")

    @pytest.mark.asyncio
    async def test_download_subtitle_xmlrpc_success(self, tmp_path):
        """Test successful subtitle download with XML-RPC API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "xmlrpc"
        
        import base64
        subtitle_content = b"1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n"
        encoded_content = base64.b64encode(subtitle_content).decode()
        
        mock_result = {
            "status": "200 OK",
            "data": {"data": encoded_content},
        }
        
        with patch.object(client, "_xmlrpc_download", return_value=mock_result):
            output_path = tmp_path / "test.srt"
            result_path = await client.download_subtitle(
                subtitle_id="789",
                output_path=output_path,
            )
            
            assert result_path.exists()
            assert result_path.read_bytes() == subtitle_content

    @pytest.mark.asyncio
    async def test_download_subtitle_rest_api_no_file_id(self):
        """Test download fails when file_id missing for REST API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "rest"
        
        with pytest.raises(OpenSubtitlesAPIError, match="file_id required"):
            await client.download_subtitle(subtitle_id="123", file_id=None)

    @pytest.mark.asyncio
    async def test_download_subtitle_not_authenticated(self):
        """Test download fails when not authenticated."""
        client = OpenSubtitlesClient()
        client.token = None
        
        with pytest.raises(OpenSubtitlesAPIError, match="Not authenticated"):
            await client.download_subtitle(subtitle_id="123", file_id="456")

    @pytest.mark.asyncio
    async def test_download_subtitle_rate_limit(self):
        """Test download handles rate limit error."""
        client = OpenSubtitlesClient()
        client.token = "test-token"
        client.auth_method = "rest"
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_response)
            
            with pytest.raises(OpenSubtitlesRateLimitError):
                await client.download_subtitle(subtitle_id="123", file_id="456")

    @pytest.mark.asyncio
    async def test_download_subtitle_token_expired_refresh(self, tmp_path):
        """Test token refresh when expired during download."""
        client = OpenSubtitlesClient()
        client.token = "expired-token"
        client.auth_method = "rest"
        client.api_key = "test-api-key"
        
        # First POST returns 401, second succeeds
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"link": "https://example.com/subtitle.srt"}
        
        mock_auth_response = MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {"token": "new-token"}
        
        mock_file_response = MagicMock()
        mock_file_response.status_code = 200
        mock_file_response.content = b"Test subtitle content"
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(side_effect=[mock_response_401, mock_auth_response, mock_response_200])
            mock_http.get = AsyncMock(return_value=mock_file_response)
            
            output_path = tmp_path / "test.srt"
            result_path = await client.download_subtitle(
                subtitle_id="123",
                file_id="456",
                output_path=output_path,
            )
            
            assert client.token == "new-token"
            assert result_path.exists()


class TestOpenSubtitlesRetryLogic:
    """Test retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        """Test retry mechanism on network errors."""
        client = OpenSubtitlesClient()
        client.api_key = "test-api-key"
        
        # Simulate network error then success
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"token": "test-token"}
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(
                side_effect=[
                    httpx.RequestError("Network error"),
                    mock_success_response,
                ]
            )
            
            await client._authenticate_rest()
            
            assert client.token == "test-token"
            assert mock_http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test retry mechanism on timeout errors."""
        client = OpenSubtitlesClient()
        client.api_key = "test-api-key"
        
        # Simulate timeout then success
        mock_success_response = MagicMock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"token": "test-token"}
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(
                side_effect=[
                    httpx.TimeoutException("Timeout"),
                    mock_success_response,
                ]
            )
            
            await client._authenticate_rest()
            
            assert client.token == "test-token"
            assert mock_http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test failure after maximum retries exceeded."""
        client = OpenSubtitlesClient()
        client.api_key = "test-api-key"
        
        with patch.object(client, "http_client") as mock_http:
            mock_http.post = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )
            
            with pytest.raises(httpx.RequestError):
                await client._authenticate_rest()
            
            # Should attempt 3 times (configured in @retry decorator)
            assert mock_http.post.call_count == 3


class TestOpenSubtitlesClientLifecycle:
    """Test client connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        """Test client connect and disconnect lifecycle."""
        client = OpenSubtitlesClient()
        client.api_key = "test-api-key"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "test-token"}
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http_instance = AsyncMock()
            mock_http_instance.post = AsyncMock(return_value=mock_response)
            mock_http_instance.aclose = AsyncMock()
            mock_client_class.return_value = mock_http_instance
            
            await client.connect()
            
            assert client.http_client is not None
            assert client.token == "test-token"
            assert client.auth_method == "rest"
            
            await client.disconnect()
            
            assert client.token is None
            assert client.auth_method is None
            mock_http_instance.aclose.assert_called_once()

