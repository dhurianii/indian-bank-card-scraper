# Changelog

All notable changes to this project will be documented in this file.

This project follows a sprint-based development approach.

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