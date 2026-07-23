"""
scripts/parse_hdfc_listing.py
-----------------------------
Manual verification script for the HDFC listing-page parser.

Reads logs/debug/hdfc_cards.html (the artifact produced by
scripts/test_http_client.py), runs the pure parser, and prints
a small summary so a human can eyeball that the output is right.

This script is INTENTIONALLY a manual-only check:
- It reads from disk.
- It is not collected by pytest (it lives outside the tests/ tree).
- Run it with:  python scripts/parse_hdfc_listing.py

Per Sprint 3.2 decisions:
- No downloader / HTTP client / controller involvement.
- No database writes.
- No CardRecord construction.
- Parser itself remains pure (parsers/hdfc.py has no I/O).
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from parsers.hdfc import parse_listing  # noqa: E402  (import after path bootstrap)


HTML_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "hdfc_cards.html"
PREVIEW_COUNT: int = 10


def main() -> int:
    if not HTML_PATH.is_file():
        print(f"ERROR: Saved HTML not found at {HTML_PATH}", file=sys.stderr)
        print(
            "Run scripts/test_http_client.py first to download it.",
            file=sys.stderr,
        )
        return 1

    html = HTML_PATH.read_text(encoding="utf-8")
    cards = parse_listing(html)

    unique_urls = {entry["card_url"] for entry in cards}

    print()
    print(f"Cards Found : {len(cards)}")
    print(f"Unique URLs : {len(unique_urls)}")
    print()
    print(f"First {min(PREVIEW_COUNT, len(cards))} Cards:")
    for index, entry in enumerate(cards[:PREVIEW_COUNT], start=1):
        print(f"  {index:>2}. {entry['card_name']}  ->  {entry['card_url']}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
