"""
scripts/build_hdfc_database.py
------------------------------
Sprint 4.2 — production runner that builds ``database/cards.db`` from
the live HDFC credit-cards listing.

Pipeline
========

    HDFC listing page (saved HTML)
            ↓
    parse_listing()   -> 45 card detail URLs
            ↓
    HttpClient.get()  -> detail HTML
            ↓
    parse_card()      -> CardRecord
            ↓
    CardRepository.save_card()   -> UPSERT into cards.db
            ↓
    ImageDownloader.download()   -> WebP under images/raw/hdfc/

This script INTENTIONALLY reuses every existing module; it contains
no parsing, no SQL, no HTTP, and no image-fetching logic of its own.
Its only job is **orchestration**: drive the pipeline end-to-end,
collect per-card outcomes, and write a final report.

Failure handling
================

The script is fail-safe: every card is processed inside a ``try``
block. A failure on any one card is recorded in
``logs/build_hdfc_errors.log`` and the loop continues. The final
``Failures`` count is the number of cards that could not be persisted
into the database (i.e. detail-page fetch errors). Cards that parsed
but lacked an ``image_url``, or whose image download failed, are
**still persisted**; only their image step is logged.

Re-runnability
==============

* The image downloader skips files that already exist.
* The repository UPSERTs on ``(bank_id, card_slug)``.
* So this script is safe to re-run any number of times; the second
  run will report 0 new images downloaded and 0 net inserts.

Usage
=====

    python scripts/build_hdfc_database.py
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin

# Force UTF-8 stdout so non-ASCII characters (rupee signs, em-dashes,
# HDFC's narrow no-break spaces, etc.) survive on Windows consoles
# that default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import CardRepository  # noqa: E402
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

# Path of the production database. CardRepository creates the file
# and applies the schema on construction.
PROD_DB_PATH: Path = PROJECT_ROOT / "database" / "cards.db"

# Path of the failure log. Created on demand.
ERROR_LOG_PATH: Path = PROJECT_ROOT / "logs" / "build_hdfc_errors.log"

# Output directory for downloaded images. Mirrors the on-disk layout
# used by the Sprint 3.6 downloader script.
IMAGES_DIR: Path = PROJECT_ROOT / "images" / "raw" / BANK_ID

# Polite delay between detail-page requests.
REQUEST_DELAY_SECONDS: float = 0.5


# --------------------------------------------------------------------------- #
# Result dataclass
# --------------------------------------------------------------------------- #
@dataclass
class BuildResult:
    """Aggregate outcome of a build run.

    The fields are independent so the script's summary can report
    each one separately:

      - ``cards_discovered``  : rows the listing parser returned
      - ``cards_processed``   : cards we attempted to persist
      - ``persisted``         : UPSERTs that returned a positive rowid
      - ``images_downloaded`` : images newly written to disk
      - ``images_skipped``    : cards whose image was already on disk
      - ``images_failed``     : image downloader returned ``None``
                                (not persisted as a row failure)
      - ``failures``          : cards that could not be persisted
                                (typically: detail-page fetch error)
      - ``failure_details``   : list of (name, url, reason) for failures
    """

    cards_discovered: int = 0
    cards_processed: int = 0
    persisted: int = 0
    images_downloaded: int = 0
    images_skipped: int = 0
    images_failed: int = 0
    failures: int = 0
    failure_details: list[tuple[str, str, str]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Pipeline (importable; tested in tests/test_build_hdfc_database.py)
# --------------------------------------------------------------------------- #
def _resolve_url(card_url: str) -> str:
    """Resolve a possibly-relative listing URL to an absolute HTTPS URL."""
    return urljoin(LISTING_BASE_URL, card_url)


def _configure_file_logger(log_path: Path) -> logging.Logger:
    """Return a logger that writes to ``log_path`` (created on demand).

    Independent of the root logger so the failure log is clean even
    when the user has ``logging.basicConfig()`` configured elsewhere.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    failure_logger = logging.getLogger("build_hdfc.failures")
    failure_logger.setLevel(logging.INFO)
    failure_logger.propagate = False  # do not echo to root logger

    # Reset handlers on every run so re-runs do not duplicate lines.
    failure_logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8", mode="w")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")
    )
    failure_logger.addHandler(handler)
    return failure_logger


