"""Tests for ffsubsync-based subtitle synchronization logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from downloader import worker as downloader_worker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sync_enabled,keep_unsynced_copy,expect_sync_applied,expect_unsynced_exists",
    [
        (False, True, False, False),
        (True, True, True, True),
        (True, False, True, False),
    ],
)
async def test_sync_subtitle_to_audio_if_enabled_success_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sync_enabled: bool,
    keep_unsynced_copy: bool,
    expect_sync_applied: bool,
    expect_unsynced_exists: bool,
) -> None:
    video_path = tmp_path / "video.mkv"
    video_path.write_bytes(b"\x00")

    subtitle_path = tmp_path / "video.en.srt"
    subtitle_path.write_text("ORIGINAL\n", encoding="utf-8")

    async def fake_run_ffsubsync(
        *,
        video_path: Path,
        input_subtitle_path: Path,
        output_subtitle_path: Path,
        timeout_seconds: int,
    ) -> Tuple[int, str, str]:
        # Create a deterministic "synced" output without invoking external tools.
        output_subtitle_path.write_text("SYNCED\n", encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(
        downloader_worker, "_run_ffsubsync", fake_run_ffsubsync, raising=True
    )
    monkeypatch.setattr(
        downloader_worker.settings, "subtitle_sync_enabled", sync_enabled, raising=False
    )
    monkeypatch.setattr(
        downloader_worker.settings,
        "subtitle_sync_keep_unsynced_copy",
        keep_unsynced_copy,
        raising=False,
    )
    monkeypatch.setattr(
        downloader_worker.settings,
        "subtitle_sync_timeout_seconds",
        1,
        raising=False,
    )

    final_path, metadata = await downloader_worker.sync_subtitle_to_audio_if_enabled(
        video_url=str(video_path),
        downloaded_subtitle_path=subtitle_path,
    )

    assert final_path == subtitle_path
    assert metadata["sync_applied"] is expect_sync_applied

    unsynced_path = tmp_path / "video.en.unsynced.srt"
    assert unsynced_path.exists() is expect_unsynced_exists

    if not sync_enabled:
        assert subtitle_path.read_text(encoding="utf-8") == "ORIGINAL\n"
        assert metadata.get("unsynced_subtitle_path") is None
        assert metadata.get("sync_error") is None
    else:
        assert subtitle_path.read_text(encoding="utf-8") == "SYNCED\n"
        if keep_unsynced_copy:
            assert unsynced_path.read_text(encoding="utf-8") == "ORIGINAL\n"
            assert metadata.get("unsynced_subtitle_path") == str(unsynced_path)
        else:
            assert metadata.get("unsynced_subtitle_path") is None


@pytest.mark.asyncio
async def test_sync_subtitle_to_audio_if_enabled_skips_when_video_path_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subtitle_path = tmp_path / "video.en.srt"
    subtitle_path.write_text("ORIGINAL\n", encoding="utf-8")

    monkeypatch.setattr(
        downloader_worker.settings, "subtitle_sync_enabled", True, raising=False
    )

    final_path, metadata = await downloader_worker.sync_subtitle_to_audio_if_enabled(
        video_url=str(tmp_path / "does-not-exist.mkv"),
        downloaded_subtitle_path=subtitle_path,
    )

    assert final_path == subtitle_path
    assert metadata["sync_applied"] is False
    assert "video_url is not a local readable file path" in metadata.get("sync_error", "")
    assert subtitle_path.read_text(encoding="utf-8") == "ORIGINAL\n"
    assert not (tmp_path / "video.en.unsynced.srt").exists()


@pytest.mark.asyncio
async def test_sync_subtitle_to_audio_if_enabled_rolls_back_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video_path = tmp_path / "video.mkv"
    video_path.write_bytes(b"\x00")

    subtitle_path = tmp_path / "video.en.srt"
    subtitle_path.write_text("ORIGINAL\n", encoding="utf-8")

    async def fake_run_ffsubsync_failure(
        *,
        video_path: Path,
        input_subtitle_path: Path,
        output_subtitle_path: Path,
        timeout_seconds: int,
    ) -> Tuple[int, str, str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        downloader_worker,
        "_run_ffsubsync",
        fake_run_ffsubsync_failure,
        raising=True,
    )
    monkeypatch.setattr(
        downloader_worker.settings, "subtitle_sync_enabled", True, raising=False
    )

    final_path, metadata = await downloader_worker.sync_subtitle_to_audio_if_enabled(
        video_url=str(video_path),
        downloaded_subtitle_path=subtitle_path,
    )

    assert final_path == subtitle_path
    assert metadata["sync_applied"] is False
    assert metadata.get("sync_error") == "boom"

    # Original subtitle should be restored as the standard output.
    assert subtitle_path.read_text(encoding="utf-8") == "ORIGINAL\n"
    # The unsynced file should have been moved back during rollback.
    assert not (tmp_path / "video.en.unsynced.srt").exists()


