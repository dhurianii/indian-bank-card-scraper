"""
bank_modules/base.py
--------------------
Base class every concrete bank module inherits from.

A bank module knows:
- The bank's listing URLs.
- How to fetch the next page.
- Which parser to delegate HTML to.
- Any bank-specific quirks (delays, headers, retries).
"""

from abc import ABC, abstractmethod
from typing import Iterable

from models import CardRecord


class BaseBankModule(ABC):
    """Common interface for every supported bank."""

    bank_id: str = "unknown"
    display_name: str = "Unknown Bank"

    @abstractmethod
    def list_card_pages(self) -> Iterable[str]:
        """Yield source URLs for each card detail page (or listing page)."""
        raise NotImplementedError

    @abstractmethod
    def process(self) -> list[CardRecord]:
        """Fetch + parse + return all card records for this bank."""
        raise NotImplementedError
