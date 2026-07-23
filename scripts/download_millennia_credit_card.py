"""
scripts/download_millennia_credit_card.py
-----------------------------------------
One-shot download of a single HDFC credit card detail page using the
existing HttpClient (Sprint 3.1). Output goes to
logs/debug/millennia_credit_card.html so it can be inspected offline
during Sprint 3.4 discovery.

Sprint 3.4 is discovery-only. This script:
- Touches the real network.
- Lives outside tests/ so pytest does not collect it.
- Does NOT modify http_client.py, downloader.py, parsers, or models.
- Does NOT build any parser or write to the database.

Run with:  python scripts/download_millennia_credit_card.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from http_client import HttpClient, HttpClientError  # noqa: E402


# The card detail page discovered in Sprint 3.3 via the credit-cards
# category listing. We use the "KNOW MORE" URL pattern observed there.
TARGET_URL: str = "https://www.hdfcbank.com/personal/pay/cards/credit-cards/millennia-credit-card"
OUTPUT_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "millennia_credit_card.html"


def main() -> int:
    client = HttpClient()
    try:
        try:
            html = client.get(TARGET_URL)
        except HttpClientError as exc:
            print(f"ERROR: HTTP failure: {exc}", file=sys.stderr)
            return 1

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(html, encoding="utf-8")

        size_bytes = OUTPUT_PATH.stat().st_size
        print()
        print("HTTP success")
        print(f"  URL     : {TARGET_URL}")
        print(f"  Chars   : {len(html):,}")
        print(f"  Size    : {size_bytes:,} bytes")
        print(f"  Output  : {OUTPUT_PATH}")
        print()
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
