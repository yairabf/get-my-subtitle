"""Tests for downloader language-code expansion helpers."""

from __future__ import annotations

import pytest

from downloader import worker as downloader_worker


@pytest.mark.parametrize(
    "languages,expected",
    [
        (None, None),
        ([], []),
        (["en"], ["en"]),
        (["he"], ["he", "heb"]),
        (["heb"], ["he", "heb"]),
        (["HE"], ["he", "heb"]),
        (["HeB"], ["he", "heb"]),
        (["en", "he"], ["en", "he", "heb"]),
        (["he", "en"], ["he", "heb", "en"]),
        (["he", "heb"], ["he", "heb"]),
    ],
)
def test_expand_hebrew_language_codes(languages, expected) -> None:
    assert downloader_worker._expand_hebrew_language_codes(languages) == expected


