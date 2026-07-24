"""
tests/test_image_downloader.py
------------------------------
Unit tests for :mod:`image_downloader`.

All HTTP traffic is mocked. The real :class:`HttpClient` is wired up
with a fake ``requests.Session`` (same pattern used in
``tests/test_http_client.py``) so we exercise the real error-mapping
path without touching the network.

Coverage
========

* Successful download
* Existing file is skipped
* Timeout  ->  ``None`` returned
* HTTP 4xx/5xx  ->  ``None`` returned
* Empty / non-image response body  ->  ``None`` returned
* Empty / whitespace URL  ->  ``None`` returned
* Invalid scheme / malformed URL  ->  ``None`` returned
* Target path is computed correctly (extension from URL, fallback to
  ``.webp``, slug sanitisation)
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from http_client import HttpClient
from image_downloader import (
    DEFAULT_EXTENSION,
    ImageDownloader,
    _extension_from_url,
    _looks_like_image,
    _safe_slug,
)


# --------------------------------------------------------------------------- #
# Test fixtures
# --------------------------------------------------------------------------- #
# A real WebP header so the magic-byte sniff is satisfied. The payload
# is short but >= MIN_IMAGE_BYTES (256).
WEBP_BYTES: bytes = (
    b"RIFF" b"\x24\x00\x00\x00" b"WEBPVP8 "
    b"\x18\x00\x00\x00" b"\x30\x01\x00\x9d"
    + b"\x00" * 300
)


def _mock_response(
    *,
    status_code: int = 200,
    content: bytes | None = None,
) -> MagicMock:
    """Build a MagicMock that quacks like a ``requests.Response``."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    if content is None:
        content = WEBP_BYTES
    resp.content = content
    return resp


@pytest.fixture()
def fake_session() -> MagicMock:
    """A mock ``requests.Session`` with a real dict for headers."""
    session = MagicMock()
    session.headers = {}
    return session


@pytest.fixture()
def http_client(fake_session: MagicMock) -> HttpClient:
    """A real HttpClient backed by a mock session."""
    return HttpClient(session=fake_session, timeout=10.0)


@pytest.fixture()
def downloader(http_client: HttpClient, tmp_path: Path) -> ImageDownloader:
    """An ImageDownloader writing into a throwaway directory."""
    return ImageDownloader(http_client=http_client, base_dir=tmp_path)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
