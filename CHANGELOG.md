# Changelog

All notable changes to this project will be documented in this file.

This project follows a sprint-based development approach.

---

## Sprint 4.1 - SQLite Persistence (24 July 2026)

### Added
- `tests/test_database_persistence.py` — 20 new tests focused on
  the parser-to-DB integration.
- `scripts/test_database.py` — manual verification script that
  loads the real HDFC detail page, parses it, saves it into a
  dedicated SQLite file, reads it back, and prints every field
  and the raw JSON columns.

### Implemented
- Confirmed end-to-end that `parsers.hdfc_card.parse_card(html)
  -> CardRepository.save_card(record) -> CardRepository.get_card(...)`
  round-trips every field of a real HDFC card.
- Confirmed that JSON fields (`fees`, `rewards`, `extra`) survive
  byte-for-byte through the database, including nested dicts,
  lists, and Unicode (₹, em-dashes, narrow no-break spaces).
- Confirmed that `ON CONFLICT(bank_id, card_slug) DO UPDATE SET`
  preserves the original `created_at` while updating `updated_at`
  and every other column.
- Confirmed that the production `database/cards.db` is never
  touched by tests or by the manual script.

### Migration
**None required.** The Sprint 2 schema already stores every
field of `CardRecord` plus `created_at` / `updated_at`, with
composite `UNIQUE(bank_id, card_slug)`. JSON columns are
`TEXT NOT NULL DEFAULT '{}'`. The Sprint 4.1 deliverable is
the test/script coverage, not new SQL.

### SQL (unchanged from Sprint 2)
```sql
CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id     TEXT    NOT NULL,
    card_slug   TEXT    NOT NULL,
    card_name   TEXT    NOT NULL,
    card_type   TEXT    NOT NULL CHECK (card_type IN ('debit', 'credit')),
    network     TEXT    NOT NULL,
    image_url   TEXT,
    source_url  TEXT,
    fees        TEXT    NOT NULL DEFAULT '{}',
    rewards     TEXT    NOT NULL DEFAULT '{}',
    extra       TEXT    NOT NULL DEFAULT '{}',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE (bank_id, card_slug)
);
```

### Testing
- 20 new tests in `tests/test_database_persistence.py`.
- Total project tests: **160 / 160 passing** (140 prior + 20 new).

### Changed
- No code changes. `database.py`, `models.py`,
  `http_client.py`, `image_downloader.py`, `controller.py`, and
  `main.py` are all untouched.

### Fixed
- None.

### Discovery
- `save_card` returns a positive integer rowid. The Sprint 4
  architecture's `BankScraper` interface should expose this so
  the controller can log "inserted row N" without an extra
  `SELECT`.
- A regression-guard test
  (`test_production_db_does_not_grow_during_test_run`) protects
  the production `database/cards.db` from accidental writes by
  future test suites. It works in two modes: when the
  production DB exists, it asserts the row count is unchanged
  after a `tmp_path` repo save; when it does not exist, it
  asserts it is still not on disk after the test.

---

## Sprint 3.6 - Image Downloader (24 July 2026)

### Added
- `image_downloader.py` — new `ImageDownloader` class.
- `tests/test_image_downloader.py` — 49 unit tests.
- `scripts/download_hdfc_images.py` — end-to-end runner that parses
  the saved listing, fetches every detail page, extracts
  `image_url`, and downloads the image.

### Implemented
- Reuses the existing `HttpClient` (Sprint 3.1). Added a small
  additive `HttpClient.get_bytes(url) -> bytes` for binary payloads
  so the same session, headers, timeout, and exception mapping
  apply to image fetches.
- Saves to `images/raw/<bank_id>/<card_slug>.<ext>`. Extension is
  derived from the URL path (or `?fmt=` query) and falls back to
  `.webp` per the brief.
- Skips downloads when the target file already exists (idempotent
  re-runs).
- Returns the local `Path` on success, `None` on every failure
  mode (timeout, connection error, HTTP error, empty body,
  non-image body, empty URL, invalid URL).
- Structured logging via the project-wide `logging.getLogger`.
- New typed exceptions: `ImageDownloadError`,
  `InvalidImageUrlError`, `InvalidImageContentError`.
- Magic-byte content sniffing (RIFF/WEBP, PNG, JPEG, GIF, SVG)
  so a 200 OK HTML error page is correctly rejected.

### Discovery (impacts future sprints)
- 5 of 45 detail pages do not expose an `image_url` through the
  existing `div.pd-banner img.cmp-image__image` selector. Affected:
  Pixel Play, Diners Club Black Metal Edition, Pixel Go,
  Swiggy HDFC Bank, HDFC Bank H-O-G Diners Club. Future sprint
  should add a fallback (e.g. `<meta property="og:image">`).
- One URL is aliased by HDFC: the listing's
  `/credit-cards/platinum-edge-credit-card` resolves to a
  canonical `.../platinum-edge-credit-card/fees-and-charges`,
  so the derived slug and saved filename are `fees-and-charges`,
  not `platinum-edge-credit-card`. Future sprint: cross-reference
  against the listing's URL to recover the listing's slug.
- Three cards (Diners Black, Diners Privilege, Regalia Activ)
  receive the same 4448-byte WebP from HDFC's CDN — a generic
  placeholder, not a code bug. Manual review recommended.

