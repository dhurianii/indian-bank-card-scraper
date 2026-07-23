"""
parsers/hdfc.py
---------------
Parse the HDFC Bank "Types of Cards" listing page
(https://www.hdfcbank.com/personal/pay/cards) and return one record
per card category teaser found on the page.

The parser is a pure function. It does no I/O: callers pass in the
HTML string. It returns the data exactly as it appears in the
source HTML (no normalization, no "View " prefix stripping, no
URL absolutization). Sprint 3.2 deliberately keeps extraction
narrow; richer shaping belongs to later sprints.

Page structure (verified against the saved HTML):
    <a class="cmp-teaser__action-link btn btn-secondary"
       href="/<category-slug>"
       title="View <Category Name>"
       ...>View <Category Name> ...</a>

Each such <a> is one card. Other anchors on the page (navigation,
footer, "Read More" expanders with href="#") are filtered out by
the class selector.

Selector rationale:
    a.cmp-teaser__action-link.btn.btn-secondary
    - BEM-style AEM class (stable across AEM versions).
    - The compound btn.btn-secondary is what HDFC's frontend uses
      for the primary CTA on a teaser; it excludes "Read More"
      expanders and nav-menu links which use other classes.
"""

from __future__ import annotations

from bs4 import BeautifulSoup


# CSS selector for the "View <Category>" CTA inside each card teaser.
# Public so tests can reuse it without duplicating the magic string.
CARD_LINK_SELECTOR: str = "a.cmp-teaser__action-link.btn.btn-secondary"


def parse_listing(html: str) -> list[dict]:
    """Parse the HDFC cards listing page.

    Args:
        html: Raw HTML of the listing page, as a string.

    Returns:
        A list of {"card_name": str, "card_url": str} dicts, one
        per card teaser found on the page, in document order and
        deduplicated by card_url.

        Values are returned exactly as they appear in the source:
        - card_name is the raw ``title`` attribute (e.g.
          "View Credit Cards"); the "View " prefix is NOT stripped.
        - card_url is the raw ``href`` attribute (e.g.
          "/credit-cards"); URLs are NOT absolutized.
    """
    soup = BeautifulSoup(html, "html.parser")

    seen_urls: set[str] = set()
    cards: list[dict] = []

    for anchor in soup.select(CARD_LINK_SELECTOR):
        card_name = (anchor.get("title") or "").strip()
        card_url = (anchor.get("href") or "").strip()

        # Defensive: skip empty entries. Current page has none, but
        # the rule is cheap and guards against future drift.
        if not card_name or not card_url:
            continue

        # Deduplicate by URL while preserving first-seen order.
        if card_url in seen_urls:
            continue
        seen_urls.add(card_url)

        cards.append({"card_name": card_name, "card_url": card_url})

    return cards
