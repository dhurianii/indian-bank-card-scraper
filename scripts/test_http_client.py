"""
scripts/test_http_client.py
---------------------------
Manual integration test for the HttpClient.

Fetches the HDFC Bank cards listing page using the project's HttpClient
and writes the raw HTML to logs/debug/hdfc_cards.html. Prints a small
summary to stdout.

This script is INTENTIONALLY a manual-only test:
- It touches the real network.
- It is not collected by pytest (it lives outside the tests/ tree).
- Run it with:  python scripts/test_http_client.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from http_client import HttpClient, HttpClientError  # noqa: E402  (import after path bootstrap)


# --- Configuration for this manual test ----------------------------------- #
TARGET_URL: str = "https://www.hdfcbank.com/personal/pay/cards"
OUTPUT_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "hdfc_cards.html"


def _configure_logging() -> None:
    """Stream INFO logs to stdout so the run is easy to follow."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )


def main() -> int:
    """Run the manual integration test. Returns a process exit code."""
    _configure_logging()
    logger = logging.getLogger("scripts.test_http_client")

    client = HttpClient()
    try:
        try:
            html = client.get(TARGET_URL)
        except HttpClientError as exc:
            logger.error("HTTP failure: %s", exc)
            return 1

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(html, encoding="utf-8")

        # --- Summary ----------------------------------------------------- #
        print()
        print("HTTP success")
        print(f"  URL     : {TARGET_URL}")
        print(f"  Chars   : {len(html):,}")
        print(f"  Output  : {OUTPUT_PATH}")
        print()
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
