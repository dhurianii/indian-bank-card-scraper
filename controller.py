"""
controller.py
-------------
The orchestrator. This is the brain of the scraper.

Responsibilities:
- Decide WHICH banks to scrape.
- For each bank, load the appropriate bank module.
- Coordinate parser -> validator -> downloader -> database write.
- Aggregate stats and surface them to logs / metrics.

The controller NEVER parses HTML, downloads images, or writes to the DB
directly. It delegates to specialized modules (Single Responsibility).
"""

import logging
from typing import Iterable

from config import settings


class ScraperController:
    """Coordinates the full scraping pipeline."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.banks: list[str] = settings.ACTIVE_BANKS

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """Run the scraper for every active bank."""
        if not self.banks:
            self.logger.warning("No active banks configured. Nothing to do.")
            return

        self.logger.info("Scraping %d bank(s): %s", len(self.banks), self.banks)
        for bank_id in self.banks:
            self.run_for_bank(bank_id)

    def run_for_bank(self, bank_id: str) -> None:
        """Run the scraper for a single bank."""
        self.logger.info("=== %s ===", bank_id)
        # TODO (next sprint): dynamically import bank module, run pipeline.

    # ------------------------------------------------------------------ #
    # Helpers (placeholders — flesh out in later sprints)
    # ------------------------------------------------------------------ #
    def _summary(self, items: Iterable) -> int:
        """Return the count of items processed. Used for logging metrics."""
        return sum(1 for _ in items)
