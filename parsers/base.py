"""
parsers/base.py
---------------
Shared building blocks for every bank-specific parser.

Why this exists:
- DRY: most bank pages share structure (listing page -> detail page).
- Single Responsibility: each concrete parser only overrides the
  parts that differ.

Note: CardRecord lives in models.py. It is re-exported here for
backward compatibility with existing imports; new code should import
from models directly.
"""

from models import CardRecord  # re-export


class BaseParser:
    """Subclass this to implement a bank-specific parser."""

    bank_id: str = "unknown"

    def parse(self, html: str, source_url: str) -> list[CardRecord]:
        """Return a list of CardRecord objects parsed from the given HTML."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement parse()")
