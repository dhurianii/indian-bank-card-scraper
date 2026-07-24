"""
scripts/download_hdfc_images.py
-------------------------------
End-to-end script for Sprint 3.6.

* Load the saved HDFC Credit Cards listing page.
* Parse the 45 individual card entries.
* For each card:
    - Resolve its URL to an absolute URL.
    - Fetch the detail page with :class:`HttpClient`.
    - Run :func:`parsers.hdfc_card.parse_card` to get
      ``image_url`` and ``card_slug``.
    - Hand the image URL to :class:`ImageDownloader`.
* Print a progress line per card and a final summary.

Run with:  python scripts/download_hdfc_images.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urljoin

# Force UTF-8 stdout so non-ASCII characters survive on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from http_client import HttpClient  # noqa: E402
from image_downloader import ImageDownloader  # noqa: E402
from parsers.hdfc_card import parse_card  # noqa: E402
from parsers.hdfc_credit_cards import parse_listing  # noqa: E402


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
LISTING_HTML: Path = PROJECT_ROOT / "logs" / "debug" / "hdfc_credit_cards.html"
LISTING_BASE_URL: str = "https://www.hdfc.bank.in/personal/pay/cards/credit-cards"
BANK_ID: str = "hdfc"
HTTP_TIMEOUT: float = 30.0

# Polite delay between detail-page requests (matches config.REQUEST_DELAY_SECONDS).
REQUEST_DELAY_SECONDS: float = 0.5


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _resolve_url(card_url: str) -> str:
    """Resolve a possibly-relative listing URL to an absolute HTTPS URL."""
    return urljoin(LISTING_BASE_URL, card_url)


def _print_header() -> None:
    print()
    print("=" * 60)
    print("HDFC Credit Card Image Downloader — Sprint 3.6")
    print("=" * 60)
    print(f"Listing HTML : {LISTING_HTML}")
    print(f"Listing base : {LISTING_BASE_URL}")
    print(f"Output dir   : {PROJECT_ROOT / 'images' / 'raw' / BANK_ID}")
    print()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    if not LISTING_HTML.is_file():
        print(f"ERROR: missing listing HTML: {LISTING_HTML}", file=sys.stderr)
        return 1

    _print_header()

    cards = parse_listing(LISTING_HTML.read_text(encoding="utf-8"))
    total = len(cards)
    print(f"Found {total} cards in listing.\n")

    http = HttpClient(timeout=HTTP_TIMEOUT)
    downloader = ImageDownloader(http_client=http)

    downloaded = 0
    skipped = 0
    failed = 0
    failed_cards: list[tuple[str, str]] = []  # (card_name, reason)
    no_image: list[str] = []  # cards whose detail page had no image_url

    try:
        for index, card in enumerate(cards, start=1):
            name = card["card_name"]
            slug = card["card_url"]  # we re-derive the real slug from the canonical
            print(f"Downloading {index}/{total}: {name} ...", flush=True)

            detail_url = _resolve_url(card["card_url"])
            try:
                html = http.get(detail_url)
            except Exception as exc:  # noqa: BLE001 - we want every error
                failed += 1
                failed_cards.append((name, f"detail fetch: {exc}"))
                print(f"  -> FAILED (detail fetch: {exc})", flush=True)
                continue

            record = parse_card(html)
            if not record.image_url:
                failed += 1
                no_image.append(name)
                failed_cards.append((name, "no image_url on detail page"))
                print("  -> FAILED (no image_url on detail page)", flush=True)
                continue

            # Count this as a skip if the file already exists, BEFORE doing
            # the network call, so the summary accurately reflects "we did
            # not re-download an already-cached file".
            target = downloader.target_path(
                record.card_slug, url=record.image_url,
            )
            already_present = target.exists()

            saved = downloader.download(
                record.image_url,
                card_slug=record.card_slug,
                bank_id=BANK_ID,
            )

            if saved is not None:
                downloaded += 1
                print(f"  -> saved {saved.name} ({saved.stat().st_size:,} bytes)", flush=True)
            elif already_present:
                skipped += 1
                print(f"  -> skipped (already present: {target.name})", flush=True)
            else:
                failed += 1
                failed_cards.append((name, "download returned None"))
                print("  -> FAILED (download returned None)", flush=True)

            # Be polite to HDFC's origin between requests.
            if index < total:
                time.sleep(REQUEST_DELAY_SECONDS)

    finally:
        downloader.close()

    # --- Summary ------------------------------------------------------------
    print()
    print("Completed.")
    print()
    print(f"Images downloaded : {downloaded}")
    print(f"Skipped           : {skipped}")
    print(f"Failed            : {failed}")
    if no_image:
        print()
        print("Cards with no image on the detail page:")
        for n in no_image:
            print(f"  - {n}")
    if failed_cards:
        print()
        print("Failed cards (detail):")
        for n, reason in failed_cards:
            if reason == "no image_url on detail page":
                continue  # already shown above
            print(f"  - {n}: {reason}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
