"""
main.py
-------
Entry point for the Indian Bank Card Scraper.

This file is intentionally minimal. It should:
1. Load environment variables and configuration.
2. Initialize the database connection.
3. Invoke the controller to orchestrate scraping jobs.
4. Handle graceful shutdown and logging.

DO NOT add scraping logic here. This file is only the bootstrap layer.
"""

import logging
import sys
from pathlib import Path

# Ensure the project root is in sys.path so submodules can be imported cleanly.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from controller import ScraperController


def ensure_directories() -> None:
    """Create required directories if they do not already exist."""
    for path in (settings.IMAGES_RAW_DIR, settings.DATABASE_DIR, settings.LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def configure_logging() -> None:
    """Configure root logger to write to console and to logs/scraper.log."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(PROJECT_ROOT / "logs" / "scraper.log", encoding="utf-8"),
        ],
    )


def main() -> int:
    """Run the scraper end-to-end."""
    ensure_directories()
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Indian Bank Card Scraper (v%s)", settings.VERSION)

    controller = ScraperController()
    controller.run()

    logger.info("Scraper finished cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
