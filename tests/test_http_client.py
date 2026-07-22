"""
tests/test_http_client.py
-------------------------
Unit tests for HttpClient. We mock the requests.Session so no real
network is touched during CI.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
import requests

from http_client import (
    HttpClient,
    HttpClientError,
    HttpRequestError,
    HttpResponseError,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _mock_response(
    *,
    status_code: int = 200,
    text: str = "<html>hello</html>",
    content: bytes | None = None,
) -> MagicMock:
    """Build a MagicMock that quacks like a requests.Response.

    Note: status_code / text / content are set as real values (not MagicMock
    attributes) so `>=` comparisons and `len()` work as in production.
    """
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = content if content is not None else text.encode("utf-8")
    return resp


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
class TestGet:
    def test_returns_html_text(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response(text="<html>ok</html>")

        client = HttpClient(session=session)
        body = client.get("https://example.com/cards")

        assert body == "<html>ok</html>"
        session.get.assert_called_once()

    def test_uses_provided_timeout(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response()

        HttpClient(session=session).get("https://example.com", timeout=5.0)

        _, kwargs = session.get.call_args
        assert kwargs["timeout"] == 5.0

    def test_uses_default_timeout_from_config(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response()

        HttpClient(session=session).get("https://example.com")

        _, kwargs = session.get.call_args
        assert kwargs["timeout"] > 0

    def test_sets_user_agent_header(self) -> None:
        session = MagicMock()
        # Use a real dict so we can actually inspect what got set.
        session.headers = {}
        session.get.return_value = _mock_response()

        client = HttpClient(user_agent="TestAgent/1.0", session=session)
        client.get("https://example.com")

        # setdefault in __init__ should have stored the UA on the session.
        assert session.headers["User-Agent"] == "TestAgent/1.0"

    def test_passes_url_to_session(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response()

        HttpClient(session=session).get("https://example.com/foo")

        args, _ = session.get.call_args
        assert args[0] == "https://example.com/foo"


# --------------------------------------------------------------------------- #
# Error mapping
# --------------------------------------------------------------------------- #
class TestErrorMapping:
    def test_timeout_becomes_httprequesterror(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = requests.exceptions.Timeout()

        with pytest.raises(HttpRequestError):
            HttpClient(session=session).get("https://example.com")

    def test_connection_error_becomes_httprequesterror(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(HttpRequestError):
            HttpClient(session=session).get("https://example.com")

    def test_ssl_error_becomes_httprequesterror(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = requests.exceptions.SSLError()

        with pytest.raises(HttpRequestError):
            HttpClient(session=session).get("https://example.com")

    def test_generic_request_exception_becomes_httprequesterror(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = requests.exceptions.RequestException()

        with pytest.raises(HttpRequestError):
            HttpClient(session=session).get("https://example.com")

    def test_500_becomes_httpresponseerror(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response(status_code=500)

        with pytest.raises(HttpResponseError):
            HttpClient(session=session).get("https://example.com")

    def test_404_becomes_httpresponseerror(self) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response(status_code=404)

        with pytest.raises(HttpResponseError):
            HttpClient(session=session).get("https://example.com")

    def test_all_http_errors_subclass_base(self) -> None:
        assert issubclass(HttpRequestError, HttpClientError)
        assert issubclass(HttpResponseError, HttpClientError)


# --------------------------------------------------------------------------- #
# Structured logging
# --------------------------------------------------------------------------- #
class TestLogging:
    def test_logs_request_started_and_status(self, caplog: pytest.LogCaptureFixture) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response(
            status_code=200,
            text="<html>x</html>",
        )

        with caplog.at_level(logging.INFO, logger="http_client"):
            HttpClient(session=session).get("https://example.com/page")

        joined = " ".join(caplog.messages)
        assert "HTTP request started" in joined
        assert "GET https://example.com/page" in joined
        assert "HTTP response" in joined
        assert "200" in joined
        # Size must be logged.
        assert "bytes" in joined

    def test_logs_error_on_timeout(self, caplog: pytest.LogCaptureFixture) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = requests.exceptions.Timeout()

        with caplog.at_level(logging.ERROR, logger="http_client"):
            with pytest.raises(HttpRequestError):
                HttpClient(session=session).get("https://example.com")

        joined = " ".join(caplog.messages)
        assert "timeout" in joined.lower()

    def test_logs_error_on_5xx(self, caplog: pytest.LogCaptureFixture) -> None:
        session = MagicMock()
        session.headers = {}
        session.get.return_value = _mock_response(status_code=503)

        with caplog.at_level(logging.INFO, logger="http_client"):
            with pytest.raises(HttpResponseError):
                HttpClient(session=session).get("https://example.com")

        joined = " ".join(caplog.messages)
        assert "HTTP response" in joined
        assert "503" in joined
