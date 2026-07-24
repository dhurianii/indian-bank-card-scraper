# Sprint 4 — Multi-Bank Framework Architecture

> **Status:** Proposed — design only, no code changes yet.
> **Date:** 24 July 2026
> **Author:** Architecture proposal for Sprint 4 (multi-bank support).
>
> This document is the output of Sprint 4's design phase. It proposes
> a new layout for the project, the contracts that bank modules must
> implement, and a roadmap for executing the refactor in small,
> testable sprints. **No file in the project has been modified by
> the design phase itself** — only this document has been added.

---

## 1. Why this sprint exists

After Sprints 1–3, the project can scrape HDFC end-to-end:

```
listing HTML  →  parsers/hdfc_credit_cards.py  →  45 cards
detail HTML   →  parsers/hdfc_card.py           →  CardRecord
URL           →  image_downloader.py            →  WebP on disk
CardRecord    →  database.py                    →  SQLite row
```

Everything is wired together by **ad-hoc scripts** in `scripts/`
(e.g. `download_hdfc_images.py`, `parse_hdfc_credit_cards.py`).
The controller (`controller.py`) is still a stub. There is no shared
abstraction over a "bank" — the HDFC pipeline is a collection of
discrete tools, not a single object.

**Goal of Sprint 4:** introduce a `BankScraper` abstraction that
captures the HDFC pipeline, so that adding SBI / ICICI / Axis is a
matter of writing one new bank module — not new scripts, a new
controller branch, and new glue code in every layer.

---

## 2. Goals & non-goals

### Goals

1. One **interface** (`BankScraper`) that fully describes a bank's
   pipeline.
2. One **per-bank package** (`bank_modules/<bank>/`) that implements
   that interface.
3. The existing `ScraperController` becomes a **generic orchestrator**
   that loops over `BankScraper` instances — no per-bank `if` branches.
4. **Zero regressions**: 140/140 tests still pass after the refactor.
5. No changes to `models.py`, `database.py`, `image_downloader.py`,
   or `http_client.py` (per the Sprint 4 rules).

### Non-goals (deferred to later sprints)

- Implementing SBI / ICICI / Axis scrapers. **Architecture only.**
- Resumability, retry, distributed execution.
- A REST API or web UI.
- Per-bank image deduplication or similarity detection.
- Bank-specific data quality rules beyond what the existing
  `validator.py` already does.

---

## 3. Review of the current architecture

The project today has **three layers** that already work, plus one
that does not:

| Layer | Module | State | Reusable as-is? |
|-------|--------|-------|-----------------|
| HTTP client | `http_client.py` | Done (Sprint 3.1) | **Yes** |
| Image downloader | `image_downloader.py` | Done (Sprint 3.6) | **Yes** |
| SQLite repo | `database.py`, `models.py` | Done (Sprint 2) | **Yes** |
| HDFC parser | `parsers/hdfc*.py` | Done (Sprints 3.2, 3.3, 3.5) | Per-bank only |
| Bank glue | `bank_modules/` | Empty (just a stub `BaseBankModule`) | **No** |
| Orchestrator | `controller.py` | Stub (`run_for_bank` is a TODO) | **No** |
| Entry point | `main.py` | OK | **Yes** |
| Per-bank scripts | `scripts/download_hdfc_*.py`, `scripts/parse_hdfc_*.py` | HDFC-only | **No** |

The key observation: **HDFC logic is scattered across `parsers/`,
`scripts/`, and (conceptually) the controller's TODO**. There is no
single place where someone can read "how does the HDFC pipeline work?"
— they have to assemble it from three modules and four scripts.

---

## 4. Proposed folder structure

