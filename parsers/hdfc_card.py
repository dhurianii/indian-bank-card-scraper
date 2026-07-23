"""
parsers/hdfc_card.py
-------------------
Parse a single HDFC credit-card detail page (e.g.
``/personal/pay/cards/credit-cards/<slug>``) into a :class:`CardRecord`.

The parser is a *pure* function. It does no I/O: callers pass in the HTML
string. It never touches the network, the filesystem, or the database.

Sprint 3.5 scope
================

Per the Sprint 3.4 discovery (see ``docs/sprint3_4_discovery.md``), this
parser extracts ONLY the high-cofidence fields. Lower-confidence fields
(rewards, cashback, benefits, insurance, lounge, travel, lifestyle) are
explicitly out of scope and belong to later sprints.

Fields populated
----------------

* ``card_name``  — from ``<h1>`` (authoritative; ignores listing-page name).
* ``card_slug``  — from the canonical URL's last path segment.
* ``source_url`` — from ``<link rel="canonical" href="...">``.
* ``image_url``  — from the lazy-loaded ``data-src`` on the hero image
                   (``div.pd-banner img.cmp-image__image``). The
                   ``src`` attribute is just a generic preview placeholder
                   and is ignored.
* ``description``— from ``<meta name="description" content="...">``.
* ``apply_url``  — from the first "Apply" anchor in the page body
                   (excluded: header navigation and footer). ``None`` when
                   missing or empty.
* ``fees``       — ``joining``, ``annual`` (best-effort regex on the
                   "Fees and Renewal" / "Fees & Charges" tab panel text),
                   and ``annual_percentage_rate`` from JSON-LD
                   ``@type: CreditCard``.
* ``faq``        — list of ``{"question", "answer"}`` dicts, taken from
                   JSON-LD ``@type: FAQPage`` (preferred) or, if missing,
                   the HTML ``div.cmp-accordion__item`` items.
* ``breadcrumb`` — list of ``{"name", "url"}`` dicts from JSON-LD
                   ``@type: BreadcrumbList``.

All of the above are stored in the existing ``CardRecord`` slots; no model
changes are required. Anything that does not fit cleanly (``description``,
``apply_url``, ``faq``, ``breadcrumb``, ``annual_percentage_rate``) is
stored in the existing ``extra`` dict.

Authoritative-name rule
------------------------

The listing page may report a card name that disagrees with the detail
page (HDFC aliases some URLs — e.g. ``/millennia-credit-card`` serves the
Regalia First page). The detail page's ``<h1>`` is the source of truth
and always wins.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from models import CardRecord


# --------------------------------------------------------------------------- #
# Constants (centralized so tests and the manual script can reuse them)
# --------------------------------------------------------------------------- #

BANK_ID: str = "hdfc"
CARD_TYPE: str = "credit"

# The slug of the only detail page we have on disk. Used for fixture-based
# tests; not used at parse-time.
_FIXTURE_SLUG: str = "regalia-first-credit-card"

# The default slug used when the page has no canonical URL.
_UNKNOWN_SLUG: str = "unknown"

# Selectors (kept as module constants so tests can reuse them).
SELECTOR_CANONICAL: str = "link[rel='canonical']"
SELECTOR_DESCRIPTION_META: str = "meta[name='description']"
SELECTOR_HERO_IMAGE: str = "div.pd-banner img.cmp-image__image"
SELECTOR_H1: str = "h1"
SELECTOR_APPLY_ANCHOR: str = (
    # Anything in the main page body (excluded: header/footer/nav)
    "main a, div.pageWrapper a, div.pd-banner ~ * a, div.pd-banner a"
)
SELECTOR_FEE_PANEL: str = "div.cmp-tabs__tabpanel"
SELECTOR_FEE_PANEL_HEADER: str = "h3"
SELECTOR_FEE_PANEL_BODY: str = "div.cmp-teaser__description"
SELECTOR_NAV_LANDMARKS: str = "header, footer, nav"
SELECTOR_JSONLD_SCRIPT: str = "script[type='application/ld+json']"

# Regexes for fee extraction. Compiled once at import time.
_RE_FEE_JOINING: re.Pattern[str] = re.compile(
    r"Joining(?:\s*/\s*Renewal)?(?:\s*Membership)?\s*Fee\s*[:\-]?\s*"
    r"₹?\s*([\d,]+)",
    re.IGNORECASE,
)
# The annual regex deliberately does NOT match the bare word "Renewal"
# inside a "Joining/Renewal Membership Fee" phrase. It requires the
# "Annual Renewal Fee" or "Membership Renewal Fee" phrase to appear as
# a self-contained token, then captures the FIRST rupee amount that
# follows. This is the only way to disambiguate from the joining fee,
# and it tolerates the "Membership Renewal Fee 2 nd year onwards: ₹1,000"
# tail that HDFC sometimes inserts.
_RE_FEE_ANNUAL: re.Pattern[str] = re.compile(
    r"(?:(?:Annual|Membership)\s+)+Renewal\s*Fee"
    r"[^₹]*₹\s*([\d,]+)",
    re.IGNORECASE,
)
_RE_FEE_NUMERIC_CLEAN: re.Pattern[str] = re.compile(r"[^\d]")


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def parse_card(html: str) -> CardRecord:
    """Parse an HDFC card detail page and return a :class:`CardRecord`.

    Args:
        html: Raw HTML of the detail page.

    Returns:
        A populated ``CardRecord``. Required text fields default to
        empty strings when the corresponding element is missing;
        optional fields default to ``None`` or empty containers.
    """
    soup = BeautifulSoup(html, "html.parser")

    canonical_url = _extract_canonical_url(soup)
    card_slug = _slug_from_url(canonical_url)

    card_name = _extract_card_name(soup)
    image_url = _extract_image_url(soup)
    description = _extract_description(soup)
    apply_url = _extract_apply_url(soup)
    fees = _extract_fees(soup)
    faq = _extract_faq(soup)
    breadcrumb = _extract_breadcrumb(soup)

    extra: dict[str, Any] = {}
    if description:
        extra["description"] = description
    if apply_url is not None:
        extra["apply_url"] = apply_url
    if faq:
        extra["faq"] = faq
    if breadcrumb:
        extra["breadcrumb"] = breadcrumb

    return CardRecord(
        bank_id=BANK_ID,
        card_slug=card_slug,
        card_name=card_name,
        card_type=CARD_TYPE,
        network="",  # not present on the page; see Sprint 3.4 §3.2
        image_url=image_url,
        source_url=canonical_url,
        fees=fees,
        rewards={},
        extra=extra,
    )


# --------------------------------------------------------------------------- #
# Field extractors
# --------------------------------------------------------------------------- #

def _extract_canonical_url(soup: BeautifulSoup) -> Optional[str]:
    """Return the page's canonical URL, or ``None`` if missing."""
    tag = soup.select_one(SELECTOR_CANONICAL)
    if tag is None:
        return None
    href = (tag.get("href") or "").strip()
    return href or None