### Testing
- 49 new tests in `tests/test_image_downloader.py`.
- Total project tests: **140 / 140 passing** (91 prior + 49 new).

### Changed
- `http_client.py`: added `get_bytes()` for binary downloads. The
  existing `.get()` text method is unchanged.
- No changes to `database.py`, `models.py`, `controller.py`, or
  `main.py` (per the Sprint 3.6 rules).
- No changes to any existing test file.

### Fixed
- None.

---


## Sprint 3.3 - HDFC Credit Card Parser(23/072026)

Added
- `parsers/hdfc_credit_cards.py`
- `scripts/parse_hdfc_credit_cards.py`
- `tests/test_hdfc_credit_cards_parser.py`

Implemented
- Pure HTML parser using BeautifulSoup.
- Extracted 45 unique cards.
- URL-based deduplication.
- Preserved relative URLs.
- Included `/coming-soon` cards.
- Ignored placeholder CTA cards.

Testing
- Added 10 parser tests.
- Full project test suite: 67 passing.

# Sprint 3.2 (23 July 2026)

## Added

### HDFC Listing Parser

- `parsers/hdfc.py` — pure function `parse_listing(html) -> list[dict]`
- Returns only `card_name` (from `title` attribute) and `card_url`
  (from `href` attribute), verbatim — no normalization, no
  absolutization
- Selector: `a.cmp-teaser__action-link.btn.btn-secondary`
  (AEM BEM class, stable, excludes nav menu and "Read More"
  expanders)
- Deduplicates by URL while preserving document order
- Skips entries with empty name or empty URL

### Tests

- `tests/test_hdfc_parser.py` — 19 tests
- Coverage:
  - Real saved HTML (`logs/debug/hdfc_cards.html`) — 7 cards
  - 7 card-name presence checks (all observed in the HTML)
  - 4 URL presence checks
  - Relative-URL preservation
  - "View " prefix preservation (no normalization)
  - Document order
  - URL uniqueness
  - Empty / unrelated HTML
  - Missing title / missing href
  - Deduplication
  - Selector stability vs. non-card anchors

### Manual Verification

- `scripts/parse_hdfc_listing.py` — reads the saved HTML, prints
  `Cards Found`, `Unique URLs`, and the first 10 entries

---

## Testing

- 19 new HDFC parser tests
- Total Project Tests: **57 / 57 Passing** (38 prior + 19 new)

---

## Changed

- No architecture changes
- No database changes
- No controller changes
- No downloader changes
- No HTTP client changes
- `parsers/base.py` left untouched (parser deliberately
  does not subclass it; reconciles in a later sprint)

---

## Fixed

- None

---

## Discovery (does not affect Sprint 3.2 scope)

- The HDFC `personal/pay/cards` page is a **category index**,
  not a flat individual-card listing. It contains exactly 7
  category teasers (Credit / Debit / Millennia / Prepaid /
  Forex / Commercial / Business). Sprint 3.3 must fan out to
  each category URL to reach individual card pages. Documented
  in `PROJECT_STATUS.md` under Sprint 3.2.

---

# Sprint 3.1 (22 July 2026)

## Added

### HTTP Layer

- Implemented reusable `HttpClient`
- Added persistent `requests.Session`
- Configurable timeout support
- Configurable User-Agent
- Structured request logging
- Structured response logging

### Exception Handling

- Added `HttpRequestError`
- Added `HttpResponseError`
- Proper error mapping for:
  - Connection errors
  - Timeouts
  - SSL errors
  - HTTP 4xx
  - HTTP 5xx

### Manual Integration

- Added `scripts/test_http_client.py`
- Added manual verification workflow
- Added debug HTML output

### Documentation

- Updated README
- Added manual integration testing guide

---

## Testing

- Added 15 HTTP client unit tests
- Total Project Tests: **38 / 38 Passing**

---

## Changed

- No architecture changes
- No database changes
- No parser changes

---

## Fixed

- None

---

# Sprint 2 (22 July 2026)

## Added

### Database Layer

- SQLite Repository
- Automatic schema creation
- CRUD operations
- UPSERT support
- JSON field storage
- Card existence checking
- Bulk insert support
- Bulk update support

### Data Model

- Introduced canonical `CardRecord`
- Added timestamp management
- Added JSON serialization

### Testing

- Added database fixtures
- Added repository tests
- Added JSON round-trip tests

---

## Testing

- Added 23 database tests
- Total Project Tests: **23 / 23 Passing**

---

## Changed

- Moved `CardRecord` into `models.py`
- Simplified architecture

---

## Fixed

- Removed duplicate architecture components
- Removed unnecessary scaffolding
- Removed import side effects

---

# Sprint 1 (22 July 2026)

## Added

### Project Foundation

- Project architecture
- Folder structure
- Development roadmap
- SQLite-first architecture
- Parser architecture
- Downloader architecture
- Validator architecture

### Engineering Standards

- KISS
- DRY
- Single Responsibility Principle
- Architecture-first development

---

## Testing

- Project scaffold verified

---

## Changed

- Initial project setup

---

## Fixed

- Architecture review improvements
- Configuration cleanup
- Folder organization