def build_hdfc_database(
    *,
    listing_html: str,
    http: HttpClient,
    image_downloader: ImageDownloader,
    repository: CardRepository,
    listing_base_url: str = LISTING_BASE_URL,
    bank_id: str = BANK_ID,
    request_delay_seconds: float = REQUEST_DELAY_SECONDS,
    failure_log: Optional[logging.Logger] = None,
    progress_printer: Optional[Callable[[str], None]] = None,
) -> BuildResult:
    """Run the full HDFC pipeline against the given dependencies.

    The function is importable and parameter-driven so unit tests can
    drive it with mocks. The script's ``main`` is a thin wrapper that
    constructs real HttpClient / ImageDownloader / CardRepository and
    calls this function.

    Args:
        listing_html:        The raw HTML of the saved listing page.
        http:                An HttpClient (real or mock).
        image_downloader:    An ImageDownloader (real or mock).
        repository:          A CardRepository (real or mock).
        listing_base_url:    Base URL used to resolve relative card URLs.
        bank_id:             Bank identifier passed to the downloader.
        request_delay_seconds: Sleep between requests (0.0 in tests).
        failure_log:         Optional logger for per-card failures.
        progress_printer:    Optional callable for per-card progress
                             output. Defaults to ``print``.

    Returns:
        A populated :class:`BuildResult`.
    """
    if progress_printer is None:
        progress_printer = print

    result = BuildResult()

    cards = parse_listing(listing_html)
    result.cards_discovered = len(cards)
    total = len(cards)

    for index, card in enumerate(cards, start=1):
        name = card.get("card_name", "<unknown>")
        detail_url = _resolve_url(card.get("card_url", ""))

        progress_printer(
            f"[{index}/{total}] {name} -> {detail_url}", flush=True,
        )
        result.cards_processed += 1

        # --- 1. Fetch the detail page --------------------------------
        try:
            detail_html = http.get(detail_url)
        except Exception as exc:  # noqa: BLE001 - record every error
            result.failures += 1
            reason = f"{type(exc).__name__}: {exc}"
            result.failure_details.append((name, detail_url, reason))
            if failure_log is not None:
                failure_log.error(
                    "card=%r url=%r exception=%s", name, detail_url, reason,
                )
            progress_printer(f"  -> FAILED (detail fetch: {reason})", flush=True)
            # Be polite to HDFC's origin even on failure.
            if request_delay_seconds > 0 and index < total:
                time.sleep(request_delay_seconds)
            continue

        # --- 2. Parse the detail page -------------------------------
        # parse_card is defensive; it never raises on malformed HTML.
        # It always returns a CardRecord (possibly with empty fields).
        record = parse_card(detail_html)

        # --- 3. Persist the record (UPSERT) -------------------------
        try:
            row_id = repository.save_card(record)
        except Exception as exc:  # noqa: BLE001
            result.failures += 1
            reason = f"db save: {type(exc).__name__}: {exc}"
            result.failure_details.append((name, detail_url, reason))
            if failure_log is not None:
                failure_log.error(
                    "card=%r url=%r exception=%s", name, detail_url, reason,
                )
            progress_printer(f"  -> FAILED ({reason})", flush=True)
            if request_delay_seconds > 0 and index < total:
                time.sleep(request_delay_seconds)
            continue

        if row_id > 0:
            result.persisted += 1

        # --- 4. Download the image (best-effort) --------------------
        if record.image_url:
            target = image_downloader.target_path(
                record.card_slug, url=record.image_url,
            )
            already_present = target.exists()
            saved = image_downloader.download(
                record.image_url,
                card_slug=record.card_slug,
                bank_id=bank_id,
            )
            if saved is not None:
                result.images_downloaded += 1
                progress_printer(
                    f"  -> persisted row {row_id}; saved {saved.name} "
                    f"({saved.stat().st_size:,} bytes)",
                    flush=True,
                )
            elif already_present:
                result.images_skipped += 1
                progress_printer(
                    f"  -> persisted row {row_id}; image already present "
                    f"({target.name})",
                    flush=True,
                )
            else:
                result.images_failed += 1
                progress_printer(
                    f"  -> persisted row {row_id}; image download FAILED "
                    f"({record.image_url})",
                    flush=True,
                )
        else:
            progress_printer(
                f"  -> persisted row {row_id}; no image_url on detail page",
                flush=True,
            )

        # --- 5. Be polite to HDFC's origin --------------------------
        if request_delay_seconds > 0 and index < total:
            time.sleep(request_delay_seconds)

    return result


# --------------------------------------------------------------------------- #
# Summary printer (matches the brief's required format exactly)
# --------------------------------------------------------------------------- #
def _print_summary(result: BuildResult, db_path: Path, images_dir: Path) -> None:
    border = "=" * 49
    print()
    print(border)
    print("HDFC Production Database Build")
    print(border)
    print()
    print(f"Cards discovered : {result.cards_discovered}")
    print(f"Cards processed  : {result.cards_processed}")
    print(f"Inserted/Updated : {result.persisted}")
    print(f"Images downloaded: {result.images_downloaded}")
    print(f"Failures         : {result.failures}")
    print()
    print("Database:")
    print(f"  {db_path}")
    print()
    print("Images:")
    print(f"  {images_dir}")
    print()
    print(border)
    print()


# --------------------------------------------------------------------------- #
# Script entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    if not LISTING_HTML.is_file():
        print(f"ERROR: missing listing HTML: {LISTING_HTML}", file=sys.stderr)
        print(
            "Run scripts/download_hdfc_credit_cards.py first to download it.",
            file=sys.stderr,
        )
        return 1

    failure_log = _configure_file_logger(ERROR_LOG_PATH)

    # --- Build the real pipeline ------------------------------------------
    http = HttpClient(timeout=HTTP_TIMEOUT)
    image_downloader = ImageDownloader(http_client=http)
    repository = CardRepository(db_path=PROD_DB_PATH)

    try:
        result = build_hdfc_database(
            listing_html=LISTING_HTML.read_text(encoding="utf-8"),
            http=http,
            image_downloader=image_downloader,
            repository=repository,
            failure_log=failure_log,
        )
    finally:
        image_downloader.close()

    _print_summary(result, db_path=PROD_DB_PATH, images_dir=IMAGES_DIR)

    if result.failures:
        print(
            f"See failure log: {ERROR_LOG_PATH}",
            file=sys.stderr,
        )
        # Non-zero exit so a CI pipeline can detect a partial build.
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
