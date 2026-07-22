"""
tests/test_database.py
----------------------
Unit tests for the CardRepository (CRUD + UPSERT).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from database import CardRepository
from models import CardRecord


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
class TestInitializeDatabase:
    def test_creates_db_file_when_missing(self, tmp_path: Path) -> None:
        db_file = tmp_path / "fresh.db"
        assert not db_file.exists()
        CardRepository(db_path=db_file)
        assert db_file.exists()

    def test_is_idempotent(self, tmp_db: CardRepository) -> None:
        # Calling initialize_database again must not raise.
        tmp_db.initialize_database()
        tmp_db.initialize_database()

    def test_creates_expected_schema(self, tmp_db: CardRepository) -> None:
        with tmp_db.connect() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "cards" in tables

    def test_unique_constraint_on_bank_and_slug(self, tmp_db: CardRepository) -> None:
        # Two rows with the same (bank_id, card_slug) must collide.
        card = CardRecord(
            bank_id="hdfc",
            card_slug="dup",
            card_name="First",
            card_type="credit",
            network="Visa",
        )
        tmp_db.save_card(card)

        # Bypassing save_card's UPSERT to confirm the underlying UNIQUE
        # constraint actually fires.
        card2 = CardRecord(
            bank_id="hdfc",
            card_slug="dup",
            card_name="Second",
            card_type="credit",
            network="Mastercard",
        )
        with pytest.raises(sqlite3.IntegrityError):
            with tmp_db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO cards (
                        bank_id, card_slug, card_name, card_type, network,
                        fees, rewards, extra, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, '{}', '{}', '{}', '2026-01-01', '2026-01-01')
                    """,
                    (card2.bank_id, card2.card_slug, card2.card_name,
                     card2.card_type, card2.network),
                )


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #
class TestSaveCard:
    def test_save_inserts_new_card(self, tmp_db: CardRepository, sample_card: CardRecord) -> None:
        tmp_db.save_card(sample_card)
        fetched = tmp_db.get_card(sample_card.bank_id, sample_card.card_slug)
        assert fetched is not None
        assert fetched.card_name == sample_card.card_name
        assert fetched.network == sample_card.network
        assert fetched.fees == sample_card.fees

    def test_save_upserts_on_duplicate_natural_key(
        self, tmp_db: CardRepository, sample_card: CardRecord
    ) -> None:
        tmp_db.save_card(sample_card)
        # Same (bank_id, card_slug) — change other fields, save again.
        sample_card.card_name = "Regalia V2"
        sample_card.network = "Mastercard"
        sample_card.fees = {"joining": 0, "annual": 5000}

        tmp_db.save_card(sample_card)

        # Still exactly one row.
        assert len(tmp_db.get_all_cards()) == 1
        # And the new values were applied.
        updated = tmp_db.get_card(sample_card.bank_id, sample_card.card_slug)
        assert updated is not None
        assert updated.card_name == "Regalia V2"
        assert updated.network == "Mastercard"
        assert updated.fees == {"joining": 0, "annual": 5000}

    def test_save_handles_missing_optional_fields(self, tmp_db: CardRepository) -> None:
        minimal = CardRecord(
            bank_id="icici",
            card_slug="icici-coral",
            card_name="Coral Debit Card",
            card_type="debit",
            network="RuPay",
        )
        tmp_db.save_card(minimal)
        fetched = tmp_db.get_card("icici", "icici-coral")
        assert fetched is not None
        assert fetched.image_url is None
        assert fetched.source_url is None
        assert fetched.fees == {}
        assert fetched.rewards == {}


class TestSaveCards:
    def test_bulk_insert(self, tmp_db: CardRepository, sample_cards: list[CardRecord]) -> None:
        written = tmp_db.save_cards(sample_cards)
        assert written == len(sample_cards)
        assert len(tmp_db.get_all_cards()) == len(sample_cards)

    def test_bulk_upsert_preserves_unique_keys(
        self, tmp_db: CardRepository, sample_cards: list[CardRecord]
    ) -> None:
        tmp_db.save_cards(sample_cards)
        # Re-save with one mutated record — should still result in 3 rows.
        sample_cards[0].card_name = "Regalia Updated"
        tmp_db.save_cards(sample_cards)

        all_cards = tmp_db.get_all_cards()
        assert len(all_cards) == 3
        names = {c.card_name for c in all_cards}
        assert "Regalia Updated" in names

    def test_bulk_insert_empty_list(self, tmp_db: CardRepository) -> None:
        assert tmp_db.save_cards([]) == 0
        assert tmp_db.get_all_cards() == []


