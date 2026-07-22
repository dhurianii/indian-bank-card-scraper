"""
bank_modules/
-------------
Per-bank "glue" code: where to find listing pages, how to paginate,
how to identify detail pages, and any bank-specific quirks (e.g. SBI
hiding cards behind a form post, HDFC using Angular-rendered markup).

A bank module is a thin layer that wires together:
    config (URLs/selectors)  -> parser -> validator -> downloader -> db

This folder is intentionally empty in Sprint 1; bank modules are
filled in as we onboard each bank.
"""
