"""
image_downloader.py
-------------------
Download official card images to disk.

Responsibilities
================

* Reuse the project's :class:`HttpClient` (Sprint 3.1) so we share its
  session, headers, timeout, and exception mapping.
* Save every image under ``images/raw/<bank_id>/<card_slug>.<ext>``.
* Preserve the URL's extension when one is present (HDFC's CDN serves
  ``?fmt=webp-alpha`` payloads but the request path itself carries
  no extension — we fall back to ``.webp`` in that case to honour the
  brief's "save as ``<card_slug>.webp``" rule).
* Skip downloads whose target file already exists (idempotent re-runs).
* Return the local :class:`pathlib.Path` on success, ``None`` on any
  failure.
* Surface clear, structured log lines for: download started, download
  finished, skipped (already present), and every failure mode.

Non-responsibilities
====================

* Does NOT parse HTML (parsers do that and hand the URL to us).
* Does NOT decide which bank/folder to write to — callers pass
  ``bank_id``.
* Does NOT talk to the database.
* Does NOT do retries. That belongs on a higher layer; this class
  raises typed exceptions so callers can decide.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from http_client import HttpClient, HttpClientError


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Minimum plausible size of a real image. Anything below this is treated
# as a non-image response (e.g. an HTML error page served with a 200).
MIN_IMAGE_BYTES: int = 256

# Default extension when the URL has no recognisable file extension.
# HDFC's CDN URLs end with a query string like ``?fmt=webp-alpha`` and
# the brief asks us to save images as ``<slug>.webp``.
DEFAULT_EXTENSION: str = ".webp"

# Recognised image extensions (lowercased, including the leading dot).
_KNOWN_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".avif"}
)

# Magic-byte signatures used for cheap "is this really an image?" checks.
# The signatures are checked against the first bytes of the response body.
_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x1f\x80", "webp"),  # RIFF....WEBP — we only check the RIFF marker
    (b"RIFF", "webp"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"<?xml", "svg"),
    (b"<svg", "svg"),
)

# Used to sanity-check that a filename component contains only safe chars.
_SLUG_CLEAN_RE: re.Pattern[str] = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class ImageDownloadError(Exception):
    """Base class for image-downloader errors."""


class InvalidImageUrlError(ImageDownloadError):
    """The URL is empty, malformed, or not an http(s) URL."""


class InvalidImageContentError(ImageDownloadError):
    """The response body is empty or does not look like an image."""


# --------------------------------------------------------------------------- #
# Downloader
# --------------------------------------------------------------------------- #
class ImageDownloader:
    """Download official card images to ``images/raw/<bank_id>/``.

    Args:
        http_client:  An :class:`HttpClient` to reuse. If omitted, a
            new one is constructed from the project defaults.
        base_dir:     Root directory under which ``<bank_id>/`` is
            created. Defaults to ``config.settings.IMAGES_RAW_DIR``.
        timeout:      Optional per-request timeout override. When set,
            overrides the HttpClient's default for binary fetches.
    """

    def __init__(
        self,
        http_client: Optional[HttpClient] = None,
        base_dir: Optional[Path] = None,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        # Imported lazily to avoid a hard dependency at module import
        # time (config pulls os.getenv which is fine, but keeping the
        # import local makes the module easier to test in isolation).
        if base_dir is None:
            from config import settings

            base_dir = settings.IMAGES_RAW_DIR

        self._http: HttpClient = http_client or HttpClient()
        self._owns_http: bool = http_client is None
        self._base_dir: Path = Path(base_dir)
        self._timeout: Optional[float] = timeout

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def download(
        self,
        url: Optional[str],
        card_slug: str,
        bank_id: str = "hdfc",
    ) -> Optional[Path]:
        """Download ``url`` to ``images/raw/<bank_id>/<card_slug>.<ext>``.

        Args:
            url:        The image URL. ``None``/empty is treated as a
                        validation failure and returns ``None``.
            card_slug:  The card's slug; becomes the filename stem.
            bank_id:    The bank identifier; becomes the sub-folder.

        Returns:
            The local :class:`Path` of the saved file, or ``None`` if
            the download was skipped (file already present) *and* the
            caller wants to distinguish. ``None`` is also returned for
            every failure mode.

        Note:
            The brief asks "return the local saved path after download".
            To remain consistent with the existing
            ``ImageDownloader.download`` signature (which uses ``None``
            to signal "not downloaded"), this method returns the path
            on success and ``None`` on either failure OR skip. Callers
            that need to tell those two apart can use :meth:`exists`
            on the returned target, or pre-check with
            :meth:`target_path`.
        """
        target = self.target_path(card_slug, url=url, bank_id=bank_id)

        # --- Validate URL ------------------------------------------------
        try:
            self._validate_url(url)
        except InvalidImageUrlError as exc:
            logger.error(
                "Image download rejected: invalid URL for %s (%s): %r",
                card_slug, bank_id, url,
            )
            logger.debug("Reason: %s", exc)
            return None

        assert url is not None  # for type-checkers; validated above

        # --- Skip if already on disk ------------------------------------
        if target.exists():
            logger.info(
                "Image already present, skipping: %s -> %s", url, target,
            )
            return None

        # --- Fetch -------------------------------------------------------
        try:
            content = self._http.get_bytes(url, timeout=self._timeout)
        except HttpClientError as exc:
            logger.error(
                "Image download failed (%s) for %s: %s",
                type(exc).__name__, card_slug, exc,
            )
            return None

        # --- Validate that the body is actually an image -----------------
        if not _looks_like_image(content):
            logger.error(
                "Image download failed: response is not a valid image "
                "for %s (%d bytes): %s",
                card_slug, len(content), url,
            )
            return None

        # --- Persist -----------------------------------------------------
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        except OSError as exc:
            logger.error(
                "Image write failed for %s at %s: %s",
                card_slug, target, exc,
            )
            return None

        logger.info(
            "Image downloaded: %s -> %s (%d bytes)",
            url, target, len(content),
        )
        return target

    def target_path(
        self,
        card_slug: str,
        *,
        url: Optional[str] = None,
        bank_id: str = "hdfc",
    ) -> Path:
        """Return the on-disk path an image would be saved to.

        Provided so tests and call sites can introspect the destination
        without doing a download. When ``url`` is given, the extension
        is derived from it; otherwise the default ``.webp`` is used.
        """
        ext = _extension_from_url(url) if url else DEFAULT_EXTENSION
        return self._base_dir / bank_id / f"{_safe_slug(card_slug)}{ext}"

    def close(self) -> None:
        """Release the underlying HTTP client if we own it."""
        if self._owns_http:
            self._http.close()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_url(url: Optional[str]) -> None:
        """Raise :class:`InvalidImageUrlError` for missing/malformed URLs.

        An empty string, ``None``, a non-string, or any URL that does
        not use the ``http`` or ``https`` scheme is rejected. The
        hostname portion is also required to contain a dot (so we
        reject things like ``http://localhost-only`` style junk that
        could in theory be valid but is almost always a bug here).
        """
        if not isinstance(url, str) or not url.strip():
            raise InvalidImageUrlError("URL is empty")
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise InvalidImageUrlError(f"URL scheme is not http(s): {parsed.scheme!r}")
        if not parsed.netloc:
            raise InvalidImageUrlError("URL has no host")
        if "." not in parsed.netloc:
            raise InvalidImageUrlError(f"URL host looks invalid: {parsed.netloc!r}")


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #
def _extension_from_url(url: Optional[str]) -> str:
    """Return the file extension to use for ``url``, defaulting to ``.webp``.

    Looks at the URL's path component first (e.g.
    ``.../foo.png?fmt=webp-alpha`` -> ``.png``). Falls back to the
    query string's ``fmt=`` parameter, which is how HDFC's CDN signals
    ``webp-alpha``. Finally falls back to :data:`DEFAULT_EXTENSION`.
    """
    if not url:
        return DEFAULT_EXTENSION

    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in _KNOWN_IMAGE_EXTENSIONS:
        return suffix

    # ``?fmt=webp-alpha`` -> ".webp"
    fmt_match = re.search(r"[?&]fmt=([a-z0-9]+)", url, re.IGNORECASE)
    if fmt_match:
        fmt = fmt_match.group(1).lower()
        # Strip the "-alpha" / "-lossless" HDFC suffixes.
        fmt = fmt.split("-", 1)[0]
        if f".{fmt}" in _KNOWN_IMAGE_EXTENSIONS:
            return f".{fmt}"

    return DEFAULT_EXTENSION


def _safe_slug(slug: str) -> str:
    """Return a filename-safe version of ``slug``.

    Falls back to ``"unknown"`` if the slug is empty after sanitisation.
    """
    if not slug:
        return "unknown"
    cleaned = _SLUG_CLEAN_RE.sub("-", slug).strip("-")
    return cleaned or "unknown"


def _looks_like_image(content: bytes) -> bool:
    """Cheap content-type sniff using magic bytes.

    Returns ``False`` for empty payloads or anything that doesn't match
    a known image signature. A 200 OK HTML page (e.g. an error page
    served with status 200) is correctly rejected.
    """
    if not content or len(content) < MIN_IMAGE_BYTES:
        return False
    head = content[:16]
    for signature, _name in _IMAGE_SIGNATURES:
        if head.startswith(signature):
            return True
    return False
