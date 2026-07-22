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
        ⏳

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
38 / 38 Tests Passing
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

Sprint 3.1 — HTTP Client

Completed

- Reusable HttpClient
- Structured logging
- Manual integration script
- Documentation
- 38/38 tests passing

---

## Next Task

Sprint 3.2

Build the first parser.

Extract only

- Card Name
- Card URL

Do not work on

- Database
- Images
- Metadata extraction
- Multi-bank support

---

## Last Successful Test

```
38 / 38 Passed
```

---

## Last Commit

```
feat(http): implement reusable HTTP client and integration test
```

---

## Resume Prompt

When starting a new Claude Code session:

```
Read PROJECT_STATUS.md first.

Understand the current architecture.

Continue only from the current sprint.

Do not redesign completed modules.

Implement only the requirements of the current sprint.

Preserve all passing tests.
```

---

Last Updated

**22 July 2026**