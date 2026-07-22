"""
tests/
------
Test suite. We use pytest. Each module gets a parallel test file:

    database.py          -> tests/test_database.py
    downloader.py        -> tests/test_downloader.py
    validator.py         -> tests/test_validator.py
    parsers/hdfc.py      -> tests/parsers/test_hdfc.py
    bank_modules/hdfc.py -> tests/bank_modules/test_hdfc.py

Why this layout?
- Mirrors the source tree so contributors can find tests easily.
- Allows pytest to discover per-folder conftest.py fixtures.
"""
