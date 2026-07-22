"""
database.py
-----------
SQLite data layer for card records.

Responsibilities:
- Manage the connection lifecycle.
- Create the schema if it does not exist.
- Provide CRUD operations for CardRecord objects.
- Implement UPSERT semantics on the natural key (bank_id, card_slug).

This module is the ONLY place SQL should live. The rest of the app
interacts with the database exclusively through CardRepository.

Note: this module is deliberately small. We use the stdlib sqlite3
module so there is no extra dependency to install.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from config import settings
from models import CardRecord


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# SQL — single source of truth for the schema.
# --------------------------------------------------------------------------- #
SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS cards (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_id     TEXT    NOT NULL,
        card_slug   TEXT    NOT NULL,
        card_name   TEXT    NOT NULL,
        card_type   TEXT    NOT NULL CHECK (card_type IN ('debit', 'credit')),
        network     TEXT    NOT NULL,
        image_url   TEXT,
        source_url  TEXT,
        fees        TEXT    NOT NULL DEFAULT '{}',   -- JSON
        rewards     TEXT    NOT NULL DEFAULT '{}',   -- JSON
        extra       TEXT    NOT NULL DEFAULT '{}',   -- JSON
        created_at  TEXT    NOT NULL,
        updated_at  TEXT    NOT NULL,
        UNIQUE (bank_id, card_slug)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_cards_bank_id   ON cards(bank_id);",
    "CREATE INDEX IF NOT EXISTS idx_cards_card_type ON cards(card_type);",
    "CREATE INDEX IF NOT EXISTS idx_cards_network   ON cards(network);",
)


# Columns we read/write. Centralized to avoid SELECT * drift.
_COLUMNS: tuple[str, ...] = (
    "id",
    "bank_id",
    "card_slug",
    "card_name",
    "card_type",
    "network",
    "image_url",
    "source_url",
    "fees",
    "rewards",
    "extra",
    "created_at",
    "updated_at",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_dumps(value: dict) -> str:
    """Serialize a dict to JSON. We do NOT sort keys; preserve insertion order."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Optional[str]) -> dict:
    """Deserialize a JSON column, tolerating NULL/empty values."""
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Bad JSON in DB column, returning empty dict: %r", value[:80])
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _card_to_row(card: CardRecord, *, now: str) -> dict:
    """Convert a CardRecord into a row dict for INSERT/UPDATE."""
    return {
        "bank_id":    card.bank_id,
        "card_slug":  card.card_slug,
        "card_name":  card.card_name,
        "card_type":  card.card_type,
        "network":    card.network,
        "image_url":  card.image_url,
        "source_url": card.source_url,
        "fees":       _json_dumps(card.fees),
        "rewards":    _json_dumps(card.rewards),
        "extra":      _json_dumps(card.extra),
        "created_at": now,
        "updated_at": now,
    }


