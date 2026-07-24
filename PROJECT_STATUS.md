# 🚀 Indian Bank Card Scraper

> Production-grade scraper for collecting Indian debit and credit card metadata and official images from Indian bank websites.

---

# 📌 Project Overview

## Goal

Build a scalable scraper that automatically collects:

- Bank Name
- Card Name
- Card Type (Credit / Debit / Prepaid)
- Card Network (Visa, RuPay, Mastercard, Amex, etc.)
- Official Card URL
- Official Card Image
- Fees
- Rewards
- Additional metadata

Store the data in SQLite (v1), with PostgreSQL support planned later.

---

# 🎯 Project Principles

- KISS (Keep It Simple)
- DRY (Don't Repeat Yourself)
- Single Responsibility Principle
- Build one working feature before scaling
- Architecture-first development
- Test every sprint before moving forward

---

# 🏗️ Architecture Status

**Status:** ✅ Frozen

Core Modules

```
main.py
controller.py
config.py
models.py
database.py
http_client.py
downloader.py
validator.py
parsers/
bank_modules/
tests/
scripts/
```

### Rule

Do **not** redesign or restructure the architecture unless a real implementation problem requires it.

---

# 📂 Folder Structure

```
indian-bank-card-scraper/
│
├── README.md
├── PROJECT_STATUS.md
├── CHANGELOG.md
├── requirements.txt
│
├── main.py
├── controller.py
├── config.py
├── models.py
├── database.py
├── http_client.py
├── downloader.py
├── validator.py
│
├── parsers/
├── bank_modules/
├── scripts/
├── tests/
├── docs/
│
├── database/
├── images/
└── logs/
```

---

# ✅ Completed Sprints

## Sprint 1 — Architecture

Status: ✅ Completed

Completed

- Requirement analysis
- Project planning
- Folder structure
- Architecture design
- Separation of responsibilities
- Project scaffold

---

## Sprint 2 — Database Layer

Status: ✅ Completed

Completed

- SQLite Repository
- CRUD operations
- UPSERT support
- JSON fields
- CardRecord model
- 23 Unit Tests

Result

Stable database foundation.

---

## Sprint 3.1 — HTTP Layer

Status: ✅ Completed

Completed

- Reusable HttpClient
- requests.Session support
- Structured logging
- Exception hierarchy
- Manual integration test
- Documentation
- Total Tests: **38/38 Passing**

Result

Reliable HTTP layer ready for parsing.

---

# 🔄 Current Sprint

# Sprint 3.2 — Parse HDFC Listing Page

Status: ✅ Completed

## Goal

Read the downloaded HDFC cards page and extract only:

- Card Name
- Card URL

Input

```
logs/debug/hdfc_cards.html
```

Expected Output

```python
[
    {
        "card_name": "...",
        "card_url": "..."
    }
]
```

### Scope

Allowed

- BeautifulSoup
- HTML parsing
- Unit Tests

Not Allowed

- Database
- Images
- Downloader
- Controller changes
- Card metadata
- CardRecord objects

### Discovery (Important for Future Sprints)

The page at `https://www.hdfcbank.com/personal/pay/cards` is a
**category index**, not a flat list of individual card products.
It contains exactly 7 server-rendered teasers, each pointing at a
category landing page (e.g. `/credit-cards`, `/debit-cards`,
`/millennia-cards`, `/prepaid-cards`, `/forex-cards`,
`/commercial-credit-cards`, `/business-credit-cards`).

Implications for the crawler architecture (does NOT change Sprint 3.2):

- The Sprint 3.2 parser correctly extracts those 7 category
  links as the listing's "cards" — that is faithful to the page.
- Sprint 3.3 will need to follow each of those 7 URLs to reach
  the real per-card listings. Some categories may themselves
  have subcategories or paginated lists.
- The crawler must be treated as a 2-level fan-out (category
  index → category page → individual card), not a single flat
  scrape.

Technical notes for stability:

- The page is server-rendered (Adobe AEM). No JS execution is
  required; BeautifulSoup alone is sufficient.
- The chosen selector `a.cmp-teaser__action-link.btn.btn-secondary`
  is BEM-style and stable. It excludes nav-menu anchors (which
  use different classes) and the "Read More" accordion expanders
  (`href="#"`).
- The `title` attribute on those anchors carries the "View …"
  prefix by design; the Sprint 3.2 parser preserves it verbatim.

---

# 🗺️ Development Roadmap

```
Sprint 1
Architecture
        ✅

Sprint 2
Database Layer
        ✅

Sprint 3.1
HTTP Client
        ✅

Sprint 3.2
Parse Listing Page
        ✅

Sprint 3.3
Visit Individual Card Pages

Sprint 3.4
Extract Card Metadata

Sprint 3.5
Store Data in SQLite

Sprint 3.6
Download Official Images

Sprint 4
Support Multiple Banks

Sprint 5
Automation & Scheduling

Sprint 6
Production Ready
```

---

# 🧪 Test Status

Current

```
140 / 140 Tests Passing
```

Run Tests

```bash
python -m pytest -q
```

---

# 🌐 Current Bank Support

In Progress

- HDFC Bank

Upcoming

- SBI
- ICICI
- Axis
- Kotak
- Yes Bank
- Bank of Baroda
- Canara Bank
- Union Bank
- PNB
- IDFC FIRST
- IndusInd
- AU Small Finance Bank
- Others

---

# 📋 Development Rules

Always

- Keep functions small.
- Write tests.
- Commit after every completed sprint.
- Do not introduce unnecessary complexity.
- Keep modules independent.

Never

- Rewrite completed modules without a valid reason.
- Mix responsibilities.
- Break existing tests.

---

# 🔀 Git Workflow

After every completed sprint

```bash
git add .
git commit -m "<meaningful commit message>"
git push
```

---

# 📝 Session Handoff

## Last Completed

Sprint 3.2 — Parse HDFC Listing Page

Completed

- Pure `parsers/hdfc.py` parser (no I/O, no normalization)
- `parse_listing(html) -> list[dict]` returning `{card_name, card_url}`
- Verbatim extraction (e.g. "View Credit Cards" → "/credit-cards")
- 19 unit tests against the real saved HTML + synthetic edge cases
- Manual verification script `scripts/parse_hdfc_listing.py`
- Discovery: the HDFC page is a 7-item category index, not a
  flat individual-card list. Sprint 3.3 must fan out to each
  category URL.
- 57/57 tests passing

---
 ## Sprint 3.3 ✅ Complete

### Completed
- Downloaded HDFC Credit Cards category page.
- Built `parsers/hdfc_credit_cards.py`.
- Extracted 45 unique credit cards.
- Preserved `/coming-soon` entries.
- Skipped placeholder CTA cards.
- Deduplicated by URL while preserving order.
- Added manual parser verification script.
- Added 10 parser unit tests.
- Full test suite passing (67 tests).

### Discovery
The HDFC Credit Cards page is server-rendered and contains 45 individual card entries inside repeated `div.card-wrap` elements.

## Last Successful Test

```
57 / 57 Passed

67 / 67 Passed
```

---

## Last Commit

```
feat(http): implement reusable HTTP client and integration test
```
feat(parser): add HDFC credit cards parser and tests
---

## Resume Prompt

Read PROJECT_STATUS.md first.

Understand the current architecture and current sprint.

Do not redesign completed modules.

Do not modify completed sprints unless fixing a bug.

Continue only from the next unfinished sprint.

Preserve backward compatibility.

Keep all existing tests passing.

After implementing each sprint:
1. Run the relevant parser manually.
2. Run the full pytest suite.
3. Update PROJECT_STATUS.md and CHANGELOG.md.
4. Stop and report before starting the next sprint.
```

---

Last Updated

**24 July 2026**

---

## Sprint 3.6 ✅ Complete

### Completed
- `image_downloader.py` with `ImageDownloader` class.
- Reuses the existing `HttpClient` (extended with a small additive
  `get_bytes` method for binary payloads — the original `.get()` text
  method is untouched).
- Saves under `images/raw/<bank_id>/<card_slug>.<ext>`. Extension is
  derived from the URL path / `?fmt=` query and falls back to `.webp`.
- Skips downloads whose target file already exists (idempotent).
- Handles timeouts, connection errors, HTTP 4xx/5xx, empty bodies,
  and invalid (non-image) responses.
- Structured logging consistent with the rest of the project.
- 49 new unit tests covering: success, file-already-present skip,
  timeout, HTTP error, connection error, invalid content, empty URL,
  invalid scheme/host, plus helpers for extension / slug / magic-byte
  sniffing.
- `scripts/download_hdfc_images.py` end-to-end runner: loads
  `logs/debug/hdfc_credit_cards.html`, parses all 45 cards, fetches
  every detail page via `HttpClient`, extracts `image_url` with
  `parsers.hdfc_card.parse_card`, and downloads every image.
- All 45 detail pages fetched against the real HDFC origin.
- 40 of 45 images downloaded successfully.

### Result
40 real WebP files under `images/raw/hdfc/`. Total project tests:
**140/140 passing** (91 prior + 49 new).

### Discovery (impacts future sprints)
- 5 detail pages have **no `image_url`** at all on the hero
  selector used by `parsers/hdfc_card`. Affected cards:
  Pixel Play, Diners Club Black Metal Edition, Pixel Go,
  Swiggy HDFC Bank, and HDFC Bank H-O-G Diners Club.
  Their `div.pd-banner img.cmp-image__image` is absent from the
  markup. Future sprint: add a fallback selector (e.g. an
  `<meta property="og:image">` tag, or a "compare-card" image
  elsewhere on the page) and re-run the downloader.
- HDFC aliases one URL to a sub-page: the listing's
  `/credit-cards/platinum-edge-credit-card` resolves to a canonical
  `.../platinum-edge-credit-card/fees-and-charges`, so the parser
  derives the slug `fees-and-charges`. The downloaded image is
  real but the filename does not match the listing's card name.
  Future sprint: cross-reference the slug against the listing
  entry's URL to disambiguate.
- HDFC's CDN serves the same 4448-byte WebP to three different
  cards (Diners Black, Diners Privilege, Regalia Activ). Likely a
  generic placeholder, not a data-corruption issue. No code action
  needed; flag for manual review of those three card pages.
- The new `HttpClient.get_bytes` method is the only addition to
  `http_client.py`. It reuses the same session, headers, timeout,
  and exception mapping as `.get()`. No changes to
  `database.py`, `models.py`, `controller.py`, or `main.py`.
