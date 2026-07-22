# Indian Bank Card Scraper

Production-grade scraper that collects debit/credit card information
from official Indian bank websites for the **Money360** fintech platform.

> **Current sprint:** Architecture & scaffolding only. No scraping,
> database, or image-download logic is implemented yet.

See [`docs/architecture.md`](docs/architecture.md) for the design intent
behind the layout.

## Folder map

```
indian-bank-card-scraper/
├── main.py                 # Entry point — boots logging & controller.
├── controller.py           # Orchestrator: decides what runs, in what order.
├── config.py               # Centralized settings (paths, timeouts, flags).
├── models.py               # Canonical domain types (e.g. CardRecord).
├── database.py             # SQLite repository (thin abstraction over SQL).
├── downloader.py           # Streams card images to disk with retry logic.
├── validator.py            # Schema + business rules for scraped records.
│
├── parsers/                # HTML -> CardRecord. One file per bank.
│   ├── __init__.py
│   └── base.py
│
├── bank_modules/           # Per-bank glue: URLs, pagination, quirks.
│   ├── __init__.py
│   └── base.py
│
├── images/raw/             # Downloaded images, unmodified.
├── database/               # SQLite file lives here.
├── logs/                   # Rotating log files.
├── scripts/                # Manual integration test scripts (not pytest).
├── tests/                  # Pytest suite, mirrors the source tree.
├── docs/                   # Architecture notes, runbooks, ADRs.
└── requirements.txt        # Pinned dependencies for v1.
```

## File responsibilities

| File / Folder          | Responsibility                                                                 |
|------------------------|--------------------------------------------------------------------------------|
| `main.py`              | Bootstrap: ensure dirs, configure logging, instantiate controller, run, exit.  |
| `config.py`            | Immutable `Settings` dataclass + env-var overrides.                            |
| `controller.py`        | Picks active banks, loads each bank module, runs the parse->validate->save pipeline. |
| `models.py`            | Canonical domain types. `CardRecord` lives here.                               |
| `database.py`          | `CardRepository`: open/close connections, schema bootstrap, `upsert_card`.     |
| `downloader.py`        | Streams images to disk, retries transient failures, validates the file is an image. |
| `validator.py`         | `validate_card()` returns a `ValidationResult(is_valid, errors)`.              |
| `parsers/`             | HTML -> `list[CardRecord]`. Pure functions, no I/O.                            |
| `parsers/base.py`      | `BaseParser` interface. `CardRecord` re-exported from `models.py`.             |
| `bank_modules/`        | Per-bank orchestration: knows listing URLs, pagination, bank-specific quirks.  |
| `bank_modules/base.py` | `BaseBankModule` ABC every concrete bank inherits.                             |
| `images/raw/`          | Untouched downloaded card images.                                              |
| `database/`            | SQLite database file location.                                                 |
| `logs/`                | `scraper.log` and friends.                                                     |
| `scripts/`             | Manual integration-test scripts (run by hand, not by pytest).                  |
| `tests/`               | Pytest suite, mirrors source tree.                                             |
| `docs/`                | Architecture decisions, runbooks.                                              |
| `requirements.txt`     | Pinned Python dependencies.                                                    |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # or .venv\Scripts\Activate.ps1 on Windows
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Manual Integration Test

A real-network smoke test for the `HttpClient`. This script is
**not** part of the pytest suite — it is meant to be run by hand to
verify that the HTTP layer can actually reach a real bank site.

```bash
python scripts/test_http_client.py
```

**Expected output (stdout):**

```
2026-07-22 18:30:01,234 | INFO     | http_client | HTTP request started: GET https://www.hdfcbank.com/personal/pay/cards (timeout=30.0s)
2026-07-22 18:30:02,891 | INFO     | http_client | HTTP response: https://www.hdfcbank.com/personal/pay/cards -> 200 (87342 bytes)

HTTP success
  URL     : https://www.hdfcbank.com/personal/pay/cards
  Chars   : 87,342
  Output  : C:\Users\USER\indian-bank-card-scraper\logs\debug\hdfc_cards.html
```

**Expected output file:** `logs/debug/hdfc_cards.html`
— a non-empty HTML document, typically starting with `<!DOCTYPE html>`
or `<html`.

The script exits with code `0` on success and `1` on any `HttpClientError`.

## Design principles

- **KISS** — simple, obvious code over clever code.
- **DRY** — shared logic in `base.py` modules, never copy-pasted.
- **Modular** — each file has one clear job.
- **Single Responsibility** — controller orchestrates, parsers parse,
  validator validates, downloader downloads, repository persists.
- **Scales from 1 to 60+ banks** — onboarding a new bank = drop a new
  parser + a new bank module. No core code changes.
