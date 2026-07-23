"""
tests/test_hdfc_parser.py
-------------------------
Tests for the HDFC listing-page parser (Sprint 3.2).

The primary fixture is the real saved HDFC page at
logs/debug/hdfc_cards.html. Tests that need synthetic HTML use
small inline strings so failures point at the parser, not the
fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Path bootstrap so the tests can be run from the repo root or
# from inside the tests/ directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parsers.hdfc import CARD_LINK_SELECTOR, parse_listing  # noqa: E402


SAVED_HTML_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "hdfc_cards.html"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def saved_html() -> str:
    """Read the real saved HDFC listing page. Skip if absent."""
    if not SAVED_HTML_PATH.is_file():
        pytest.skip(
            f"Saved HDFC HTML not found at {SAVED_HTML_PATH}. "
            "Run: python scripts/test_http_client.py"
        )
    return SAVED_HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def one_card_html() -> str:
    """Minimal HTML containing a single valid card teaser."""
    return """
    <html><body>
      <a class="cmp-teaser__action-link btn btn-secondary"
         href="/credit-cards" title="View Credit Cards">View Credit Cards</a>
    </body></html>
    """


# --------------------------------------------------------------------------- #
# Real saved page
# --------------------------------------------------------------------------- #
class TestParseListingAgainstSavedPage:
    """End-to-end checks against the real saved HDFC page."""

    def test_returns_non_empty_list(self, saved_html: str) -> None:
        result = parse_listing(saved_html)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_each_entry_has_only_expected_keys(self, saved_html: str) -> None:
        result = parse_listing(saved_html)
        for entry in result:
            assert set(entry.keys()) == {"card_name", "card_url"}

    def test_values_are_non_empty_strings(self, saved_html: str) -> None:
        result = parse_listing(saved_html)
        for entry in result:
            assert isinstance(entry["card_name"], str)
            assert isinstance(entry["card_url"], str)
            assert entry["card_name"].strip() != ""
            assert entry["card_url"].strip() != ""

    def test_returns_seven_category_cards(self, saved_html: str) -> None:
        """The saved page contains exactly 7 card category teasers."""
        result = parse_listing(saved_html)
        assert len(result) == 7

    def test_known_cards_present_by_title(self, saved_html: str) -> None:
        """Names below are observed in the saved HTML; not invented."""
        result = parse_listing(saved_html)
        names = [entry["card_name"] for entry in result]
        expected_subset = [
            "View Credit Cards",
            "View Debit Cards",
            "View Millennia Cards",
            "View Prepaid Cards",
            "View Forex Cards",
        ]
        for expected in expected_subset:
            assert expected in names, f"Missing expected card: {expected}"

    def test_known_card_urls_present(self, saved_html: str) -> None:
        """URLs are kept verbatim (relative) per the sprint decision."""
        result = parse_listing(saved_html)
        urls = [entry["card_url"] for entry in result]
        for url in (
            "/credit-cards",
            "/debit-cards",
            "/prepaid-cards",
            "/business-credit-cards",
        ):
            assert url in urls, f"Missing expected URL: {url}"

    def test_urls_are_relative_and_unchanged(self, saved_html: str) -> None:
        """Sprint decision: do not absolutize; return href as-is."""
        result = parse_listing(saved_html)
        for entry in result:
            assert entry["card_url"].startswith("/"), (
                f"Expected relative URL, got: {entry['card_url']!r}"
            )

    def test_view_prefix_is_preserved(self, saved_html: str) -> None:
        """Sprint decision: parser is extraction-only; no normalization."""
        result = parse_listing(saved_html)
        for entry in result:
            assert entry["card_name"].startswith("View "), (
                f"Expected raw 'View ...' title, got: {entry['card_name']!r}"
            )

    def test_urls_are_unique(self, saved_html: str) -> None:
        result = parse_listing(saved_html)
        urls = [entry["card_url"] for entry in result]
        assert len(urls) == len(set(urls))

    def test_preserves_document_order(self, saved_html: str) -> None:
        """First card on the page is Credit Cards (per HTML inspection)."""
        result = parse_listing(saved_html)
        assert result[0]["card_name"] == "View Credit Cards"
        assert result[0]["card_url"] == "/credit-cards"


# --------------------------------------------------------------------------- #
# Synthetic edge cases
# --------------------------------------------------------------------------- #
class TestParseListingEdgeCases:
    def test_empty_html_returns_empty_list(self) -> None:
        assert parse_listing("") == []

    def test_unrelated_html_returns_empty_list(self) -> None:
        html = "<html><body><h1>Nothing here</h1><p>Some text.</p></body></html>"
        assert parse_listing(html) == []

    def test_single_card(self, one_card_html: str) -> None:
        assert parse_listing(one_card_html) == [
            {"card_name": "View Credit Cards", "card_url": "/credit-cards"}
        ]

    def test_skips_anchors_without_title(self) -> None:
        html = """
        <html><body>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/no-title">no title</a>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/with-title" title="View With Title">View With Title</a>
        </body></html>
        """
        assert parse_listing(html) == [
            {"card_name": "View With Title", "card_url": "/with-title"}
        ]

    def test_skips_anchors_without_href(self) -> None:
        html = """
        <html><body>
          <a class="cmp-teaser__action-link btn btn-secondary"
             title="No Href Here">No Href Here</a>
        </body></html>
        """
        assert parse_listing(html) == []

    def test_deduplicates_by_url_preserving_order(self) -> None:
        html = """
        <html><body>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/credit-cards" title="View Credit Cards">A</a>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/debit-cards" title="View Debit Cards">B</a>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/credit-cards" title="View Credit Cards (dup)">C</a>
        </body></html>
        """
        result = parse_listing(html)
        assert result == [
            {"card_name": "View Credit Cards", "card_url": "/credit-cards"},
            {"card_name": "View Debit Cards", "card_url": "/debit-cards"},
        ]

    def test_ignores_anchors_missing_btn_secondary_class(self) -> None:
        """`cmp-teaser__action-link` alone matches "Read More" expanders
        (with href="#") which must be excluded."""
        html = """
        <html><body>
          <a class="cmp-teaser__action-link" href="#"
             title="Read More">Read More</a>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/credit-cards" title="View Credit Cards">View Credit Cards</a>
        </body></html>
        """
        result = parse_listing(html)
        assert result == [
            {"card_name": "View Credit Cards", "card_url": "/credit-cards"}
        ]

    def test_ignores_unrelated_anchors(self) -> None:
        html = """
        <html><body>
          <a href="/">Home</a>
          <a class="leftulLink" href="/credit-cards" title="Wrong Class">X</a>
          <a class="cmp-teaser__action-link btn btn-secondary"
             href="/credit-cards" title="View Credit Cards">View Credit Cards</a>
        </body></html>
        """
        assert parse_listing(html) == [
            {"card_name": "View Credit Cards", "card_url": "/credit-cards"}
        ]


# --------------------------------------------------------------------------- #
# Selector sanity
# --------------------------------------------------------------------------- #
def test_selector_is_documented_constant() -> None:
    """Selector is exposed so tests and other code can reuse it."""
    assert CARD_LINK_SELECTOR == "a.cmp-teaser__action-link.btn.btn-secondary"
