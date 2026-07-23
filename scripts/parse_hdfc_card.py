"""
scripts/parse_hdfc_card.py
--------------------------
Manual verification script for the HDFC card detail-page parser
(parsers/hdfc_card.py).

Reads the raw HTML captured during Sprint 3.4
(logs/debug/millennia_credit_card.html), runs the pure parser, and
prints every extracted field cleanly. No network access, no DB writes.

Run with:  python scripts/parse_hdfc_card.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Force UTF-8 stdout so non-ASCII characters (HDFC's HTML uses
# narrow no-break spaces, rupee signs, em-dashes, etc.) survive on
# Windows consoles that default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# --- Path bootstrap so the script can be run from the project root -------- #
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models import CardRecord  # noqa: E402
from parsers.hdfc_card import parse_card  # noqa: E402


HTML_PATH: Path = PROJECT_ROOT / "logs" / "debug" / "millennia_credit_card.html"


def _print_section(title: str) -> None:
    """Print a clearly delimited section header."""
    print()
    print(f"--- {title} ---")


def _print_field(label: str, value: object) -> None:
    """Print a single labelled field, with a friendly representation."""
    print(f"  {label:<28} {value!r}")


def _print_faq(faq: list[dict[str, str]]) -> None:
    for index, item in enumerate(faq, start=1):
        print(f"  [{index}] Q: {item['question']}")
        print(f"      A: {item['answer']}")


def _print_breadcrumb(breadcrumb: list[dict[str, str]]) -> None:
    for index, item in enumerate(breadcrumb, start=1):
        print(f"  [{index}] {item['name']}  ->  {item['url']}")


def _render_record(record: CardRecord) -> None:
    _print_section("Identity")
    _print_field("bank_id", record.bank_id)
    _print_field("card_slug", record.card_slug)
    _print_field("card_name", record.card_name)
    _print_field("card_type", record.card_type)
    _print_field("network", record.network)
    _print_field("image_url", record.image_url)
    _print_field("source_url", record.source_url)

    _print_section("Fees")
    if record.fees:
        for key, value in record.fees.items():
            _print_field(key, value)
    else:
        print("  (none)")

    _print_section("Rewards")
    if record.rewards:
        for key, value in record.rewards.items():
            _print_field(key, value)
    else:
        print("  (none — out of scope for Sprint 3.5)")

    _print_section("Extra (description / apply_url)")
    description = record.extra.get("description")
    apply_url = record.extra.get("apply_url")
    if description is not None:
        _print_field("description", description)
    if apply_url is not None:
        _print_field("apply_url", apply_url)
    if description is None and apply_url is None:
        print("  (none)")

    faq = record.extra.get("faq")
    if faq:
        _print_section(f"FAQ ({len(faq)} items)")
        _print_faq(faq)
    else:
        _print_section("FAQ")
        print("  (none)")

    breadcrumb = record.extra.get("breadcrumb")
    if breadcrumb:
        _print_section(f"Breadcrumb ({len(breadcrumb)} items)")
        _print_breadcrumb(breadcrumb)
    else:
        _print_section("Breadcrumb")
        print("  (none)")


def main() -> int:
    if not HTML_PATH.is_file():
        print(f"ERROR: Saved HTML not found at {HTML_PATH}", file=sys.stderr)
        print(
            "Run scripts/download_millennia_credit_card.py first to download it.",
            file=sys.stderr,
        )
        return 1

    html = HTML_PATH.read_text(encoding="utf-8")
    record = parse_card(html)

    print()
    print("=" * 60)
    print("HDFC card detail-page parser — manual verification")
    print("=" * 60)
    print(f"Input HTML : {HTML_PATH}")
    print(f"Input size : {len(html):,} chars")

    _render_record(record)

    _print_section("Raw dict (as_dict)")
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False, default=str))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
