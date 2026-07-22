"""
tests/conftest.py
-----------------
Shared pytest fixtures for the project.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from database import CardRepository
from models import CardRecord


@pytest.fixture()
def tmp_db(tmp_path: Path) -> CardRepository:
    """A fresh CardRepository backed by a throwaway SQLite file."""
    return CardRepository(db_path=tmp_path / "test_cards.db")


@pytest.fixture()
def sample_card() -> CardRecord:
    """A single representative CardRecord for use across tests."""
    return CardRecord(
        bank_id="hdfc",
        card_slug="hdfc-regalia",
        card_name="Regalia Credit Card",
        card_type="credit",
        network="Visa",
        image_url="https://example.com/hdfc-regalia.png",
        source_url="https://example.com/hdfc/regalia",
        fees={"joining": 1000, "annual": 2500},
        rewards={"points_per_100": 4},
        extra={"tier": "premium"},
    )


@pytest.fixture()
def sample_cards() -> list[CardRecord]:
    """A small list of cards for bulk-insert tests."""
    return [
        CardRecord(
            bank_id="hdfc",
            card_slug="hdfc-regalia",
            card_name="Regalia Credit Card",
            card_type="credit",
            network="Visa",
        ),
        CardRecord(
            bank_id="hdfc",
            card_slug="hdfc-millennia",
            card_name="Millennia Credit Card",
            card_type="credit",
            network="Mastercard",
        ),
        CardRecord(
            bank_id="sbi",
            card_slug="sbi-simplyclick",
            card_name="SimplyCLICK Card",
            card_type="credit",
            network="Visa",
        ),
    ]