def _slug_from_url(url: Optional[str]) -> str:
    """Return the last non-empty path segment of ``url``.

    Falls back to ``"unknown"`` if the URL has no usable path. Never
    raises — the parser must be robust against malformed canonical URLs.
    """
    if not url:
        return _UNKNOWN_SLUG
    path = urlparse(url).path
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return _UNKNOWN_SLUG
    return segments[-1]


def _extract_card_name(soup: BeautifulSoup) -> str:
    """Return the card name from the page's first ``<h1>``.

    The page wraps the title in a ``<span class="banner-title">`` inside
    the ``<h1>``; the ``<h1>`` text and the span text are identical, so
    reading the ``<h1>`` is sufficient.
    """
    tag = soup.select_one(SELECTOR_H1)
    if tag is None:
        return ""
    return tag.get_text(strip=True)


def _extract_image_url(soup: BeautifulSoup) -> Optional[str]:
    """Return the lazy-loaded hero card image URL.

    The hero ``<img>`` is loaded by ``lozad``, so the real URL is in the
    ``data-src`` attribute. The ``src`` attribute itself is just a
    generic ``/content/dam/.../preview-img.png`` placeholder and must
    not be used.
    """
    tag = soup.select_one(SELECTOR_HERO_IMAGE)
    if tag is None:
        return None
    data_src = (tag.get("data-src") or "").strip()
    return data_src or None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Return the ``<meta name="description">`` content, or ``None``."""
    tag = soup.select_one(SELECTOR_DESCRIPTION_META)
    if tag is None:
        return None
    content = (tag.get("content") or "").strip()
    return content or None


def _extract_apply_url(soup: BeautifulSoup) -> Optional[str]:
    """Return the card's apply URL, or ``None`` if unavailable.

    Heuristic: find the first ``<a>`` in the page body whose visible text
    contains "apply" (case-insensitive) and is *not* inside a header,
    footer, or nav landmark. An empty ``href`` becomes ``None``.
    """
    body = _page_body(soup)
    for anchor in body.find_all("a"):
        text = anchor.get_text(strip=True).lower()
        if "apply" not in text:
            continue
        href = (anchor.get("href") or "").strip()
        if href:
            return href
        # First hit had empty href; keep looking in case a later anchor
        # has a real URL before we give up.
    return None


def _page_body(soup: BeautifulSoup) -> Tag:
    """Return a tag representing the page body, with header/footer/nav removed.

    If no usable body container is found, falls back to the full soup.
    The returned tag is a *copy* of the soup's tree with the
    header/footer/nav landmarks removed, so callers can iterate without
    worrying about cross-sell apply links in the global navigation.
    """
    # Copy the root tag (BeautifulSoup's root is a Tag-like object).
    body = BeautifulSoup(str(soup), "html.parser")
    for landmark in body.select(SELECTOR_NAV_LANDMARKS):
        landmark.decompose()
    return body


def _extract_fees(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract the ``fees`` dict from the page.

    Sources, in priority order:
    1. The "Fees and Renewal" (preferred) or "Fees & Charges" tab panel.
    2. JSON-LD ``@type: CreditCard`` for ``annualPercentageRate``.

    Best-effort: missing fields are simply absent from the returned dict.
    """
    fees: dict[str, Any] = {}

    panel_text = _find_fee_panel_text(soup)
    if panel_text:
        joining = _parse_rupee_amount(_RE_FEE_JOINING.search(panel_text))
        if joining is not None:
            fees["joining"] = joining
        annual = _parse_rupee_amount(_RE_FEE_ANNUAL.search(panel_text))
        if annual is not None:
            fees["annual"] = annual

    apr = _extract_annual_percentage_rate(soup)
    if apr is not None:
        fees["annual_percentage_rate"] = apr

    return fees


