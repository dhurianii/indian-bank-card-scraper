"""
validator.py
------------
Single source of truth for "is this scraped card record valid enough
to persist?".

Responsibilities:
- Schema-level checks (required fields present, types correct).
- Business-level checks (card name not empty, network in allowed set,
  image URL looks like a URL, etc.).
- Returning clear, structured error messages so the controller can log
  them and decide whether to retry, skip, or fail the bank.

Why a separate module?
- The same validation rules need to run whether a card came from a
  parser, a CSV import, or a future API ingestion. Centralize them.
"""

import logging
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


REQUIRED_FIELDS: tuple[str, ...] = (
    "bank_id",
    "card_slug",
    "card_name",
    "card_type",       # "debit" | "credit"
    "network",         # "Visa" | "Mastercard" | "RuPay" | "Amex" | ...
    "source_url",
)
ALLOWED_CARD_TYPES: set[str] = {"debit", "credit"}
ALLOWED_NETWORKS: set[str] = {"Visa", "Mastercard", "RuPay", "AmericanExpress", "DinersClub"}


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: tuple[str, ...] = ()


def validate_card(card: dict[str, Any]) -> ValidationResult:
    """Validate a scraped card record. Returns a structured result."""
    # TODO (next sprint): implement the actual checks.
    logger.debug("Placeholder validator — will be implemented next sprint.")
    return ValidationResult(is_valid=True, errors=())
