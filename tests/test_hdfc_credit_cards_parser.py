from pathlib import Path

import pytest

from parsers.hdfc_credit_cards import parse_listing


HTML_FILE = Path("logs/debug/hdfc_credit_cards.html")


@pytest.fixture(scope="module")
def real_html():
    if not HTML_FILE.exists():
        pytest.skip(f"Missing HTML fixture: {HTML_FILE}")
    return HTML_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cards(real_html):
    return parse_listing(real_html)


def test_returns_list(cards):
    assert isinstance(cards, list)


def test_returns_expected_number_of_cards(cards):
    assert len(cards) == 45


def test_every_item_is_dict(cards):
    assert all(isinstance(card, dict) for card in cards)


def test_every_card_has_required_keys(cards):
    for card in cards:
        assert set(card.keys()) == {"card_name", "card_url"}


def test_no_blank_card_names(cards):
    assert all(card["card_name"].strip() for card in cards)


def test_no_blank_urls(cards):
    assert all(card["card_url"].strip() for card in cards)


def test_coming_soon_card_exists(cards):
    assert any(
        card["card_url"] == "/coming-soon"
        for card in cards
    )


def test_duplicate_urls_removed(cards):
    urls = [card["card_url"] for card in cards]
    assert len(urls) == len(set(urls))


def test_empty_html_returns_empty_list():
    assert parse_listing("") == []


def test_random_html_returns_empty_list():
    html = "<html><body><h1>Hello World</h1></body></html>"
    assert parse_listing(html) == []