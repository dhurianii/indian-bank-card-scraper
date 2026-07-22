"""
config.py
---------
Centralized configuration for the scraper.

All environment-dependent values (paths, URLs, timeouts, feature flags)
must live here. Do NOT hard-code values in business logic modules.

Why this exists:
- One place to change behavior without touching code in multiple files.
- Easy to swap settings for local / staging / production.
- Easy to override via environment variables in CI/CD.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # --- General ----------------------------------------------------------
    VERSION: str = "0.1.0"
    ENV: str = os.getenv("MONEY360_ENV", "development")
    LOG_LEVEL: str = os.getenv("MONEY360_LOG_LEVEL", "INFO")

    # --- Paths ------------------------------------------------------------
    IMAGES_RAW_DIR: Path = PROJECT_ROOT / "images" / "raw"
    DATABASE_DIR: Path = PROJECT_ROOT / "database"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"

    # --- Database ---------------------------------------------------------
    DATABASE_PATH: Path = DATABASE_DIR / "cards.db"

    # --- HTTP / Scraping --------------------------------------------------
    REQUEST_TIMEOUT_SECONDS: int = 30
    REQUEST_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; Money360-BankCardScraper/0.1; "
        "+https://money360.example.com/bot)"
    )
    MAX_CONCURRENT_REQUESTS: int = 5
    RETRY_ATTEMPTS: int = 3
    RETRY_BACKOFF_SECONDS: float = 2.0

    # --- Rate Limiting ----------------------------------------------------
    REQUEST_DELAY_SECONDS: float = 1.5  # polite delay between requests

    # --- Feature Flags ----------------------------------------------------
    DOWNLOAD_IMAGES: bool = os.getenv("MONEY360_DOWNLOAD_IMAGES", "true").lower() == "true"
    DRY_RUN: bool = os.getenv("MONEY360_DRY_RUN", "false").lower() == "true"

    # --- Banks ------------------------------------------------------------
    # List of bank identifiers to process. Add more here as we onboard banks.
    ACTIVE_BANKS: list[str] = field(
        default_factory=lambda: [
            # "hdfc",
            # "icici",
            # "sbi",
            # "axis",
        ]
    )


# A single shared instance that the rest of the app imports.
settings: Settings = Settings()
