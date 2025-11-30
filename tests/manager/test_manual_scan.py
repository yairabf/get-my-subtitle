from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from manager.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_trigger_manual_scan_success():
    """Test successful manual scan trigger."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = client.post("/scan")

        assert response.status_code == 202
        assert response.json() == {
            "status": "accepted",
            "message": "Manual scan initiated",
        }
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_manual_scan_scanner_error():
    """Test manual scan trigger when scanner returns error."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        response = client.post("/scan")

        assert response.status_code == 502
        assert "Scanner service returned error" in response.json()["detail"]


@pytest.mark.asyncio
async def test_trigger_manual_scan_connection_error():
    """Test manual scan trigger when scanner is unreachable."""
    with patch("httpx.AsyncClient.post") as mock_post:
        import httpx

        mock_post.side_effect = httpx.RequestError("Connection refused")

        response = client.post("/scan")

        assert response.status_code == 503
        assert "Scanner service is unreachable" in response.json()["detail"]
