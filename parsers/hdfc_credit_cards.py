"""Parser for the HDFC Bank credit-cards listing page.

The real card entries on this page live inside repeated
``div.card-wrap`` blocks (part of the "Types of Credit Cards" tabbed
carousel, class ``ourcardSuits-sec``). Each block looks like:

    <div class="card-wrap">
        <div class="header-card">
            ...
            <div class="rightcard-area">
                ...
                <h3 class="card-Title">Millennia Credit Card</h3>
                ...
            </div>
        </div>
        <div class="body-card">
            <div class="features-card">
                ...
                <div class="btn_wrap">
                    <a class="btn btn-primary" href="...apply-online...">APPLY ONLINE</a>
                    <a class="btn btn-primary-outline" href="/credit-cards/millennia-credit-card">
                        KNOW MORE
                    </a>
                </div>
            </div>
        </div>
    </div>

The "KNOW MORE" anchor (``a.btn-primary-outline`` inside ``.btn_wrap``)
is the only link present on *every* card -- including cards with no
"APPLY ONLINE" button (e.g. many "Others" tab cards) and cards marked
as no-longer-applicable / coming soon (href="/coming-soon") -- so it is
used as the canonical card URL.

The same physical card can appear in more than one tab (e.g. "Millennia
Credit Card" shows up under both "Popular Cards" and "Everyday
Rewards"), so results are deduplicated by URL, keeping the first
occurrence (preserving document order).

A separate, unrelated "suggestion" placeholder card (class
``uniqueCardemptyCard`` / ``blur-overlay``) is rendered once per tab as
a filler CTA ("We Have a Credit Card Made for You!") and is not a real
card entry, so it is skipped.
"""

from bs4 import BeautifulSoup


def parse_listing(html: str) -> list[dict]:
    """Parse the HDFC credit-cards listing HTML.

    Args:
        html: Raw HTML of the credit cards listing page.

    Returns:
        A list of dicts, each with exactly two keys:
            - "card_name": the card's display name
            - "card_url": the card's URL (left as-is; relative URLs
              are NOT resolved to absolute)
        Order is preserved (first occurrence wins) and entries are
        deduplicated by URL. Entries with a blank name or missing
        href are skipped. Inactive / "coming soon" cards are kept.
    """
    soup = BeautifulSoup(html, "html.parser")

    seen_urls: set[str] = set()
    results: list[dict] = []

    for card_wrap in soup.select("div.card-wrap"):
        classes = card_wrap.get("class") or []
        if "blur-overlay" in classes:
            # Filler "suggest a card" CTA block, not a real card.
            continue

        title_tag = card_wrap.select_one("h3.card-Title")
        card_name = title_tag.get_text(strip=True) if title_tag else ""

        link_tag = card_wrap.select_one(".btn_wrap a.btn-primary-outline")
        card_url = link_tag.get("href") if link_tag else None

        if not card_name or not card_url:
            continue

        if card_url in seen_urls:
            continue
        seen_urls.add(card_url)

        results.append({"card_name": card_name, "card_url": card_url})

    return results