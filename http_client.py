"""
http_client.py
--------------
Reusable HTTP client built on top of the `requests` library.

Responsibilities:
- Maintain a single `requests.Session` (connection pooling, shared headers).
- Fetch a webpage by URL and return the HTML as text.
- Apply a realistic User-Agent and reasonable defaults.
- Translate low-level network/HTTP failures into a small set of typed
  exceptions so callers can react meaningfully.

Non-responsibilities (intentionally out of scope for Sprint 3.1):
- HTML parsing (no BeautifulSoup, no lxml).
- Persistence (no SQLite, no file I/O beyond what callers request).
- Image downloading (lives in downloader.py).
- Retries / rate limiting (will live on this class in a later sprint).

Defaults come from config.py but every parameter is overridable so
unit tests can run without touching the network.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from config import settings


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class HttpClientError(Exception):
    """Base class for all HTTP client errors."""


class HttpRequestError(HttpClientError):
    """Connection failed, DNS failed, timeout, TLS error, etc.

    These are typically transient and may be worth retrying.
    """


class HttpResponseError(HttpClientError):
    """The server responded, but with a non-success status code.

    By default 4xx and 5xx are both raised. Callers can opt out of
    raising on 4xx if they need to inspect error pages.
    """


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class HttpClient:
    """Thin, reusable HTTP client for fetching HTML pages."""

    DEFAULT_HEADERS: dict[str, str] = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(
        self,
        *,
        user_agent: Optional[str] = None,
        timeout: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout: float = float(timeout if timeout is not None else settings.REQUEST_TIMEOUT_SECONDS)
        self.user_agent: str = user_agent or settings.REQUEST_USER_AGENT

        self._session: requests.Session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", self.user_agent)
        for header, value in self.DEFAULT_HEADERS.items():
            self._session.headers.setdefault(header, value)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get(self, url: str, *, timeout: Optional[float] = None) -> str:
        """Fetch a URL and return the response body as text.

        Raises:
            HttpRequestError:   connection / timeout / TLS failures.
            HttpResponseError:  HTTP status >= 400.
        """
        effective_timeout = float(timeout) if timeout is not None else self.timeout
        logger.info("HTTP request started: GET %s (timeout=%.1fs)", url, effective_timeout)

        try:
            response = self._session.get(url, timeout=effective_timeout)
        except requests.exceptions.Timeout as exc:
            logger.error("HTTP timeout after %.1fs: %s", effective_timeout, url)
            raise HttpRequestError(f"Timeout after {effective_timeout}s: {url}") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("HTTP connection error: %s", url)
            raise HttpRequestError(f"Connection error: {url}") from exc
        except requests.exceptions.SSLError as exc:
            logger.error("HTTP TLS error: %s", url)
            raise HttpRequestError(f"TLS error: {url}") from exc
        except requests.exceptions.RequestException as exc:
            # Catch-all for any other requests-layer failure.
            logger.error("HTTP request failed: %s", url)
            raise HttpRequestError(f"Request failed: {url}") from exc

        status = response.status_code
        size = len(response.content)
        logger.info("HTTP response: %s -> %d (%d bytes)", url, status, size)

        if status >= 400:
            raise HttpResponseError(
                f"HTTP {status} for {url} ({size} bytes)"
            )

        # response.text decodes using the charset the server declared
        # (or chardet fallback). errors="replace" is defensive — bad
        # bytes should never abort a fetch.
        return response.text

    def close(self) -> None:
        """Release the underlying connection pool."""
        self._session.close()