```
indian-bank-card-scraper/
│
├── main.py
├── controller.py                 (refactored: generic orchestrator)
├── config.py
├── models.py                     (UNCHANGED)
├── database.py                   (UNCHANGED)
├── http_client.py                (UNCHANGED)
├── image_downloader.py           (UNCHANGED)
├── validator.py
│
├── bank_modules/                 (REFACTORED: one package per bank)
│   ├── __init__.py               (registry: bank_id -> BankScraper class)
│   ├── base.py                   (BankScraper ABC + shared dataclasses)
│   ├── hdfc/                     (MOVED from parsers/hdfc*.py)
│   │   ├── __init__.py           (re-exports HDFCScraper)
│   │   ├── scraper.py            (BankScraper impl: URLs, fetcher, glue)
│   │   ├── parsers.py            (PURE: listing + detail HTML -> CardRecord)
│   │   ├── selectors.py          (centralized CSS selectors / regexes)
│   │   └── urls.py               (canonical URLs, slug helpers)
│   ├── sbi/                      (STUB for Sprint 4.2)
│   │   └── __init__.py
│   ├── icici/                    (STUB for Sprint 4.3)
│   │   └── __init__.py
│   └── axis/                     (STUB for Sprint 4.4)
│       └── __init__.py
│
├── scripts/                      (SHRINKS: only generic scripts remain)
│   ├── download_bank_images.py   (replaces scripts/download_hdfc_images.py)
│   ├── parse_bank_card.py        (replaces scripts/parse_hdfc_card.py)
│   └── ...                       (one entry-point script per bank as needed)
│
├── tests/
│   ├── test_image_downloader.py  (UNCHANGED)
│   ├── test_http_client.py       (UNCHANGED)
│   ├── test_database.py          (UNCHANGED)
│   ├── bank_modules/             (NEW: per-bank test packages)
│   │   ├── hdfc/
│   │   │   ├── test_parsers.py   (MOVED from tests/test_hdfc_*.py)
│   │   │   └── test_scraper.py   (NEW: BankScraper contract tests)
│   │   └── base/
│   │       └── test_bank_scraper_contract.py  (shared interface tests)
│   └── test_controller.py        (NEW)
│
├── docs/
│   ├── architecture.md           (refreshed to match new layout)
│   └── sprint4_architecture.md   (this file)
│
├── database/
├── images/
│   └── raw/
│       ├── hdfc/                 (UNCHANGED: 40 real WebP files)
│       ├── sbi/                  (empty until Sprint 4.2)
│       ├── icici/                (empty until Sprint 4.3)
│       └── axis/                 (empty until Sprint 4.4)
│
└── logs/
```

### Rationale for each move

- **`bank_modules/<bank>/` becomes a real Python package.** A new
  bank means creating a new folder, not a new file. The folder
  boundary is the bank boundary — there is no "HDFC parser" shared
  with another bank by accident.
- **`parsers/` is retired.** Today it contains only HDFC code; once
  that moves into `bank_modules/hdfc/parsers.py`, the top-level
  `parsers/` package has nothing left and is deleted. The existing
  `parsers/base.py` (which only re-exports `CardRecord`) becomes
  redundant.
- **`selectors.py` and `urls.py` per bank** hold the bank-specific
  magic strings. This is the same pattern that
  `parsers/hdfc_card.py` already follows (it has a block of
  `SELECTOR_*` constants), now generalized and lifted out of the
  parser body so tests can reuse them without re-importing the
  parser.
- **`scripts/` shrinks to a small set of generic entry points.**
  The per-bank scripts in there today (`download_hdfc_images.py`,
  `parse_hdfc_card.py`, `parse_hdfc_credit_cards.py`, ...) are
  replaced by parameterized scripts (`--bank hdfc`) that delegate
  to the bank module.

---

## 5. The `BankScraper` interface

This is the single contract every bank implements. It is intentionally
small — every method maps to one pipeline stage.

