"""
tests/test_hdfc_card_parser.py
-----------------------------
Unit tests for ``parsers.hdfc_card.parse_card``.

These tests follow the project's existing pattern (see
``tests/test_hdfc_credit_cards_parser.py``):

* The real downloaded HTML at ``logs/debug/millennia_credit_card.html``
  is the primary fixture.
* Synthetic HTML is used only for the "empty" / "unrelated" negative
  cases.
* Tests do not mock BeautifulSoup; they exercise the parser end-to-end.

The downloaded page is actually HDFC's Regalia First page (HDFC aliases
the millennia URL). The parser must extract Regalia First — never
"Millennia" — because the detail page is the source of truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from models import CardRecord
from parsers.hdfc_card import (
    BANK_ID,
    CARD_TYPE,
    SELECTOR_CANONICAL,
    SELECTOR_DESCRIPTION_META,
    SELECTOR_H1,
    SELECTOR_HERO_IMAGE,
    _extract_apply_url,
    _extract_card_name,
    _extract_canonical_url,
    _extract_description,
    _extract_faq,
    _extract_fees,
    _extract_image_url,
    _iter_jsonld,
    _slug_from_url,
    parse_card,
)


HTML_FILE = Path("logs/debug/millennia_credit_card.html")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def real_html() -> str:
    """The real HDFC detail page saved in Sprint 3.4."""
    if not HTML_FILE.exists():
        pytest.skip(f"Missing HTML fixture: {HTML_FILE}")
    return HTML_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def record(real_html: str) -> CardRecord:
    """A CardRecord produced by parsing the real HTML."""
    return parse_card(real_html)


# --------------------------------------------------------------------------- #
# Smoke / shape tests
# --------------------------------------------------------------------------- #

def test_returns_card_record(record: CardRecord) -> None:
    assert isinstance(record, CardRecord)


def test_bank_id_is_hdfc(record: CardRecord) -> None:
    assert record.bank_id == BANK_ID == "hdfc"


def test_card_type_is_credit(record: CardRecord) -> None:
    assert record.card_type == CARD_TYPE == "credit"


# --------------------------------------------------------------------------- #
# Field-by-field tests
# --------------------------------------------------------------------------- #

def test_card_name_is_regalia_first_not_millennia(record: CardRecord) -> None:
    """The page is the Regalia First page (HDFC aliases the URL).

    The listing-page name said "Millennia", but the detail page is the
    source of truth and must win. The parser must never trust the
    listing-page name.
    """
    assert record.card_name == "Regalia First Credit Card"
    assert "millennia" not in record.card_name.lower()


def test_canonical_url_extracted(record: CardRecord) -> None:
    assert record.source_url is not None
    assert record.source_url == (
        "https://www.hdfc.bank.in/credit-cards/regalia-first-credit-card"
    )


def test_card_slug_from_canonical_url(record: CardRecord) -> None:
    assert record.card_slug == "regalia-first-credit-card"


def test_description_extracted(record: CardRecord) -> None:
    assert "description" in record.extra
    desc = record.extra["description"]
    assert isinstance(desc, str)
    assert "Regalia First Credit Card" in desc
    assert len(desc) > 40


def test_image_url_extracted(record: CardRecord) -> None:
    assert record.image_url is not None
    assert record.image_url.startswith("https://")
    assert "regalia-first" in record.image_url
    # The lazy-loaded data-src, not the generic preview placeholder.
    assert "preview-img" not in record.image_url


def test_image_url_is_lazy_loaded_data_src(record: CardRecord) -> None:
    """The hero <img> uses a generic preview src; only data-src is real."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(HTML_FILE.read_text(encoding="utf-8"), "html.parser")
    hero = soup.select_one(SELECTOR_HERO_IMAGE)
    assert hero is not None
    assert (hero.get("src") or "").endswith("preview-img.png")
    assert "regalia-first" in (hero.get("data-src") or "")


def test_apply_url_is_none_when_hero_apply_anchor_has_empty_href(
    record: CardRecord,
) -> None:
    """On this card new applications are paused; the apply anchor's
    href is empty, so apply_url must be None (not "")."""
    assert record.extra.get("apply_url") is None


def test_joining_fee_extracted(record: CardRecord) -> None:
    assert record.fees.get("joining") == 1000


