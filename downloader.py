"""
downloader.py
-------------
Responsible for downloading binary assets (card images) from a URL.

Responsibilities:
- Stream large files to disk (avoid loading entire image into memory).
- Retry on transient failures (network blip, 5xx).
- Validate that the downloaded file is actually an image.
- Compute a deterministic, collision-free filename.

Non-responsibilities:
- It does NOT parse HTML. The parser hands it a URL.
- It does NOT decide WHERE images live on disk — config does.
"""

import logging
import hashlib
from pathlib import Path
from typing import Optional

import requests

from config import settings


logger = logging.getLogger(__name__)


class ImageDownloader:
    """Downloads card images and stores them on disk."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", settings.REQUEST_USER_AGENT)
        self.target_dir: Path = settings.IMAGES_RAW_DIR

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def download(self, url: str, filename_hint: str) -> Optional[Path]:
        """Download an image and return its local path, or None on failure."""
        # TODO (next sprint): implement streaming + retry + validation.
        logger.debug("Placeholder: would download %s", url)
        return None

    # ------------------------------------------------------------------ #
    # Helpers (placeholders)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_filename(hint: str, url: str) -> str:
        """Build a stable filename from a hint + url hash."""
        ext = Path(url).suffix or ".png"
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
        return f"{hint}_{digest}{ext}"