```python
# bank_modules/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Protocol

from models import CardRecord


@dataclass(frozen=True)
class ListingPage:
    """One listing page to fetch and parse.

    A bank may produce one ListingPage (HDFC) or many (paginated SBI).
    """
    url: str                         # absolute URL
    label: str = ""                  # human-readable (e.g. "Credit Cards")


@dataclass(frozen=True)
class CardDetail:
    """One card detail page to fetch and parse.
    """
    url: str                         # absolute URL
    listing_label: str = ""          # for logging


class BankScraper(ABC):
    """The contract every bank implements.

    A BankScraper is a stateless object: all per-run state is held by
    the controller, which passes the shared HttpClient and ImageDownloader
    in. This makes BankScraper instances cheap to construct and easy
    to test.
    """

    # --- Identity --------------------------------------------------------
    bank_id: str                     # e.g. "hdfc"
    display_name: str                # e.g. "HDFC Bank"
    card_type_focus: str             # "credit" | "debit" | "both"

    # --- Stage 1: discover listing pages --------------------------------
    @abstractmethod
    def listing_pages(self) -> list[ListingPage]:
        """Return every listing page to fetch for this bank.

        Most banks return one entry. Paginated banks (future) may
        return many; the controller will iterate.
        """

    # --- Stage 2: parse a listing page ----------------------------------
    @abstractmethod
    def parse_listing(self, html: str, source_url: str) -> list[CardDetail]:
        """Turn one listing page's HTML into a list of card detail URLs.

        Pure: no I/O. The controller fetches the HTML, calls this,
        then iterates the returned details to fetch each one.
        """

    # --- Stage 3: parse a card detail page ------------------------------
    @abstractmethod
    def parse_card(self, html: str, source_url: str) -> CardRecord:
        """Turn one card detail page's HTML into a CardRecord.

        Pure: no I/O. The controller persists the returned record.
        Must populate at least: bank_id, card_slug, card_name,
        card_type, image_url, source_url.
        """

    # --- Stage 4: image policy (optional override) ----------------------
    def image_policy(self) -> "ImagePolicy":
        """Return the image download policy for this bank.

        Default policy lives on the base class; banks override only
        if they need different extensions, slug rules, or fallbacks.
        """
        return ImagePolicy()

    # --- Optional hooks --------------------------------------------------
    def before_run(self) -> None:
        """Optional setup hook (logging, warm-up, etc.)."""

    def after_run(self) -> None:
        """Optional teardown hook."""


@dataclass(frozen=True)
class ImagePolicy:
    """Per-bank overrides for image download behaviour.

    Default values mirror the brief in Sprint 3.6: save under
    images/raw/<bank_id>/, default to .webp, skip if present.
    """
    default_extension: str = ".webp"
    extra_subdir: str = ""           # e.g. "credit/" for HDFC
    # Note: most behaviour (skip-if-exists, magic-byte sniffing,
    # timeout, error mapping) stays in ImageDownloader and is NOT
    # duplicated here.
```

### Why this shape

- **Methods, not constructors.** A bank's URLs, parsing functions,
  and image policy are properties of the bank, not per-run state.
  Constructor injection of `HttpClient` / `ImageDownloader` is the
  controller's job.
- **No "fetch" methods on the scraper.** Fetching is the controller's
  job. A scraper that *fetches* is harder to test (you have to mock
  the network) and harder to reuse (you can't pre-fetch a listing
  page and feed its HTML to a parser from a saved fixture). The
  current HDFC parsers are already pure functions — this proposal
  keeps that contract.
- **One `parse_listing` and one `parse_card` per bank.** The two
  pages have different shapes; a single `parse(html) -> CardRecord`
  method (as `parsers/base.py` today suggests) cannot represent
  HDFC's two-stage fan-out.
- **`image_policy()` is a method, not a constructor argument.**
  Some banks may want `.png` (Axis) or a different sub-layout. A
  method keeps the override discoverable and overridable.

### What is intentionally NOT in `BankScraper`

- `download_image`, `save_to_db` — owned by `ImageDownloader` and
  `CardRepository` respectively. The controller calls them.
- `validate` — owned by `validator.py`. The controller calls it
  between `parse_card` and `repository.save_card`.
- `__init__` taking an `HttpClient` — the controller injects this
  via a small `wire()` method, or the scraper accepts it in `__init__`
  but **does not call it itself**.

---

## 6. Controller orchestration

After the refactor, the controller's `run` method becomes:

```python
def run(self) -> None:
    for scraper in self._load_scrapers():
        self._run_one(scraper)

def _run_one(self, scraper: BankScraper) -> None:
    self.logger.info("=== %s (%s) ===", scraper.display_name, scraper.bank_id)

    scraper.before_run()
    try:
        for listing in scraper.listing_pages():
            html = self.http.get(listing.url)            # 1. fetch
            details = scraper.parse_listing(html, listing.url)   # 2. parse

            for detail in details:
                detail_html = self.http.get(detail.url)   # 3. fetch detail
                record = scraper.parse_card(detail_html, detail.url)  # 4. parse detail
                result = self.validator.validate(record)   # 5. validate
                if not result.ok:
                    self.logger.warning("Skipping %s: %s", record.card_slug, result.reason)
                    continue
                self.repo.save_card(record)               # 6. persist
                if self.image_downloader:
                    self.image_downloader.download(       # 7. image
                        record.image_url,
                        card_slug=record.card_slug,
                        bank_id=scraper.bank_id,
                    )
    finally:
        scraper.after_run()
```

### Pipeline diagram

