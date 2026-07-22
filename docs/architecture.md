# Architecture

Single source of truth for the folder map, file responsibilities, and
setup steps is the top-level [`README.md`](../README.md). This document
captures only the design intent — the *why* — behind the layout, not
the *what*.

## Module boundaries

The pipeline is one-directional:

```
main.py
  └── controller.py
        ├── bank_modules/<bank>.py   (per-bank orchestration)
        │     └── parsers/<bank>.py (HTML -> CardRecord)
        ├── validator.py            (CardRecord -> ValidationResult)
        ├── downloader.py           (URL -> local image path)
        └── database.py             (CardRecord -> SQLite)
```

Each arrow crosses exactly one module boundary, and each module is
importable in isolation. The only shared types are in `models.py`.

## Why the bank_modules / parsers split

`parsers/` is pure: HTML in, list of `CardRecord` out, no I/O. Easy to
test with saved fixtures.

`bank_modules/` is the bank-specific glue: where to find listing pages,
how to paginate, how to identify detail pages, and any per-bank
quirks. A bank module wires a parser together with the controller's
generic flow.

The split keeps parsing logic (which we can unit-test) separate from
fetching logic (which we cannot).