def _row_to_card(row: sqlite3.Row) -> CardRecord:
    """Convert a SQLite row into a CardRecord."""
    return CardRecord(
        bank_id=row["bank_id"],
        card_slug=row["card_slug"],
        card_name=row["card_name"],
        card_type=row["card_type"],
        network=row["network"],
        image_url=row["image_url"],
        source_url=row["source_url"],
        fees=_json_loads(row["fees"]),
        rewards=_json_loads(row["rewards"]),
        extra=_json_loads(row["extra"]),
    )


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
class CardRepository:
    """High-level data access for card records.

    A single repository instance is bound to one database file. The
    database file and schema are created lazily on construction, so a
    caller never has to remember to run DDL first.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path: Path = Path(db_path) if db_path is not None else settings.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_database()

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a SQLite connection and commit/rollback cleanly.

        Foreign keys are enabled per-connection (SQLite default is OFF).
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Schema bootstrap
    # ------------------------------------------------------------------ #
    def initialize_database(self) -> None:
        """Create the database file (if missing) and apply the schema.

        Safe to call repeatedly; every statement is idempotent
        (CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS).
        """
        with self.connect() as conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
        logger.info("Database initialized at %s", self.db_path)

    # ------------------------------------------------------------------ #
    # Create / Upsert
    # ------------------------------------------------------------------ #
    def save_card(self, card: CardRecord) -> int:
        """Insert a card, or update it if (bank_id, card_slug) already exists.

        Returns the row id of the affected row.
        """
        row = _card_to_row(card, now=_now_iso())
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO cards (
                    bank_id, card_slug, card_name, card_type, network,
                    image_url, source_url, fees, rewards, extra,
                    created_at, updated_at
                ) VALUES (
                    :bank_id, :card_slug, :card_name, :card_type, :network,
                    :image_url, :source_url, :fees, :rewards, :extra,
                    :created_at, :updated_at
                )
                ON CONFLICT(bank_id, card_slug) DO UPDATE SET
                    card_name  = excluded.card_name,
                    card_type  = excluded.card_type,
                    network    = excluded.network,
                    image_url  = excluded.image_url,
                    source_url = excluded.source_url,
                    fees       = excluded.fees,
                    rewards    = excluded.rewards,
                    extra      = excluded.extra,
                    updated_at = excluded.updated_at
                """,
                row,
            )
            return int(cur.lastrowid or 0)

    def save_cards(self, cards) -> int:
        """Insert/update many cards in a single transaction.

        Returns the number of rows written.
        """
        count = 0
        with self.connect() as conn:
            for card in cards:
                row = _card_to_row(card, now=_now_iso())
                conn.execute(
                    """
                    INSERT INTO cards (
                        bank_id, card_slug, card_name, card_type, network,
                        image_url, source_url, fees, rewards, extra,
                        created_at, updated_at
                    ) VALUES (
                        :bank_id, :card_slug, :card_name, :card_type, :network,
                        :image_url, :source_url, :fees, :rewards, :extra,
                        :created_at, :updated_at
                    )
                    ON CONFLICT(bank_id, card_slug) DO UPDATE SET
                        card_name  = excluded.card_name,
                        card_type  = excluded.card_type,
                        network    = excluded.network,
                        image_url  = excluded.image_url,
                        source_url = excluded.source_url,
                        fees       = excluded.fees,
                        rewards    = excluded.rewards,
                        extra      = excluded.extra,
                        updated_at = excluded.updated_at
                    """,
                    row,
                )
                count += 1
        return count

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def get_card(self, bank_id: str, card_slug: str) -> Optional[CardRecord]:
        """Return a single card by natural key, or None if not found."""
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM cards WHERE bank_id = ? AND card_slug = ?",
                (bank_id, card_slug),
            ).fetchone()
        return _row_to_card(row) if row else None

    def get_all_cards(self) -> list[CardRecord]:
        """Return every card in the database, ordered by bank_id then card_name."""
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM cards ORDER BY bank_id, card_name"
            ).fetchall()
        return [_row_to_card(row) for row in rows]

    def card_exists(self, bank_id: str, card_slug: str) -> bool:
        """Return True if a card with the given natural key exists."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM cards WHERE bank_id = ? AND card_slug = ? LIMIT 1",
                (bank_id, card_slug),
            ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update_card(self, card: CardRecord) -> bool:
        """Update an existing card by natural key.

        Returns True if a row was updated, False if no such card exists.
        Unlike save_card, this method does NOT insert a new row.
        """
        row = _card_to_row(card, now=_now_iso())
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE cards SET
                    card_name  = :card_name,
                    card_type  = :card_type,
                    network    = :network,
                    image_url  = :image_url,
                    source_url = :source_url,
                    fees       = :fees,
                    rewards    = :rewards,
                    extra      = :extra,
                    updated_at = :updated_at
                WHERE bank_id = :bank_id AND card_slug = :card_slug
                """,
                row,
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete_card(self, bank_id: str, card_slug: str) -> bool:
        """Delete a card by natural key. Returns True if a row was deleted."""
        with self.connect() as conn:
            cur = conn.execute(
                "DELETE FROM cards WHERE bank_id = ? AND card_slug = ?",
                (bank_id, card_slug),
            )
            return cur.rowcount > 0
