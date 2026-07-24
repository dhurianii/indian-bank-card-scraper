"""
scripts/test_database.py
------------------------
Sprint 4.1 — manual verification script for SQLite persistence.

Pipeline:
  1. Load the saved HDFC detail page (logs/debug/millennia_credit_card.html).
  2. Parse it with parsers.hdfc_card.parse_card -> CardRecord.
  3. Save the card into a temporary SQLite database.
  4. Print the inserted card's rowid, fields, and the raw JSON
     columns read back from disk.

This script uses a TEMPORARY database under
``database/test_database_sprint_4_1.db`` (NOT the production
``database/cards.db``) so it is safe to re-run without polluting
production data.

Run with:  python scripts/test_database.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# Force UTF-8 stdout so non-ASCII (rupee signs, em-dashes) survives
# on Windows consoles.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import CardRepository  # noqa: E402
from models import CardRecord  # noqa: E402
from parsers.hdfc_card import parse_card  # noqa: E402


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HTML_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "millennia_credit_card.html"
# A dedicated DB so the script never touches the production file.
SCRIPT_DB_PATH: Path = PROJECT_ROOT / "database" / "test_database_sprint_4_1.db"
# The production DB path — printed so the user can see what is NOT being touched.
PRODUCTION_DB_PATH: Path = PROJECT_ROOT / "database" / "cards.db"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _print_header(title: str) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def _print_field(label: str, value: object) -> None:
    """Print one labelled field."""
    print(f"  {label:<24} : {value!r}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    if not HTML_PATH.is_file():
        print(f"ERROR: missing HTML fixture: {HTML_PATH}", file=sys.stderr)
        print(
            "Run scripts/download_millennia_credit_card.py first to download it.",
            file=sys.stderr,
        )
        return 1

    html = HTML_PATH.read_text(encoding="utf-8")
    record = parse_card(html)

    _print_header("Sprint 4.1 — SQLite Persistence Manual Test")

    _print_field("Input HTML path", str(HTML_PATH))
    _print_field("Input HTML size", f"{len(html):,} chars")
    _print_field("Target DB      ", str(SCRIPT_DB_PATH))
    _print_field("Production DB  ", str(PRODUCTION_DB_PATH))
    _print_field("Production untouched", "yes (using a dedicated script DB)")

    # --- Persist ---------------------------------------------------------
    repo = CardRepository(db_path=SCRIPT_DB_PATH)
    row_id = repo.save_card(record)

    _print_header("Inserted card")
    _print_field("Bank",         record.bank_id)
    _print_field("Slug",         record.card_slug)
    _print_field("Name",         record.card_name)
    _print_field("Type",         record.card_type)
    _print_field("Network",      record.network)
    _print_field("Image URL",    record.image_url)
    _print_field("Source URL",   record.source_url)
    _print_field("SQLite row id", row_id)

    # --- Read back -------------------------------------------------------
    fetched = repo.get_card(record.bank_id, record.card_slug)
    if fetched is None:
        print("ERROR: card not found after insert", file=sys.stderr)
        return 1

    _print_header("Fetched back from SQLite")
    _print_field("Bank",         fetched.bank_id)
    _print_field("Slug",         fetched.card_slug)
    _print_field("Name",         fetched.card_name)
    _print_field("Type",         fetched.card_type)
    _print_field("Network",      fetched.network)
    _print_field("Image URL",    fetched.image_url)
    _print_field("Source URL",   fetched.source_url)

    # --- Raw JSON columns read directly from SQLite ---------------------
    # We open a raw sqlite3 connection (bypassing the repository)
    # so the user sees exactly what is on disk in the JSON columns.
    _print_header("Stored JSON columns (read from disk)")
    with sqlite3.connect(SCRIPT_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT fees, rewards, extra, created_at, updated_at "
            "FROM cards WHERE id = ?",
            (row_id,),
        ).fetchone()

    for column in ("fees", "rewards", "extra"):
        raw = row[column]
        print(f"\n  [{column}]   (raw, {len(raw):,} bytes)")
        try:
            parsed = json.loads(raw)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except json.JSONDecodeError as exc:
            print(f"  <bad json: {exc}>")
            print(f"  {raw[:200]!r}")

    _print_header("Timestamps")
    _print_field("created_at", row["created_at"])
    _print_field("updated_at", row["updated_at"])

    # --- Round-trip equality check --------------------------------------
    _print_header("Round-trip equality")
    if fetched == record:
        print("  OK — fetched CardRecord == parsed CardRecord (every field equal)")
    else:
        print("  FAIL — fetched CardRecord differs from parsed CardRecord")
        for f in record.to_dict():
            if getattr(record, f) != getattr(fetched, f):
                print(f"    {f}: parsed={getattr(record, f)!r}  fetched={getattr(fetched, f)!r}")
        return 1

    # --- Confirm UPSERT behaviour ---------------------------------------
    _print_header("UPSERT behaviour")
    print("  Re-saving the same card...")
    record.card_name = record.card_name + " (resaved)"
    repo.save_card(record)
    with sqlite3.connect(SCRIPT_DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        refetched = repo.get_card(record.bank_id, record.card_slug)
    _print_field("Total rows in DB", count)
    _print_field("Updated name    ", refetched.card_name if refetched else None)
    if count != 1:
        print(f"  FAIL — expected 1 row, got {count}", file=sys.stderr)
        return 1
    if refetched is None or "resaved" not in refetched.card_name:
        print("  FAIL — UPSERT did not update the row", file=sys.stderr)
        return 1
    print("  OK — UPSERT kept the row count at 1 and updated the name.")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