```
                ┌────────────────────────────────────────────┐
                │              main.py                        │
                │  ensure_directories()                       │
                │  configure_logging()                        │
                │  ScraperController().run()                  │
                └─────────────────────┬──────────────────────┘
                                      │
                                      ▼
                ┌────────────────────────────────────────────┐
                │           ScraperController                │
                │  for each BankScraper in registry:         │
                │      run pipeline                          │
                └──┬──────────────┬──────────────┬──────────┘
                   │              │              │
        ┌──────────┘              │              └──────────┐
        ▼                         ▼                         ▼
┌───────────────┐      ┌──────────────────┐      ┌────────────────┐
│ BankScraper   │      │  HttpClient      │      │ CardRepository │
│ (per bank)    │      │  (shared)        │      │  (shared)      │
│               │      └──────────────────┘      └────────────────┘
│ • listing_pages│
│ • parse_listing│              ┌──────────────────┐
│ • parse_card   │              │  validator.py    │
│ • image_policy │              │  (shared)        │
└───────┬───────┘              └──────────────────┘
        │
        │           ┌──────────────────┐
        └──────────▶│  ImageDownloader │
                    │  (shared)        │
                    └──────────────────┘
```

Each arrow crosses exactly one module boundary. The controller is
the only place that knows about all five boxes.

### Why the controller owns the loop, not the scraper

- **Testable.** A bank module is testable with a fake controller
  (or no controller at all — feed it fixtures, assert its outputs).
- **Composable.** To run only listing parsing for a bank (e.g. to
  regenerate a fixture), call the scraper directly without going
  through the controller.
- **Consistent metrics.** Logs, timings, and error counts are
  produced in one place rather than in every bank's `__init__`.

---

## 7. Changes required (per the rules)

### `controller.py` — REFACTOR

The current `ScraperController` is a stub. It becomes a real
orchestrator. **Public method names change** (`run` now actually
runs, `run_for_bank` becomes `_run_one`), which is a breaking
change for any caller — there are none today, so this is safe.

### `bank_modules/` — POPULATE

- `bank_modules/base.py` — gain the `BankScraper` ABC and the
  `ListingPage` / `CardDetail` / `ImagePolicy` dataclasses.
- `bank_modules/hdfc/` — new package; absorbs today's
  `parsers/hdfc.py`, `parsers/hdfc_credit_cards.py`, and
  `parsers/hdfc_card.py`. New `HDFCScraper` class wires them
  together and implements `BankScraper`.
- `bank_modules/{sbi,icici,axis}/` — empty stub packages with
  `__init__.py` that re-export a placeholder `*Scraper` class.
  Filled in by Sprints 4.2, 4.3, 4.4.

### `parsers/` — DELETE (after migration)

After all three HDFC parser files move into `bank_modules/hdfc/`,
the top-level `parsers/` package has no remaining contents and
is deleted. The existing test files that live under
`tests/test_hdfc_*.py` move to `tests/bank_modules/hdfc/`.

### `scripts/` — SHRINK

- New: `scripts/download_bank_images.py --bank hdfc`. Replaces
  `scripts/download_hdfc_images.py`. Implemented as a thin wrapper
  around the controller's pipeline, run for a single bank.
- New: `scripts/parse_bank_card.py --bank hdfc --html <file>`.
  Replaces `scripts/parse_hdfc_card.py`.
- The old `scripts/download_hdfc_*.py` and
  `scripts/parse_hdfc_*.py` files are **deleted** in a single
  commit once their replacements are verified to do the same job.

### `models.py`, `database.py`, `http_client.py`, `image_downloader.py` — UNCHANGED

Per the Sprint 4 rules. The `BankScraper` interface is designed
so that none of these need to change.

---

## 8. Migration strategy

The refactor is the riskiest part of Sprint 4 because it touches
the file layout, the test layout, and the controller simultaneously.
The migration is therefore broken into **four small phases**, each
ending with a green test run.

### Phase A — Land the interface (no behaviour change)

1. Add `bank_modules/base.py` with the `BankScraper` ABC and
   dataclasses. **No existing file changes.**
2. Add `tests/bank_modules/base/test_bank_scraper_contract.py`
   with a `FakeBankScraper` that the contract tests can be run
   against.
3. Run the full test suite: must show 140 + N passing (where N is
   the number of contract tests, expected ~6).

### Phase B — Move HDFC under the new layout

