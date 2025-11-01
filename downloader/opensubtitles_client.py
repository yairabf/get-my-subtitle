"""OpenSubtitles XML-RPC API client."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from xmlrpc.client import ServerProxy

from common.config import settings
from common.retry_utils import retry_with_exponential_backoff

logger = logging.getLogger(__name__)


class OpenSubtitlesAuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class OpenSubtitlesAPIError(Exception):
    """Raised when API request fails."""

    pass


class OpenSubtitlesRateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class OpenSubtitlesClient:
    """
    Client for OpenSubtitles XML-RPC API.

    Authenticates using username and password.
    """

    def __init__(self):
        """Initialize OpenSubtitles client."""
        self.user_agent = settings.opensubtitles_user_agent
        self.username = settings.opensubtitles_username
        self.password = settings.opensubtitles_password
        self.max_retries = settings.opensubtitles_max_retries
        self.retry_delay = settings.opensubtitles_retry_delay

        self.token: Optional[str] = None
        self.xmlrpc_client: Optional[ServerProxy] = None

    def _create_retry_decorator(self):
        """Create retry decorator with configured settings."""
        return retry_with_exponential_backoff(
            max_retries=settings.opensubtitles_max_retries,
            initial_delay=float(settings.opensubtitles_retry_delay),
            exponential_base=settings.opensubtitles_retry_exponential_base,
            max_delay=float(settings.opensubtitles_retry_max_delay),
        )

    async def connect(self) -> None:
        """Initialize client and authenticate."""
        await self.authenticate()
        logger.info("✅ OpenSubtitles client connected using XML-RPC")

    async def disconnect(self) -> None:
        """Close client connection."""
        self.token = None
        self.xmlrpc_client = None
        logger.info("🔌 OpenSubtitles client disconnected")

    async def authenticate(self) -> None:
        """
        Authenticate with OpenSubtitles XML-RPC API.

        Raises:
            OpenSubtitlesAuthenticationError: If authentication fails
        """
        if not self.username or not self.password:
            raise OpenSubtitlesAuthenticationError(
                "No valid credentials provided (need username and password)"
            )

        try:
            await self._authenticate_xmlrpc()
            logger.info("✅ Authenticated with OpenSubtitles XML-RPC API")
        except OpenSubtitlesAuthenticationError as e:
            logger.error(f"❌ XML-RPC authentication failed: {e}")
            raise

    async def _authenticate_xmlrpc(self) -> None:
        """
        Authenticate using XML-RPC API with username/password.
        Includes automatic retry with exponential backoff for transient errors.

        Raises:
            OpenSubtitlesAuthenticationError: If authentication fails
        """
        # Wrap the authentication logic with retry decorator
        @self._create_retry_decorator()
        async def _do_authenticate():
            try:
                # XML-RPC is synchronous, run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._xmlrpc_login,
                )

                if result.get("status") != "200 OK":
                    raise OpenSubtitlesAuthenticationError(
                        f"XML-RPC authentication failed: {result.get('status')}"
                    )

                self.token = result.get("token")

                if not self.token:
                    raise OpenSubtitlesAuthenticationError(
                        "No token in XML-RPC response"
                    )

            except Exception as e:
                raise OpenSubtitlesAuthenticationError(
                    f"XML-RPC authentication error: {e}"
                ) from e

        await _do_authenticate()

    def _xmlrpc_login(self) -> Dict[str, Any]:
        """Execute XML-RPC login (synchronous)."""
        if not self.xmlrpc_client:
            self.xmlrpc_client = ServerProxy("https://api.opensubtitles.org/xml-rpc")

        return self.xmlrpc_client.LogIn(
            self.username,
            self.password,
            "en",
            self.user_agent,
        )

    async def search_subtitles(
        self,
        imdb_id: Optional[str] = None,
        query: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for subtitles using available metadata.

        Args:
            imdb_id: IMDB ID of the video (without 'tt' prefix)
            query: Search query (movie/TV show name)
            languages: List of language codes (e.g., ['en', 'he'])

        Returns:
            List of subtitle results

        Raises:
            OpenSubtitlesAPIError: If search fails
        """
        if not self.token:
            raise OpenSubtitlesAPIError("Not authenticated")

        return await self._search_subtitles_xmlrpc(imdb_id, query, languages)

    async def search_subtitles_by_hash(
        self,
        movie_hash: str,
        file_size: int,
        languages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for subtitles using file hash and size.

        Args:
            movie_hash: 16-character OpenSubtitles hash
            file_size: File size in bytes
            languages: List of language codes (e.g., ['en', 'he'])

        Returns:
            List of subtitle results

        Raises:
            OpenSubtitlesAPIError: If search fails
        """
        if not self.token:
            raise OpenSubtitlesAPIError("Not authenticated")

        return await self._search_subtitles_by_hash_xmlrpc(
            movie_hash, file_size, languages
        )

    async def _search_subtitles_xmlrpc(
        self,
        imdb_id: Optional[str] = None,
        query: Optional[str] = None,
        languages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search subtitles using XML-RPC API.
        Includes automatic retry with exponential backoff for transient errors.
        """
        search_criteria = []

        if imdb_id:
            search_criteria.append({"imdbid": imdb_id})
        if query:
            search_criteria.append({"query": query})
        if languages:
            for criteria in search_criteria:
                criteria["sublanguageid"] = ",".join(languages)

        if not search_criteria:
            return []

        @self._create_retry_decorator()
        async def _do_search():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._xmlrpc_search,
                    search_criteria,
                )

                if result.get("status") != "200 OK":
                    raise OpenSubtitlesAPIError(
                        f"XML-RPC search failed: {result.get('status')}"
                    )

                return result.get("data", [])

            except Exception as e:
                raise OpenSubtitlesAPIError(f"XML-RPC search error: {e}") from e

        return await _do_search()

    def _xmlrpc_search(self, search_criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute XML-RPC search (synchronous)."""
        if not self.xmlrpc_client:
            self.xmlrpc_client = ServerProxy("https://api.opensubtitles.org/xml-rpc")

        return self.xmlrpc_client.SearchSubtitles(self.token, search_criteria)

    async def _search_subtitles_by_hash_xmlrpc(
        self,
        movie_hash: str,
        file_size: int,
        languages: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search subtitles by hash using XML-RPC API.
        Includes automatic retry with exponential backoff for transient errors.
        """
        search_criteria = [
            {
                "moviehash": movie_hash,
                "moviebytesize": str(file_size),
            }
        ]

        if languages:
            for criteria in search_criteria:
                criteria["sublanguageid"] = ",".join(languages)

        @self._create_retry_decorator()
        async def _do_hash_search():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._xmlrpc_search,
                    search_criteria,
                )

                if result.get("status") != "200 OK":
                    raise OpenSubtitlesAPIError(
                        f"XML-RPC hash search failed: {result.get('status')}"
                    )

                return result.get("data", [])

            except Exception as e:
                raise OpenSubtitlesAPIError(f"XML-RPC hash search error: {e}") from e

        return await _do_hash_search()

    async def download_subtitle(
        self,
        subtitle_id: str,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Download subtitle file.

        Args:
            subtitle_id: Subtitle ID from search results
            output_path: Optional output path (default: storage path from config)

        Returns:
            Path to downloaded subtitle file

        Raises:
            OpenSubtitlesAPIError: If download fails
        """
        if not self.token:
            raise OpenSubtitlesAPIError("Not authenticated")

        return await self._download_subtitle_xmlrpc(subtitle_id, output_path)

    async def _download_subtitle_xmlrpc(
        self,
        subtitle_id: str,
        output_path: Optional[Path],
    ) -> Path:
        """
        Download subtitle using XML-RPC API.
        Includes automatic retry with exponential backoff for transient errors.
        """

        @self._create_retry_decorator()
        async def _do_download():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._xmlrpc_download,
                    subtitle_id,
                )

                if result.get("status") != "200 OK":
                    raise OpenSubtitlesAPIError(
                        f"XML-RPC download failed: {result.get('status')}"
                    )

                # Get subtitle content (base64 encoded and gzip compressed)
                import base64
                import gzip

                subtitle_data = result.get("data", [])

                # XML-RPC returns data as a list with one element containing the subtitle
                if isinstance(subtitle_data, list) and len(subtitle_data) > 0:
                    encoded_data = subtitle_data[0].get("data", "")
                    # Decode from base64
                    compressed_data = base64.b64decode(encoded_data)
                    # Decompress gzip
                    subtitle_content = gzip.decompress(compressed_data)
                else:
                    raise OpenSubtitlesAPIError("No subtitle data in response")

                # Save to file
                final_output_path = output_path
                if not final_output_path:
                    storage_path = Path(settings.subtitle_storage_path)
                    storage_path.mkdir(parents=True, exist_ok=True)
                    final_output_path = storage_path / f"{subtitle_id}.srt"

                final_output_path.write_bytes(subtitle_content)
                logger.info(f"✅ Downloaded subtitle to {final_output_path}")

                return final_output_path

            except Exception as e:
                raise OpenSubtitlesAPIError(f"XML-RPC download error: {e}") from e

        return await _do_download()

    def _xmlrpc_download(self, subtitle_id: str) -> Dict[str, Any]:
        """Execute XML-RPC download (synchronous)."""
        if not self.xmlrpc_client:
            self.xmlrpc_client = ServerProxy("https://api.opensubtitles.org/xml-rpc")

        return self.xmlrpc_client.DownloadSubtitles(self.token, [subtitle_id])
