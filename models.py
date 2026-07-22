"""
models.py
---------
Canonical domain models for the scraper.

This is the single source of truth for data shapes that flow between
layers (parser -> validator -> downloader -> repository). Other modules
must import from here, not define their own copies.

The re-export from parsers.base is preserved for backward compatibility
in Sprint 2 and will be removed in a later sprint.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class CardRecord:
    """A single scraped card, in a shape close to what the DB stores."""

    bank_id: str
    card_slug: str
    card_name: str
    card_type: str            # "debit" | "credit"
    network: str              # "Visa" | "Mastercard" | "RuPay" | ...
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    fees: dict[str, Any] = field(default_factory=dict)
    rewards: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict representation."""
        return asdict(self)
