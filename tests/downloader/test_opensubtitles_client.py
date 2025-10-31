"""Tests for OpenSubtitles XML-RPC API client."""

import base64
import gzip
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from downloader.opensubtitles_client import (
    OpenSubtitlesAPIError,
    OpenSubtitlesAuthenticationError,
    OpenSubtitlesClient,
)


class TestOpenSubtitlesAuthentication:
    """Test OpenSubtitles XML-RPC authentication."""

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
            with pytest.raises(
                OpenSubtitlesAuthenticationError, match="XML-RPC authentication failed"
            ):
                await client._authenticate_xmlrpc()

    @pytest.mark.asyncio
    async def test_authenticate_no_credentials(self):
        """Test authentication fails when no credentials provided."""
        client = OpenSubtitlesClient()
        client.username = None
        client.password = None

        with pytest.raises(
            OpenSubtitlesAuthenticationError, match="No valid credentials"
        ):
            await client.authenticate()


class TestOpenSubtitlesSearch:
    """Test OpenSubtitles subtitle search."""

    @pytest.mark.asyncio
    async def test_search_subtitles_xmlrpc_found(self):
        """Test successful subtitle search with XML-RPC API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

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
    async def test_search_subtitles_xmlrpc_not_found(self):
        """Test subtitle search returns empty when nothing found."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "200 OK",
            "data": [],
        }

        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            results = await client.search_subtitles(query="Nonexistent Movie")

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_subtitles_not_authenticated(self):
        """Test search fails when not authenticated."""
        client = OpenSubtitlesClient()
        client.token = None

        with pytest.raises(OpenSubtitlesAPIError, match="Not authenticated"):
            await client.search_subtitles(query="Test Movie")

    @pytest.mark.asyncio
    async def test_search_xmlrpc_error(self):
        """Test handling of XML-RPC search errors."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "500 Internal Server Error",
            "data": [],
        }

        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            with pytest.raises(OpenSubtitlesAPIError, match="XML-RPC search failed"):
                await client.search_subtitles(query="Test Movie")


class TestOpenSubtitlesDownload:
    """Test OpenSubtitles subtitle download."""

    @pytest.mark.asyncio
    async def test_download_subtitle_xmlrpc_success(self, tmp_path):
        """Test successful subtitle download with XML-RPC API."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        subtitle_content = b"1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n"
        compressed_content = gzip.compress(subtitle_content)
        encoded_content = base64.b64encode(compressed_content).decode()

        mock_result = {
            "status": "200 OK",
            "data": [{"data": encoded_content}],
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
    async def test_download_subtitle_not_authenticated(self):
        """Test download fails when not authenticated."""
        client = OpenSubtitlesClient()
        client.token = None

        with pytest.raises(OpenSubtitlesAPIError, match="Not authenticated"):
            await client.download_subtitle(subtitle_id="123")

    @pytest.mark.asyncio
    async def test_download_xmlrpc_error(self):
        """Test handling of XML-RPC download errors."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "500 Internal Server Error",
            "data": [],
        }

        with patch.object(client, "_xmlrpc_download", return_value=mock_result):
            with pytest.raises(OpenSubtitlesAPIError, match="XML-RPC download failed"):
                await client.download_subtitle(subtitle_id="123")


class TestOpenSubtitlesHashSearch:
    """Test OpenSubtitles hash-based subtitle search."""

    @pytest.mark.asyncio
    async def test_search_subtitles_by_hash_found(self):
        """Test successful subtitle search using file hash."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "200 OK",
            "data": [
                {
                    "IDSubtitleFile": "12345",
                    "SubLanguageID": "eng",
                    "MovieHash": "8e245d9679d31e12",
                    "MovieByteSize": "735934464",
                }
            ],
        }

        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            results = await client.search_subtitles_by_hash(
                movie_hash="8e245d9679d31e12",
                file_size=735934464,
                languages=["en"],
            )

            assert len(results) == 1
            assert results[0]["IDSubtitleFile"] == "12345"
            assert results[0]["MovieHash"] == "8e245d9679d31e12"

    @pytest.mark.asyncio
    async def test_search_subtitles_by_hash_not_found(self):
        """Test hash search returns empty when nothing found."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "200 OK",
            "data": [],
        }

        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            results = await client.search_subtitles_by_hash(
                movie_hash="0000000000000000",
                file_size=12345,
            )

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_by_hash_not_authenticated(self):
        """Test hash search fails when not authenticated."""
        client = OpenSubtitlesClient()
        client.token = None

        with pytest.raises(OpenSubtitlesAPIError, match="Not authenticated"):
            await client.search_subtitles_by_hash(
                movie_hash="8e245d9679d31e12",
                file_size=735934464,
            )

    @pytest.mark.asyncio
    async def test_search_by_hash_xmlrpc_error(self):
        """Test handling of XML-RPC hash search errors."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "500 Internal Server Error",
            "data": [],
        }

        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            with pytest.raises(
                OpenSubtitlesAPIError, match="XML-RPC hash search failed"
            ):
                await client.search_subtitles_by_hash(
                    movie_hash="8e245d9679d31e12",
                    file_size=735934464,
                )

    @pytest.mark.asyncio
    async def test_search_by_hash_with_multiple_languages(self):
        """Test hash search with multiple languages."""
        client = OpenSubtitlesClient()
        client.token = "test-token"

        mock_result = {
            "status": "200 OK",
            "data": [
                {"IDSubtitleFile": "111", "SubLanguageID": "eng"},
                {"IDSubtitleFile": "222", "SubLanguageID": "heb"},
            ],
        }

        with patch.object(client, "_xmlrpc_search", return_value=mock_result):
            results = await client.search_subtitles_by_hash(
                movie_hash="8e245d9679d31e12",
                file_size=735934464,
                languages=["en", "he"],
            )

            assert len(results) == 2


class TestOpenSubtitlesClientLifecycle:
    """Test client connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        """Test client connect and disconnect lifecycle."""
        client = OpenSubtitlesClient()
        client.username = "test-user"
        client.password = "test-pass"

        mock_result = {"status": "200 OK", "token": "test-token"}

        with patch.object(client, "_xmlrpc_login", return_value=mock_result):
            await client.connect()

            assert client.token == "test-token"

            await client.disconnect()

            assert client.token is None
            assert client.xmlrpc_client is None
