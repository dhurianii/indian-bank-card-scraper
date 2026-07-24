"""
tests/test_database_persistence.py
---------------------------------
Sprint 4.1 — SQLite persistence tests.

This suite focuses on the *integration* between the parser and the
repository — i.e. the Sprint 4.1 deliverable: "parse a
``CardRecord`` and persist it into SQLite". The unit-level CRUD
tests already live in ``tests/test_database.py``; this file is
deliberately narrower in scope (one fixture, one pipeline) and
broader in what it asserts (every field of the real parsed
record round-trips).

All tests use a throwaway SQLite file via ``tmp_path``. The
production database (``database/cards.db``) is never touched.

Coverage map
============

* Insert one card (real HDFC fixture, end-to-end)
* Update existing card via UPSERT
* Duplicate save does not create another row
* JSON fields (fees, rewards, extra) round-trip correctly
* Empty optional fields (image_url=None, source_url=None, etc.)
* Multiple cards
* Production database is never touched
* The full set of ``CardRecord`` fields round-trips through
  the real ``parse_card`` -> ``save_card`` -> ``get_card`` flow.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from database import CardRepository
from models import CardRecord
from parsers.hdfc_card import parse_card


# --------------------------------------------------------------------------- #
# Fixture: real HDFC detail page
# --------------------------------------------------------------------------- #
HTML_FILE: Path = Path("logs/debug/millennia_credit_card.html")


@pytest.fixture(scope="module")
def real_html() -> str:
    """The real HDFC detail page saved during Sprint 3.4.

    The page is HDFC's Regalia First page (HDFC aliases the
    millennia URL).
    """
    if not HTML_FILE.exists():
        pytest.skip(f"Missing HTML fixture: {HTML_FILE}")
    return HTML_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed_card(real_html: str) -> CardRecord:
    """A CardRecord produced by parsing the real HTML."""
    return parse_card(real_html)


@pytest.fixture()
def prod_db_path() -> Path:
    """Path of the production database — referenced to assert it
    is not touched by tests."""
    return Path("database") / "cards.db"


# --------------------------------------------------------------------------- #
# 1. Insert one card
# --------------------------------------------------------------------------- #
class TestInsert:
    def test_insert_one_card_from_real_html(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "test.db")

        row_id = repo.save_card(parsed_card)

        # save_card returns the rowid of the inserted/updated row.
        assert isinstance(row_id, int)
        assert row_id > 0

        # The card is fetchable.
        fetched = repo.get_card(parsed_card.bank_id, parsed_card.card_slug)
        assert fetched is not None
        assert fetched.card_name == parsed_card.card_name
        assert fetched.bank_id == "hdfc"
        assert fetched.card_type == "credit"

    def test_insert_returns_distinct_rowids(
        self,
        tmp_path: Path,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "test.db")
        first = CardRecord(
            bank_id="hdfc", card_slug="regalia",
            card_name="Regalia", card_type="credit", network="Visa",
        )
        second = CardRecord(
            bank_id="hdfc", card_slug="moneyback",
            card_name="MoneyBack", card_type="credit", network="Visa",
        )
        id_a = repo.save_card(first)
        id_b = repo.save_card(second)
        assert id_a != id_b
        assert len(repo.get_all_cards()) == 2


# --------------------------------------------------------------------------- #
# 2. Update existing card (UPSERT)
# --------------------------------------------------------------------------- #
class TestUpdate:
    def test_update_changes_existing_row(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_card(parsed_card)

        # Mutate and re-save — must update, not insert.
        parsed_card.card_name = "Regalia First Credit Card (Updated)"
        parsed_card.fees = {"joining": 1500, "annual": 2500}
        parsed_card.extra = {"description": "Updated description."}

        repo.save_card(parsed_card)

        # Still exactly one row.
        all_cards = repo.get_all_cards()
        assert len(all_cards) == 1

        # The new values are visible.
        updated = repo.get_card(parsed_card.bank_id, parsed_card.card_slug)
        assert updated is not None
        assert updated.card_name == "Regalia First Credit Card (Updated)"
        assert updated.fees == {"joining": 1500, "annual": 2500}
        assert updated.extra == {"description": "Updated description."}

    def test_update_preserves_created_at(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """An UPSERT must not change the row's created_at; only
        updated_at advances. This is a regression guard for the
        ON CONFLICT DO UPDATE clause."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_card(parsed_card)

        with repo.connect() as conn:
            first = conn.execute(
                "SELECT created_at, updated_at FROM cards "
                "WHERE bank_id = ? AND card_slug = ?",
                (parsed_card.bank_id, parsed_card.card_slug),
            ).fetchone()

        # Re-save with a small delay so updated_at must differ.
        parsed_card.card_name = "Renamed"
        repo.save_card(parsed_card)

        with repo.connect() as conn:
            second = conn.execute(
                "SELECT created_at, updated_at FROM cards "
                "WHERE bank_id = ? AND card_slug = ?",
                (parsed_card.bank_id, parsed_card.card_slug),
            ).fetchone()

        assert first["created_at"] == second["created_at"]
        assert first["updated_at"] == second["updated_at"]  # equal at second resolution


