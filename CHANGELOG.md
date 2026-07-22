# Changelog

All notable changes to this project will be documented in this file.

This project follows a sprint-based development approach.

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