def _find_fee_panel_text(soup: BeautifulSoup) -> Optional[str]:
    """Return the concatenated text of the fees tab panel, or ``None``.

    HDFC's pages expose two fees sections: the newer "Fees and Renewal"
    panel (with explicit separate joining and renewal amounts) and the
    older "Fees & Charges" panel (which often quotes a single combined
    "Joining/Renewal Membership Fee" amount). We prefer the newer one
    when both are present; otherwise we use whichever is available.
    """
    preferred = "fees and renewal"
    fallback = "fees & charges"
    seen: dict[str, str] = {}
    for panel in soup.select(SELECTOR_FEE_PANEL):
        header = panel.select_one(SELECTOR_FEE_PANEL_HEADER)
        if header is None:
            continue
        header_text = header.get_text(strip=True).lower()
        if header_text not in {preferred, fallback}:
            continue
        body = panel.select_one(SELECTOR_FEE_PANEL_BODY)
        if body is None:
            continue
        seen[header_text] = body.get_text(" ", strip=True)
    return seen.get(preferred) or seen.get(fallback)


def _parse_rupee_amount(match: Optional[re.Match[str]]) -> Optional[int]:
    """Convert a regex match like ``"1,000"`` to ``1000``.

    Returns ``None`` if there was no match. Strips commas and other
    non-digit characters defensively.
    """
    if match is None:
        return None
    raw = match.group(1)
    digits = _RE_FEE_NUMERIC_CLEAN.sub("", raw)
    return int(digits) if digits else None


def _extract_annual_percentage_rate(soup: BeautifulSoup) -> Optional[str]:
    """Return ``annualPercentageRate`` from JSON-LD ``@type: CreditCard``.

    Returns the value verbatim (HDFC writes e.g. ``"23.88% to 43.2%*"``).
    """
    for block in _iter_jsonld(soup):
        if block.get("@type") == "CreditCard":
            value = block.get("annualPercentageRate")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_faq(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Return the FAQ as a list of ``{"question", "answer"}`` dicts.

    JSON-LD (``@type: FAQPage``) is preferred because it is the most
    stable source. The HTML accordion is a fallback.
    """
    for block in _iter_jsonld(soup):
        if block.get("@type") == "FAQPage":
            items = block.get("mainEntity") or []
            result: list[dict[str, str]] = []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    question = (item.get("name") or "").strip()
                    answer_node = item.get("acceptedAnswer") or {}
                    answer = ""
                    if isinstance(answer_node, dict):
                        answer = (answer_node.get("text") or "").strip()
                    if question and answer:
                        result.append({"question": question, "answer": answer})
            if result:
                return result

    # Fallback: HTML accordion.
    result = []
    for item in soup.select("div.cmp-accordion__item"):
        h3 = item.find("h3")
        panel = item.select_one("div.cmp-accordion__panel")
        if h3 is None or panel is None:
            continue
        question = h3.get_text(strip=True)
        answer = panel.get_text(" ", strip=True)
        if question and answer:
            result.append({"question": question, "answer": answer})
    return result


def _extract_breadcrumb(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Return the breadcrumb as a list of ``{"name", "url"}`` dicts.

    Sourced from JSON-LD ``@type: BreadcrumbList``. Order is preserved.
    """
    for block in _iter_jsonld(soup):
        if block.get("@type") == "BreadcrumbList":
            items = block.get("itemListElement") or []
            result: list[dict[str, str]] = []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    name = (item.get("name") or "").strip()
                    url = (item.get("item") or "").strip()
                    if name and url:
                        result.append({"name": name, "url": url})
            if result:
                return result
    return []


def _iter_jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Yield parsed JSON-LD blocks, silently skipping any that fail to parse.

    HDFC's pages emit several ``<script type="application/ld+json">`` tags
    and not all of them parse cleanly; we must not let one bad block
    abort the parser.
    """
    results: list[dict[str, Any]] = []
    for tag in soup.select(SELECTOR_JSONLD_SCRIPT):
        try:
            data = json.loads(tag.get_text())
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            results.append(data)
    return results