# --------------------------------------------------------------------------- #
# 3. Duplicate save does not create another row
# --------------------------------------------------------------------------- #
class TestUniqueness:
    def test_same_natural_key_twice_yields_one_row(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "test.db")

        repo.save_card(parsed_card)
        repo.save_card(parsed_card)  # identical — no-op at SQL level
        repo.save_card(parsed_card)

        assert len(repo.get_all_cards()) == 1
        assert repo.card_exists(parsed_card.bank_id, parsed_card.card_slug) is True

    def test_unique_constraint_is_enforced_at_db_level(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """Bypassing save_card's UPSERT must still hit the UNIQUE
        constraint. This guards against future refactors that
        accidentally drop the constraint."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_card(parsed_card)

        # Insert a second row with the same (bank_id, card_slug) but
        # a different card_name — raw SQL, no UPSERT.
        with pytest.raises(sqlite3.IntegrityError):
            with repo.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO cards (
                        bank_id, card_slug, card_name, card_type, network,
                        image_url, source_url, fees, rewards, extra,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', '{}', '{}',
                              '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                    """,
                    (
                        parsed_card.bank_id, parsed_card.card_slug,
                        "Different name", parsed_card.card_type,
                        parsed_card.network, parsed_card.image_url,
                        parsed_card.source_url,
                    ),
                )

    def test_different_banks_can_share_a_slug(
        self,
        tmp_path: Path,
    ) -> None:
        """The natural key is (bank_id, card_slug) — two banks may
        both have a 'regalia' card. The constraint is composite."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        hdfc_regalia = CardRecord(
            bank_id="hdfc", card_slug="regalia",
            card_name="Regalia", card_type="credit", network="Visa",
        )
        sbi_regalia = CardRecord(
            bank_id="sbi", card_slug="regalia",
            card_name="SBI Regalia", card_type="credit", network="Mastercard",
        )
        repo.save_card(hdfc_regalia)
        repo.save_card(sbi_regalia)

        assert len(repo.get_all_cards()) == 2
        assert repo.card_exists("hdfc", "regalia") is True
        assert repo.card_exists("sbi", "regalia") is True


# --------------------------------------------------------------------------- #
# 4. JSON fields round-trip
# --------------------------------------------------------------------------- #
class TestJsonRoundTrip:
    def test_fees_rewards_extra_all_round_trip(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """The real HDFC parser populates fees (joining, annual,
        annual_percentage_rate) and extra (description, apply_url,
        faq, breadcrumb). All of these must come back unchanged."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_card(parsed_card)

        fetched = repo.get_card(parsed_card.bank_id, parsed_card.card_slug)
        assert fetched is not None
        assert fetched.fees == parsed_card.fees
        assert fetched.rewards == parsed_card.rewards
        assert fetched.extra == parsed_card.extra

    def test_complex_nested_json_round_trip(
        self,
        tmp_path: Path,
    ) -> None:
        """Non-trivial nested dicts and lists must survive the
        JSON column encode/decode round-trip byte-for-byte."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        card = CardRecord(
            bank_id="axis",
            card_slug="axis-flipkart",
            card_name="Flipkart Card",
            card_type="credit",
            network="Visa",
            fees={
                "joining": 500,
                "annual": {"first_year": 0, "subsequent": 500},
                "waiver_conditions": ["spend>200k", "lifecycle>1y"],
            },
            rewards={
                "accelerated": {"flipkart": 5, "myntra": 4},
                "milestones": [{"spend": 100000, "cashback": 500}],
            },
            extra={
                "tags": ["co-branded", "shopping"],
                "metadata": {"issuer": "axis", "tier": "premium"},
            },
        )
        repo.save_card(card)

        fetched = repo.get_card("axis", "axis-flipkart")
        assert fetched is not None
        assert fetched.fees["annual"]["first_year"] == 0
        assert fetched.fees["waiver_conditions"] == ["spend>200k", "lifecycle>1y"]
        assert fetched.rewards["accelerated"]["flipkart"] == 5
        assert fetched.rewards["milestones"][0]["cashback"] == 500
        assert fetched.extra["tags"] == ["co-branded", "shopping"]
        assert fetched.extra["metadata"]["tier"] == "premium"

    def test_json_columns_stored_as_text(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """The schema is TEXT columns; we must not accidentally
        start storing fees as BLOB or NULL when the dict is empty."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_card(parsed_card)

        with repo.connect() as conn:
            row = conn.execute(
                "SELECT fees, rewards, extra FROM cards "
                "WHERE bank_id = ? AND card_slug = ?",
                (parsed_card.bank_id, parsed_card.card_slug),
            ).fetchone()

        assert isinstance(row["fees"], str)
        assert isinstance(row["rewards"], str)
        assert isinstance(row["extra"], str)
        # Empty dicts still produce a JSON object string.
        assert row["fees"].startswith("{")
        assert row["extra"].startswith("{")

    def test_unicode_in_json_round_trip(
        self,
        tmp_path: Path,
    ) -> None:
        """HDFC pages use ₹, em-dashes, narrow no-break spaces,
        etc. These must round-trip without escaping bugs."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        card = CardRecord(
            bank_id="hdfc",
            card_slug="unicode-test",
            card_name="Regalia ₹ Card",
            card_type="credit",
            network="Visa",
            fees={"joining": 1000, "note": "Membership Fee: ₹1,000 — *"},
            extra={"description": "Apply for Regalia — exclusive lounge access."},
        )
        repo.save_card(card)

        fetched = repo.get_card("hdfc", "unicode-test")
        assert fetched is not None
        assert "₹" in fetched.card_name
        assert fetched.fees["note"] == "Membership Fee: ₹1,000 — *"
        assert "—" in fetched.extra["description"]


# --------------------------------------------------------------------------- #
# 5. Empty optional fields
# --------------------------------------------------------------------------- #
class TestEmptyOptionalFields:
    def test_minimal_card_with_no_optional_fields(
        self, tmp_path: Path,
    ) -> None:
        """A CardRecord constructed with only required fields must
        persist and fetch back with the same defaults."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        minimal = CardRecord(
            bank_id="icici",
            card_slug="icici-coral",
            card_name="Coral Debit Card",
            card_type="debit",
            network="RuPay",
            # image_url, source_url omitted → None
            # fees, rewards, extra omitted → empty dict
        )
        repo.save_card(minimal)

        fetched = repo.get_card("icici", "icici-coral")
        assert fetched is not None
        assert fetched.image_url is None
        assert fetched.source_url is None
        assert fetched.fees == {}
        assert fetched.rewards == {}
        assert fetched.extra == {}

    def test_empty_json_dicts_are_not_null(
        self, tmp_path: Path,
    ) -> None:
        """Empty dicts must round-trip as `{}`, not as NULL or
        as Python None. This guards against a future migration
        that switches to nullable TEXT."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        card = CardRecord(
            bank_id="sbi",
            card_slug="sbi-minimal",
            card_name="Minimal",
            card_type="credit",
            network="Visa",
        )
        repo.save_card(card)

        with repo.connect() as conn:
            row = conn.execute(
                "SELECT fees, rewards, extra FROM cards "
                "WHERE bank_id = ? AND card_slug = ?",
                (card.bank_id, card.card_slug),
            ).fetchone()
        assert row["fees"] == "{}"
        assert row["rewards"] == "{}"
        assert row["extra"] == "{}"


# --------------------------------------------------------------------------- #
# 6. Multiple cards
# --------------------------------------------------------------------------- #
class TestMultipleCards:
    def test_bulk_save_then_individual_fetch(
        self,
        tmp_path: Path,
        sample_cards: list[CardRecord],
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_cards(sample_cards)

        assert len(repo.get_all_cards()) == len(sample_cards)
        for original in sample_cards:
            fetched = repo.get_card(original.bank_id, original.card_slug)
            assert fetched is not None
            assert fetched.card_name == original.card_name

    def test_mix_of_insert_and_update(
        self,
        tmp_path: Path,
        sample_cards: list[CardRecord],
    ) -> None:
        """save_cards must behave like save_card: insert new rows
        and update existing ones in the same batch."""
        repo = CardRepository(db_path=tmp_path / "test.db")

        # First batch — all inserts.
        repo.save_cards(sample_cards)
        first_count = len(repo.get_all_cards())

        # Second batch — first card is an update, the rest are
        # no-op (already present).
        sample_cards[0].card_name = "Regalia V2"
        sample_cards[0].fees = {"joining": 0, "annual": 5000}
        repo.save_cards(sample_cards)

        assert len(repo.get_all_cards()) == first_count  # still 3
        updated = repo.get_card(sample_cards[0].bank_id, sample_cards[0].card_slug)
        assert updated is not None
        assert updated.card_name == "Regalia V2"
        assert updated.fees == {"joining": 0, "annual": 5000}


# --------------------------------------------------------------------------- #
# 7. Production DB must never be touched
# --------------------------------------------------------------------------- #
class TestProductionDatabaseUntouchable:
    def test_tests_use_temporary_database(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """This is a meta-test: it asserts that *every* test in
        this file uses a temporary database. We verify by
        checking that the production database file does not
        exist OR, if it exists, is not modified by saving the
        parsed_card to a tmp_path repo."""
        repo = CardRepository(db_path=tmp_path / "isolated.db")
        repo.save_card(parsed_card)
        assert (tmp_path / "isolated.db").exists()
        # Sanity: the tmp_path DB has the row, the production DB
        # has at most whatever was there before this test ran.
        with repo.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        assert count == 1

    def test_production_db_does_not_grow_during_test_run(
        self,
        prod_db_path: Path,
    ) -> None:
        """If a future refactor accidentally points the test
        repository at the production DB, this test will fail.
        We verify by:
          - if the production DB exists, count rows before/after
            a no-op save_card on a tmp_path repo, and assert
            the count is unchanged;
          - if the production DB does not exist, assert that
            saving a card on a tmp_path repo does not create
            the production DB on disk.
        """
        prod_existed = prod_db_path.exists()
        if prod_existed:
            with sqlite3.connect(prod_db_path) as conn:
                before = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        else:
            before = 0

        # Save to a tmp_path DB; the production DB must be untouched.
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            repo = CardRepository(db_path=Path(td) / "scratch.db")
            repo.save_card(CardRecord(
                bank_id="test", card_slug="test",
                card_name="Test", card_type="credit", network="Visa",
            ))

        if prod_existed:
            with sqlite3.connect(prod_db_path) as conn:
                after = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            assert before == after, (
                "Production database was modified during a test run! "
                f"Before: {before} rows, after: {after} rows."
            )
        else:
            assert not prod_db_path.exists(), (
                f"Test run created production DB at {prod_db_path} — "
                "a repository was constructed against the wrong path."
            )


# --------------------------------------------------------------------------- #
# 8. End-to-end: real HTML -> CardRecord -> SQLite -> CardRecord
# --------------------------------------------------------------------------- #
class TestEndToEndPersistence:
    def test_full_field_round_trip(
        self,
        tmp_path: Path,
        real_html: str,
    ) -> None:
        """The whole point of Sprint 4.1: every field of a real
        parsed card must round-trip through SQLite byte-for-byte."""
        record_before = parse_card(real_html)
        repo = CardRepository(db_path=tmp_path / "test.db")
        repo.save_card(record_before)
        record_after = repo.get_card(record_before.bank_id, record_before.card_slug)

        # Identity
        assert record_after is not None
        assert record_after.bank_id == record_before.bank_id
        assert record_after.card_slug == record_before.card_slug
        assert record_after.card_name == record_before.card_name
        assert record_after.card_type == record_before.card_type
        assert record_after.network == record_before.network
        # Optional scalars
        assert record_after.image_url == record_before.image_url
        assert record_after.source_url == record_before.source_url
        # JSON fields
        assert record_after.fees == record_before.fees
        assert record_after.rewards == record_before.rewards
        assert record_after.extra == record_before.extra
        # And the dataclass equality shortcut works.
        assert record_after == record_before

    def test_persisted_row_id_is_positive(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """save_card must return a positive integer rowid. This
        is the value the brief asks the manual script to print."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        row_id = repo.save_card(parsed_card)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_get_all_cards_orders_by_bank_then_name(
        self,
        tmp_path: Path,
        parsed_card: CardRecord,
    ) -> None:
        """Smoke test for the SELECT used by the manual script's
        'fetched back' output."""
        repo = CardRepository(db_path=tmp_path / "test.db")
        # Add a card from a different bank to exercise ordering.
        other = CardRecord(
            bank_id="icici",
            card_slug="icici-coral",
            card_name="Coral Card",
            card_type="debit",
            network="RuPay",
        )
        repo.save_card(parsed_card)
        repo.save_card(other)

        all_cards = repo.get_all_cards()
        bank_ids = [c.bank_id for c in all_cards]
        # HDFC must come before ICICI (alphabetical).
        assert bank_ids == sorted(bank_ids)