class TestDownloadSuccess:
    def test_returns_path_to_saved_file(
        self, downloader: ImageDownloader, fake_session: MagicMock,
        tmp_path: Path,
    ) -> None:
        fake_session.get.return_value = _mock_response()

        result = downloader.download(
            "https://cdn.example.com/cards/regalia.png",
            card_slug="regalia-first-credit-card",
            bank_id="hdfc",
        )

        assert result is not None
        assert result.exists()
        assert result.parent == tmp_path / "hdfc"
        assert result.read_bytes() == WEBP_BYTES

    def test_filename_uses_card_slug(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()

        result = downloader.download(
            "https://cdn.example.com/x.png",
            card_slug="millennia-credit-card",
        )

        assert result is not None
        assert result.name == "millennia-credit-card.png"

    def test_preserves_png_extension_from_url(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()

        result = downloader.download(
            "https://cdn.example.com/x.png?v=1",
            card_slug="my-card",
        )
        assert result is not None
        assert result.suffix == ".png"

    def test_preserves_jpg_extension(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()
        result = downloader.download(
            "https://cdn.example.com/x.jpg", card_slug="my-card",
        )
        assert result is not None
        assert result.suffix == ".jpg"

    def test_falls_back_to_webp_when_url_has_no_extension(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()
        result = downloader.download(
            "https://s7ap1.scene7.com/is/image/hdfcbankPWS/foo?fmt=webp-alpha",
            card_slug="my-card",
        )
        assert result is not None
        assert result.suffix == ".webp"

    def test_sanitises_unsafe_slug(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()
        result = downloader.download(
            "https://cdn.example.com/x.png",
            card_slug="weird/card?slug:with*chars",
        )
        assert result is not None
        # Only [A-Za-z0-9._-] survive.
        assert result.name == "weird-card-slug-with-chars.png"

    def test_uses_per_downloader_timeout_override(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()
        # Replace the fixture's downloader with one that has a custom timeout.
        d = ImageDownloader(
            http_client=downloader._http,  # type: ignore[attr-defined]
            base_dir=downloader._base_dir,  # type: ignore[attr-defined]
            timeout=7.5,
        )
        d.download("https://cdn.example.com/x.png", card_slug="c1")
        _, kwargs = fake_session.get.call_args
        assert kwargs["timeout"] == 7.5

    def test_creates_target_directory(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()
        # The "hdfc" subdir must not exist yet.
        assert not (downloader._base_dir / "hdfc").exists()  # type: ignore[attr-defined]
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is not None
        assert result.parent.is_dir()

    def test_creates_nested_bank_subdir(
        self, tmp_path: Path, http_client: HttpClient, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response()
        d = ImageDownloader(http_client=http_client, base_dir=tmp_path)
        result = d.download(
            "https://cdn.example.com/x.png",
            card_slug="icici-coral", bank_id="icici",
        )
        assert result is not None
        assert result.parent == tmp_path / "icici"


# --------------------------------------------------------------------------- #
# Skip behaviour
# --------------------------------------------------------------------------- #
class TestSkipWhenPresent:
    def test_returns_none_when_file_exists(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        # Pre-create the file the downloader would have written.
        target = downloader.target_path(
            "regalia-first-credit-card",
            url="https://cdn.example.com/x.png",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"already-here")

        result = downloader.download(
            "https://cdn.example.com/x.png",
            card_slug="regalia-first-credit-card",
        )

        assert result is None
        # The file must not have been touched or overwritten.
        assert target.read_bytes() == b"already-here"
        # And the network must not have been called.
        fake_session.get.assert_not_called()

    def test_skip_is_logged(
        self, downloader: ImageDownloader, fake_session: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        target = downloader.target_path(
            "regalia", url="https://cdn.example.com/x.png",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")

        with caplog.at_level(logging.INFO, logger="image_downloader"):
            downloader.download(
                "https://cdn.example.com/x.png", card_slug="regalia",
            )

        joined = " ".join(caplog.messages)
        assert "skipping" in joined.lower()
        assert "regalia" in joined


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #
class TestTimeout:
    def test_timeout_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.side_effect = requests.exceptions.Timeout()
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None

    def test_timeout_is_logged(
        self, downloader: ImageDownloader, fake_session: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_session.get.side_effect = requests.exceptions.Timeout()
        with caplog.at_level(logging.ERROR, logger="image_downloader"):
            downloader.download(
                "https://cdn.example.com/x.png", card_slug="c1",
            )
        joined = " ".join(caplog.messages)
        assert "failed" in joined.lower()
        assert "timeout" in joined.lower() or "HttpRequestError" in joined


class TestHttpError:
    def test_500_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response(status_code=500)
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None

    def test_404_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response(status_code=404)
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None

    def test_connection_error_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.side_effect = requests.exceptions.ConnectionError()
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None


class TestInvalidContent:
    def test_html_response_body_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        # The server returned 200 but with an HTML error page body.
        fake_session.get.return_value = _mock_response(
            status_code=200,
            content=b"<html><body>Error: card not found</body></html>",
        )
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None

    def test_empty_body_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response(content=b"")
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None

    def test_tiny_body_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        fake_session.get.return_value = _mock_response(content=b"AB")
        result = downloader.download(
            "https://cdn.example.com/x.png", card_slug="c1",
        )
        assert result is None

    def test_invalid_content_is_logged(
        self, downloader: ImageDownloader, fake_session: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_session.get.return_value = _mock_response(
            status_code=200, content=b"not-an-image",
        )
        with caplog.at_level(logging.ERROR, logger="image_downloader"):
            downloader.download(
                "https://cdn.example.com/x.png", card_slug="my-card",
            )
        joined = " ".join(caplog.messages)
        assert "not a valid image" in joined.lower()


class TestEmptyUrl:
    def test_empty_string_url_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        result = downloader.download("", card_slug="c1")
        assert result is None
        fake_session.get.assert_not_called()

    def test_none_url_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        result = downloader.download(None, card_slug="c1")
        assert result is None
        fake_session.get.assert_not_called()

    def test_whitespace_url_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        result = downloader.download("   \t\n  ", card_slug="c1")
        assert result is None
        fake_session.get.assert_not_called()


class TestInvalidUrl:
    def test_non_http_scheme_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        result = downloader.download(
            "ftp://example.com/card.png", card_slug="c1",
        )
        assert result is None
        fake_session.get.assert_not_called()

    def test_javascript_scheme_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        result = downloader.download(
            "javascript:alert(1)", card_slug="c1",
        )
        assert result is None
        fake_session.get.assert_not_called()

    def test_missing_host_returns_none(
        self, downloader: ImageDownloader, fake_session: MagicMock,
    ) -> None:
        result = downloader.download(
            "https:///card.png", card_slug="c1",
        )
        assert result is None
        fake_session.get.assert_not_called()

    def test_invalid_url_is_logged(
        self, downloader: ImageDownloader, fake_session: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.ERROR, logger="image_downloader"):
            downloader.download("not a url", card_slug="my-card")
        joined = " ".join(caplog.messages)
        assert "invalid url" in joined.lower()


# --------------------------------------------------------------------------- #
# Direct unit tests for module-level helpers
# --------------------------------------------------------------------------- #
class TestExtensionFromUrl:
    def test_png(self) -> None:
        assert _extension_from_url("https://x.com/foo.png") == ".png"

    def test_png_with_query(self) -> None:
        assert (
            _extension_from_url("https://x.com/foo.png?fmt=webp-alpha")
            == ".png"
        )

    def test_jpg(self) -> None:
        assert _extension_from_url("https://x.com/foo.jpg") == ".jpg"

    def test_jpeg(self) -> None:
        assert _extension_from_url("https://x.com/foo.jpeg") == ".jpeg"

    def test_webp(self) -> None:
        assert _extension_from_url("https://x.com/foo.webp") == ".webp"

    def test_webp_alpha_query(self) -> None:
        # HDFC's CDN pattern: no extension, fmt=webp-alpha in query.
        assert (
            _extension_from_url(
                "https://s7ap1.scene7.com/is/image/hdfcbankPWS/x?fmt=webp-alpha"
            )
            == ".webp"
        )

    def test_unknown_extension_falls_back_to_default(self) -> None:
        assert _extension_from_url("https://x.com/foo.bmp") == DEFAULT_EXTENSION

    def test_no_path_at_all_falls_back_to_default(self) -> None:
        assert _extension_from_url("https://x.com/") == DEFAULT_EXTENSION

    def test_empty_url_falls_back_to_default(self) -> None:
        assert _extension_from_url("") == DEFAULT_EXTENSION

    def test_none_url_falls_back_to_default(self) -> None:
        assert _extension_from_url(None) == DEFAULT_EXTENSION


class TestSafeSlug:
    def test_passthrough(self) -> None:
        assert _safe_slug("regalia-first-credit-card") == "regalia-first-credit-card"

    def test_replaces_unsafe_chars(self) -> None:
        assert _safe_slug("a/b?c:d*e") == "a-b-c-d-e"

    def test_empty_returns_unknown(self) -> None:
        assert _safe_slug("") == "unknown"
        assert _safe_slug("///") == "unknown"


class TestLooksLikeImage:
    def test_webp(self) -> None:
        assert _looks_like_image(WEBP_BYTES) is True

    def test_png(self) -> None:
        assert _looks_like_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 300) is True

    def test_jpeg(self) -> None:
        assert _looks_like_image(b"\xff\xd8\xff" + b"\x00" * 300) is True

    def test_html_rejected(self) -> None:
        assert _looks_like_image(b"<html><body>oops</body></html>") is False

    def test_empty_rejected(self) -> None:
        assert _looks_like_image(b"") is False

    def test_short_rejected(self) -> None:
        assert _looks_like_image(b"\x89PNG") is False


# --------------------------------------------------------------------------- #
# Target-path computation
# --------------------------------------------------------------------------- #
class TestTargetPath:
    def test_basic(self, downloader: ImageDownloader) -> None:
        p = downloader.target_path(
            "regalia", url="https://x.com/foo.png",
        )
        assert p == downloader._base_dir / "hdfc" / "regalia.png"  # type: ignore[attr-defined]

    def test_default_extension_when_no_url(
        self, downloader: ImageDownloader,
    ) -> None:
        p = downloader.target_path("regalia")
        assert p.suffix == ".webp"
        assert p == downloader._base_dir / "hdfc" / "regalia.webp"  # type: ignore[attr-defined]

    def test_honours_bank_id(self, tmp_path: Path, http_client: HttpClient) -> None:
        d = ImageDownloader(http_client=http_client, base_dir=tmp_path)
        p = d.target_path(
            "icici-coral", url="https://x.com/c.png", bank_id="icici",
        )
        assert p == tmp_path / "icici" / "icici-coral.png"
