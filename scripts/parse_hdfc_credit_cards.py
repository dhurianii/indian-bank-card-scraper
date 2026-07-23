"""
Manual verification script for the HDFC Credit Cards parser.

Usage:
    python scripts/parse_hdfc_credit_cards.py
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.hdfc_credit_cards import parse_listing

def main():
    html_file = Path("logs/debug/hdfc_credit_cards.html")

    if not html_file.exists():
        print(f"HTML file not found: {html_file}")
        return

    html = html_file.read_text(encoding="utf-8")

    cards = parse_listing(html)

    print("=" * 50)
    print("HDFC Credit Cards Parser")
    print("=" * 50)

    print(f"\nTotal Cards Found : {len(cards)}")

    unique_urls = len({card["card_url"] for card in cards})
    print(f"Unique URLs      : {unique_urls}")

    print("\nFirst 10 Cards:\n")

    for i, card in enumerate(cards[:10], start=1):
        print(f"{i}. {card['card_name']}")
        print(f"   {card['card_url']}\n")


if __name__ == "__main__":
    main()