1. Create `bank_modules/hdfc/` with:
   - `__init__.py` re-exporting `HDFCScraper`.
   - `selectors.py` — copy the `SELECTOR_*` constants from
     `parsers/hdfc_card.py` verbatim.
   - `urls.py` — `LISTING_BASE_URL`, `IMAGE_DIR` constants.
   - `parsers.py` — move `parse_listing` (was `parsers/hdfc.py`),
     `parse_listing_credit_cards` (was
     `parsers/hdfc_credit_cards.py`), and `parse_card` (was
     `parsers/hdfc_card.py`) here, as module-level functions.
   - `scraper.py` — new `HDFCScraper(BankScraper)` class that
     delegates to the parser functions and holds the constants.
2. Move test files:
   - `tests/test_hdfc_parser.py` → `tests/bank_modules/hdfc/test_parsers_listing.py`
   - `tests/test_hdfc_credit_cards_parser.py` → `tests/bank_modules/hdfc/test_parsers_credit_cards.py`
   - `tests/test_hdfc_card_parser.py` → `tests/bank_modules/hdfc/test_parsers_card.py`
   - Update every `from parsers.hdfc_X import …` to
     `from bank_modules.hdfc.parsers import …`.
3. Update the four HDFC scripts in `scripts/` to import from
   `bank_modules.hdfc.parsers` instead of `parsers.hdfc_*`.
   This keeps behaviour identical.
4. Delete the now-empty top-level `parsers/` package.
5. Run the full test suite: must show 140 + N passing (the same
   tests, just relocated).

### Phase C — Wire the controller

1. Refactor `controller.py` to loop over a `BANK_REGISTRY` and
   call the `BankScraper` interface. Remove the HDFC-specific
   script `scripts/download_hdfc_images.py` in favour of
   `scripts/download_bank_images.py --bank hdfc`.
2. Add `tests/test_controller.py` with a mock bank that proves
   the controller walks the pipeline in the right order.
3. Re-run `python scripts/download_bank_images.py --bank hdfc`
   end-to-end. Output must match the Sprint 3.6 run: 40
   downloaded, 5 failed, identical file names.

### Phase D — Add stubs for new banks

1. Add `bank_modules/sbi/__init__.py` exporting
   `SBIScraper(BankScraper)`. The class raises
   `NotImplementedError` from every abstract method, with a
   comment "implemented in Sprint 4.2".
2. Same for `bank_modules/icici/` and `bank_modules/axis/`.
3. Update `config.settings.ACTIVE_BANKS` to leave the list empty
   (default) so the controller skips the stubs.
4. Add a smoke test in
   `tests/bank_modules/{sbi,icici,axis}/test_stub.py` that
   imports the class and asserts the abstract methods raise
   `NotImplementedError`.

End of Phase D: 140 + ~6 + ~3 = ~149 tests passing. **Zero
behaviour change.** Adding SBI in Sprint 4.2 is now a matter of
implementing one class.

---

## 9. Sprint 4.x roadmap

Each sprint is small enough to land in one sitting and end with a
green test run.

### Sprint 4.1 — Framework refactor

- Land the `BankScraper` interface, the `ListingPage` /
  `CardDetail` / `ImagePolicy` dataclasses, and the contract
  tests (Phase A).
- Move HDFC under `bank_modules/hdfc/` (Phase B).
- Wire the controller (Phase C).
- Add SBI / ICICI / Axis stubs (Phase D).
- **Done when:** 140+ tests still pass, and
  `python scripts/download_bank_images.py --bank hdfc` reproduces
  Sprint 3.6's output (40 downloaded, 5 failed).
- **Risk:** the controller refactor. Mitigated by Phase C's
  end-to-end smoke test.

### Sprint 4.2 — Add SBI

- Discovery script: fetch SBI's card listing page, identify the
  card anchors, save to `logs/debug/sbi_cards.html`.
- `parsers/listings.py` (inside `bank_modules/sbi/`) — pure
  function `parse_listing(html) -> list[CardDetail]`.
- `parsers/cards.py` (inside `bank_modules/sbi/`) — pure
  function `parse_card(html) -> CardRecord`.
- `SBIScraper` — concrete `BankScraper` wiring the two.
- Add to `config.settings.ACTIVE_BANKS` and run the full
  pipeline.
- **Done when:** at least 1 SBI card appears in the SQLite DB
  with a downloaded image, and the new tests pass.

### Sprint 4.3 — Add ICICI

- Same shape as Sprint 4.2. ICICI's site may need different
  request headers (already supported by `HttpClient`); the only
  bank-specific change lives in the new `selectors.py` and
  `urls.py` files.

### Sprint 4.4 — Add Axis