# --------------------------------------------------------------------------- #
# Read
# --------------------------------------------------------------------------- #
class TestGetCard:
    def test_returns_none_when_missing(self, tmp_db: CardRepository) -> None:
        assert tmp_db.get_card("hdfc", "ghost") is None

    def test_round_trip_preserves_all_fields(
        self, tmp_db: CardRepository, sample_card: CardRecord
    ) -> None:
        tmp_db.save_card(sample_card)
        fetched = tmp_db.get_card(sample_card.bank_id, sample_card.card_slug)
        assert fetched == sample_card


class TestGetAllCards:
    def test_empty_database(self, tmp_db: CardRepository) -> None:
        assert tmp_db.get_all_cards() == []

    def test_returns_all_cards(
        self, tmp_db: CardRepository, sample_cards: list[CardRecord]
    ) -> None:
        tmp_db.save_cards(sample_cards)
        assert len(tmp_db.get_all_cards()) == len(sample_cards)

    def test_ordered_by_bank_then_name(
        self, tmp_db: CardRepository, sample_cards: list[CardRecord]
    ) -> None:
        tmp_db.save_cards(sample_cards)
        all_cards = tmp_db.get_all_cards()
        bank_ids = [c.bank_id for c in all_cards]
        # HDFC cards must come before the SBI card (alphabetical by bank_id).
        assert bank_ids == sorted(bank_ids)


class TestCardExists:
    def test_true_for_existing(self, tmp_db: CardRepository, sample_card: CardRecord) -> None:
        tmp_db.save_card(sample_card)
        assert tmp_db.card_exists(sample_card.bank_id, sample_card.card_slug) is True

    def test_false_for_missing(self, tmp_db: CardRepository) -> None:
        assert tmp_db.card_exists("ghost-bank", "ghost-card") is False


# --------------------------------------------------------------------------- #
# Update
# --------------------------------------------------------------------------- #
class TestUpdateCard:
    def test_updates_existing_card(
        self, tmp_db: CardRepository, sample_card: CardRecord
    ) -> None:
        tmp_db.save_card(sample_card)
        sample_card.card_name = "Regalia Gold"
        sample_card.fees = {"annual": 3000}
        result = tmp_db.update_card(sample_card)
        assert result is True

        fetched = tmp_db.get_card(sample_card.bank_id, sample_card.card_slug)
        assert fetched is not None
        assert fetched.card_name == "Regalia Gold"
        assert fetched.fees == {"annual": 3000}

    def test_update_missing_returns_false(self, tmp_db: CardRepository) -> None:
        ghost = CardRecord(
            bank_id="ghost",
            card_slug="ghost",
            card_name="Ghost",
            card_type="credit",
            network="Visa",
        )
        assert tmp_db.update_card(ghost) is False
        assert tmp_db.get_all_cards() == []


# --------------------------------------------------------------------------- #
# Delete
# --------------------------------------------------------------------------- #
class TestDeleteCard:
    def test_deletes_existing(
        self, tmp_db: CardRepository, sample_card: CardRecord
    ) -> None:
        tmp_db.save_card(sample_card)
        assert tmp_db.delete_card(sample_card.bank_id, sample_card.card_slug) is True
        assert tmp_db.get_card(sample_card.bank_id, sample_card.card_slug) is None
        assert tmp_db.get_all_cards() == []

    def test_delete_missing_returns_false(self, tmp_db: CardRepository) -> None:
        assert tmp_db.delete_card("ghost", "ghost") is False


# --------------------------------------------------------------------------- #
# JSON columns
# --------------------------------------------------------------------------- #
class TestJsonColumns:
    def test_complex_fees_round_trip(self, tmp_db: CardRepository) -> None:
        card = CardRecord(
            bank_id="axis",
            card_slug="axis-flipkart",
            card_name="Flipkart Card",
            card_type="credit",
            network="Visa",
            fees={
                "joining": 500,
                "annual": {"first_year": 0, "subsequent": 500},
                "extras": ["lounge", "insurance"],
            },
            rewards={"accelerated": {"flipkart": 5, "myntra": 4}},
        )
        tmp_db.save_card(card)
        fetched = tmp_db.get_card(card.bank_id, card.card_slug)
        assert fetched is not None
        assert fetched.fees["annual"]["first_year"] == 0
        assert fetched.fees["extras"] == ["lounge", "insurance"]
        assert fetched.rewards["accelerated"]["flipkart"] == 5

    def test_json_columns_actually_stored_as_text(self, tmp_db: CardRepository) -> None:
        card = CardRecord(
            bank_id="sbi",
            card_slug="sbi-test",
            card_name="Test",
            card_type="credit",
            network="Visa",
            fees={"x": 1},
        )
        tmp_db.save_card(card)
        with tmp_db.connect() as conn:
            row = conn.execute(
                "SELECT fees FROM cards WHERE bank_id = ? AND card_slug = ?",
                (card.bank_id, card.card_slug),
            ).fetchone()
        # SQLite's typing is dynamic, but we know we wrote a string.
        assert isinstance(row["fees"], str)
        assert row["fees"].startswith("{")