def test_annual_fee_extracted(record: CardRecord) -> None:
    assert record.fees.get("annual") == 1000


def test_annual_percentage_rate_extracted_from_jsonld(
    record: CardRecord,
) -> None:
    apr = record.fees.get("annual_percentage_rate")
    assert apr is not None
    assert "23.88" in apr
    assert "%" in apr


def test_faq_parsed(record: CardRecord) -> None:
    faq = record.extra.get("faq")
    assert isinstance(faq, list)
    assert len(faq) >= 5
    for item in faq:
        assert set(item.keys()) == {"question", "answer"}
        assert item["question"]
        assert item["answer"]
    # Specific Q/A from the real page.
    questions = " ".join(item["question"] for item in faq)
    assert "Regalia First Credit Card" in questions


def test_breadcrumb_parsed(record: CardRecord) -> None:
    bc = record.extra.get("breadcrumb")
    assert isinstance(bc, list)
    assert len(bc) >= 3
    for item in bc:
        assert set(item.keys()) == {"name", "url"}
        assert item["name"]
        assert item["url"].startswith("https://")
    # First crumb is always "Home".
    assert bc[0]["name"] == "Home"
    # Last crumb is the card itself.
    assert "regalia-first" in bc[-1]["url"]


# --------------------------------------------------------------------------- #
# Negative / defensive tests
# --------------------------------------------------------------------------- #

def test_empty_html_returns_empty_card_record() -> None:
    rec = parse_card("")
    assert isinstance(rec, CardRecord)
    assert rec.card_name == ""
    assert rec.card_slug == "unknown"
    assert rec.source_url is None
    assert rec.image_url is None
    assert rec.fees == {}
    assert rec.extra == {}


def test_unrelated_html_returns_empty_card_record() -> None:
    html = (
        "<!doctype html><html><head><title>Hello</title>"
        "<meta name='description' content='A random page.'>"
        "</head><body><h1>Hello world</h1>"
        "<p>Nothing to do with credit cards.</p></body></html>"
    )
    rec = parse_card(html)
    assert isinstance(rec, CardRecord)
    assert rec.card_name == "Hello world"
    # No canonical -> slug fallback.
    assert rec.card_slug == "unknown"
    assert rec.source_url is None
    # No hero image, no apply anchor, no JSON-LD.
    assert rec.image_url is None
    assert rec.extra.get("apply_url") is None
    assert rec.extra.get("faq") is None
    assert rec.extra.get("breadcrumb") is None
    assert rec.fees == {}


def test_minimal_card_html_extracts_everything() -> None:
    """A hand-rolled minimal page that has every supported field.

    This is a regression guard: if any selector changes, this test must
    be updated alongside the parser, and the real-HTML tests still act
    as the source of truth.
    """
    html = f"""
    <html>
      <head>
        <link rel="canonical" href="https://www.hdfc.bank.in/credit-cards/millennia-credit-card">
        <meta name="description" content="Millennia Credit Card description.">
        <script type="application/ld+json">
          {{
            "@context": "https://schema.org",
            "@type": "CreditCard",
            "name": "Millennia Credit Card",
            "annualPercentageRate": "23.88% to 43.2%*"
          }}
        </script>
        <script type="application/ld+json">
          {{
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
              {{"@type": "Question", "name": "What is Millennia?",
                "acceptedAnswer": {{"@type": "Answer",
                                    "text": "A rewards credit card."}}}}
            ]
          }}
        </script>
        <script type="application/ld+json">
          {{
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
              {{"@type": "ListItem", "position": 1, "name": "Home",
                "item": "https://www.hdfc.bank.in"}},
              {{"@type": "ListItem", "position": 2, "name": "Credit Cards",
                "item": "https://www.hdfc.bank.in/credit-cards"}},
              {{"@type": "ListItem", "position": 3, "name": "Millennia Credit Card",
                "item": "https://www.hdfc.bank.in/credit-cards/millennia-credit-card"}}
            ]
          }}
        </script>
      </head>
      <body>
        <div class="pd-banner">
          <h1><span class="banner-title">Millennia Credit Card</span></h1>
          <img class="cmp-image__image" alt="Millennia"
               src="/content/dam/.../preview-img.png"
               data-src="https://cdn.example.com/millennia-card.png?fmt=webp">
          <main>
            <a class="btn btn-primary"
               href="https://applyonline.example.com/cards/millennia">Apply Now</a>
          </main>
        </div>
        <div class="cmp-tabs__tabpanel">
          <h3>Fees and Renewal</h3>
          <div class="cmp-teaser__description">
            Joining/Renewal Membership Fee: ₹1,000 plus Applicable Taxes.
            Membership Renewal Fee 2nd year onwards: ₹1,000 plus taxes.
          </div>
        </div>
        <div class="cmp-accordion__item">
          <h3>What is Millennia?</h3>
          <div class="cmp-accordion__panel">A rewards credit card.</div>
        </div>
      </body>
    </html>
    """
    rec = parse_card(html)
    assert rec.card_name == "Millennia Credit Card"
    assert rec.card_slug == "millennia-credit-card"
    assert rec.source_url == (
        "https://www.hdfc.bank.in/credit-cards/millennia-credit-card"
    )
    assert rec.image_url == "https://cdn.example.com/millennia-card.png?fmt=webp"
    assert rec.extra["description"] == "Millennia Credit Card description."
    assert rec.extra["apply_url"] == "https://applyonline.example.com/cards/millennia"
    assert rec.fees["joining"] == 1000
    assert rec.fees["annual"] == 1000
    assert rec.fees["annual_percentage_rate"] == "23.88% to 43.2%*"
    assert rec.extra["faq"] == [
        {"question": "What is Millennia?", "answer": "A rewards credit card."}
    ]
    assert rec.extra["breadcrumb"][0]["name"] == "Home"
    assert rec.extra["breadcrumb"][-1]["name"] == "Millennia Credit Card"


