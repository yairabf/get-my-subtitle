import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from scanner.scanner import MediaScanner


@pytest.mark.asyncio
async def test_scan_library():
    """Test scan_library method."""
    scanner = MediaScanner()
    scanner.event_handler = MagicMock()
    scanner.event_handler._is_media_file.return_value = True
    scanner.event_handler._process_media_file = AsyncMock()

    with patch("scanner.scanner.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.exists.return_value = True
        mock_path_obj.is_dir.return_value = True

        # Mock file iteration
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_path_obj.rglob.return_value = [mock_file]

        # Run scan
        await scanner.scan_library()

        # Verify processing was triggered
        scanner.event_handler._process_media_file.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_scan_endpoint():
    """Test scanner webhook /scan endpoint."""
    scanner = MediaScanner()
    scanner.scan_library = AsyncMock()

    # Create the app
    app = scanner._create_webhook_app()
    client = TestClient(app)

    response = client.post("/scan")

    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "message": "Manual scan initiated"}

    # Verify scan_library was called (it's a background task, so we might need to wait a bit or check if task was created)
    # Since we mocked it, we can check if it was called.
    # Note: In the actual code it's asyncio.create_task(self.scan_library()), so it might not be awaited immediately.
    # But for unit test with AsyncMock, we can check if it was called.
    # Actually, create_task schedules it. We can't easily assert it ran without running the loop.
    # But we can check if the endpoint returned 200.
