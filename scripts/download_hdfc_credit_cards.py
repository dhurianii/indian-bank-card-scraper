"""
scripts/download_hdfc_credit_cards.py
-------------------------------------
One-shot download of the HDFC Credit Cards category page using the
existing HttpClient (Sprint 3.1). Output goes to
logs/debug/hdfc_credit_cards.html so it can be inspected for
Sprint 3.2-style parser development without any network access.

This script is INTENTIONALLY manual-only:
- Touches the real network.
- Lives outside tests/ so pytest does not collect it.
- Does NOT modify http_client.py or downloader.py.

Run with:  python scripts/download_hdfc_credit_cards.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from http_client import HttpClient, HttpClientError  # noqa: E402


TARGET_URL: str = "https://www.hdfcbank.com/personal/pay/cards/credit-cards"
OUTPUT_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "hdfc_credit_cards.html"


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