- Same shape. Axis's card pages use a different layout, so the
  `parse_card` function will be the largest of the four.

### Sprint 4.5 — Regression tests & cross-bank cleanup

- A new `tests/test_full_pipeline.py` that, for every bank in
  `config.settings.ACTIVE_BANKS`, runs the controller and
  asserts: at least N cards parsed, zero DB exceptions, every
  listed `image_url` is either present on disk or in a known
  skip set with a documented reason.
- Cross-bank metrics: per-bank pass / skip / fail counts in
  one log line.
- Delete any per-bank debug scripts that are no longer needed.
- **Done when:** the regression test passes for every active
  bank, and removing any bank's `bank_modules/<bank>/` folder
  does not affect the other banks' test runs.

---

## 10. Risks & open questions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Controller refactor breaks a hidden caller | Low | Medium | Today there are no callers; the smoke test in Phase C catches regressions. |
| HDFC tests fail to find their fixtures after move | Medium | Low | Phase B's update is mechanical and grep-verifiable. |
| A future bank needs state across stages (e.g. a session cookie from the listing page) | Medium | Medium | The `BankScraper` interface can grow a `Session` attribute, or a `context()` hook. Out of scope for Sprint 4.1; revisit in 4.2. |
| Image download policy diverges wildly per bank | Low | Low | `ImagePolicy` dataclass is the seam; a bank can override `default_extension` and `extra_subdir` without touching `ImageDownloader`. |
| The `parsers/` package removal breaks documentation links | Low | Low | `docs/architecture.md` is updated in Phase B; the CHANGELOG entry for Sprint 4.1 lists the rename. |
| "Bank" stops being a single site (e.g. co-branded cards under a parent brand) | Low | High | The `bank_id` field is just a string; `BankScraper` doesn't constrain it. If needed, a future sprint can introduce a `BankGroup` layer above. |

### Open questions to resolve before Sprint 4.2

1. **Card-type filtering.** HDFC has separate credit / debit listing
   pages. Should the controller treat them as one bank with two
   listings, or two banks (`hdfc-credit`, `hdfc-debit`)? The brief
   in the current scope is credit-only, so the proposal treats
   credit as `hdfc` and adds debit later if needed.
2. **Re-scrape policy.** When the controller re-runs, should it
   re-download every image, or skip if `updated_at` is recent? Out
   of scope for Sprint 4.1, but the controller signature leaves
   room for a `policy` argument in a later sprint.
3. **Image download scheduling.** Today every image is downloaded
   in series with a 0.5s delay. The brief for 4.1 does not change
   this, but a future sprint may want concurrency. The
   `ImageDownloader` API is unchanged in this proposal so a later
   refactor can add a pool without breaking bank modules.

---

## 11. Future scalability

The proposal is intentionally **conservative**. It does not introduce
async, a queue, a plugin system, or a config DSL. Each of those is
a real temptation at this point in a project; the brief asks for
a working multi-bank framework, not a general-purpose scraping
platform. Items deferred to a hypothetical Sprint 7+:

- **Per-bank retry and backoff policies** (currently the
  controller uses one global setting).
- **Concurrent detail-page fetching** (asyncio + aiohttp; the
  parser contract is already pure-function, so this is an
  additive change to the controller).
- **A `bank_modules/<bank>/fees_parser.py` split** for banks
  whose fee tables are complex (Axis). Today HDFC's fees are in
  `parse_card`; if another bank has 200 lines of fee-regex
  logic, it deserves its own module.
- **Bank pack distribution.** A bank's `bank_modules/<bank>/`
  folder could be packaged independently and dropped into
  `bank_modules/` without touching the rest of the project. The
  proposed layout already supports this.

---

## 12. Summary

- **One interface** (`BankScraper`) replaces the ad-hoc HDFC
  pipeline scripts.
- **One package per bank** (`bank_modules/<bank>/`) holds the
  pure parsers, the selectors, the URLs, and the wiring class.
- **The controller is the only orchestrator.** It loops over
  banks, fetches via the shared `HttpClient`, parses via the
  bank's `BankScraper`, validates, persists via `CardRepository`,
  and downloads images via `ImageDownloader`.
- **No changes** to `models.py`, `database.py`,
  `image_downloader.py`, or `http_client.py` — the refactor is
  pure reorganization and one new interface.
- **140+ tests still pass** at every phase. Adding SBI / ICICI /
  Axis is now a Sprint-sized task, not a project.

**Awaiting approval before any code changes.**