# --------------------------------------------------------------------------- #
# Direct unit tests for small helpers (no HTML required)
# --------------------------------------------------------------------------- #

def test_slug_from_url_strips_trailing_slash() -> None:
    assert (
        _slug_from_url("https://x.com/credit-cards/regalia-first-credit-card")
        == "regalia-first-credit-card"
    )
    assert (
        _slug_from_url("https://x.com/credit-cards/regalia-first-credit-card/")
        == "regalia-first-credit-card"
    )


def test_slug_from_url_falls_back_to_unknown() -> None:
    assert _slug_from_url(None) == "unknown"
    assert _slug_from_url("") == "unknown"
    assert _slug_from_url("https://x.com/") == "unknown"


def test_iter_jsonld_skips_invalid_blocks() -> None:
    from bs4 import BeautifulSoup

    html = """
    <html><head>
      <script type="application/ld+json">{not valid json</script>
      <script type="application/ld+json">{"@type": "Thing"}</script>
    </head></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    blocks = _iter_jsonld(soup)
    assert len(blocks) == 1
    assert blocks[0]["@type"] == "Thing"


def test_extract_apply_url_excludes_header_footer_nav() -> None:
    """The footer 'Apply Online' links point at *other* cards; they
    must not be treated as this card's apply URL."""
    from bs4 import BeautifulSoup

    html = """
    <html>
      <body>
        <header><a href="https://applyonline.example.com/cards/wrong-1">Apply Online</a></header>
        <nav><a href="https://applyonline.example.com/cards/wrong-2">Apply Now</a></nav>
        <main>
          <a href="https://applyonline.example.com/cards/right">Apply for Millennia</a>
        </main>
        <footer><a href="https://applyonline.example.com/cards/wrong-3">Apply Online</a></footer>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _extract_apply_url(soup) == "https://applyonline.example.com/cards/right"


def test_extract_apply_url_returns_none_when_all_anchors_empty() -> None:
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <main><a href="">Apply Online</a></main>
      <main><a href="">Apply</a></main>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert _extract_apply_url(soup) is None


def test_selectors_are_centralized() -> None:
    """Guard against duplicated magic strings in the parser body.

    A future refactor that hard-codes a selector inside a function body
    is a smell; it should use one of the module-level constants.
    """
    import parsers.hdfc_card as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    # The selectors below MUST appear at module level.
    for selector in (
        SELECTOR_CANONICAL,
        SELECTOR_DESCRIPTION_META,
        SELECTOR_H1,
        SELECTOR_HERO_IMAGE,
    ):
        assert selector in source
