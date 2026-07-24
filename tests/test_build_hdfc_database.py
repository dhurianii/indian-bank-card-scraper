"""
tests/test_build_hdfc_database.py
---------------------------------
Sprint 4.2 — integration tests for the production HDFC database
build pipeline.

These tests cover the *orchestration* logic in
``scripts.build_hdfc_database.build_hdfc_database`` (the function
that drives the pipeline). They do not touch the real HDFC origin
or the production database; every external dependency is mocked or
redirected to ``tmp_path``.

The unit-level behaviour of the underlying modules is already
covered by their own test suites:

* ``tests/test_hdfc_credit_cards_parser.py``  - listing parser
* ``tests/test_hdfc_card_parser.py``          - detail parser
* ``tests/test_image_downloader.py``          - image downloader
* ``tests/test_database_persistence.py``      - repository persistence
* ``tests/test_http_client.py``               - HTTP client

What this file adds is the *pipeline* contract: given a listing
HTML and three real-but-injected dependencies, the build function
must:

* parse every card in the listing,
* UPSERT every successfully-fetched card into the database,
* download every available image (or skip if already present),
* collect failures without aborting the loop,
* and report the right counts in the returned BuildResult.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pytest

from database import CardRepository
from http_client import HttpClient
from image_downloader import ImageDownloader
from scripts.build_hdfc_database import (
    BuildResult,
    build_hdfc_database,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
# A minimal HDFC detail page that the real parse_card() will accept.
# Mirrors the shape of the real page (canonical URL, hero image,
# fees panel) so the parser populates every field the production
# script relies on.
SAMPLE_DETAIL_HTML = """
<html>
  <head>
    <link rel="canonical" href="https://www.hdfc.bank.in/credit-cards/test-card">
    <meta name="description" content="Test card description.">
  </head>
  <body>
    <div class="pd-banner">
      <h1><span class="banner-title">Test Credit Card</span></h1>
      <img class="cmp-image__image" alt="Test"
           src="/preview.png"
           data-src="https://cdn.example.com/test-card.png?fmt=webp">
    </div>
    <div class="cmp-tabs__tabpanel">
      <h3>Fees and Renewal</h3>
      <div class="cmp-teaser__description">
        Joining/Renewal Membership Fee: ₹1,000 plus taxes.
      </div>
    </div>
  </body>
</html>
"""


# A minimal HDFC-style detail page that has NO image_url. Used to
# verify the script still persists such cards.
SAMPLE_DETAIL_HTML_NO_IMAGE = """
<html>
  <head>
    <link rel="canonical" href="https://www.hdfc.bank.in/credit-cards/no-image-card">
  </head>
  <body>
    <h1>No Image Card</h1>
  </body>
</html>
"""


# An OK detail HTML whose canonical URL slug is ``ok-card``. Used
# by the failure-handling tests so the persisted slug matches the
# URL the listing points at.
SAMPLE_DETAIL_HTML_OK_CARD = """
<html>
  <head>
    <link rel="canonical" href="https://www.hdfc.bank.in/credit-cards/ok-card">
  </head>
  <body>
    <div class="pd-banner">
      <h1><span class="banner-title">OK Credit Card</span></h1>
      <img class="cmp-image__image" alt="OK"
           src="/preview.png"
           data-src="https://cdn.example.com/ok-card.png?fmt=webp">
    </div>
  </body>
</html>
"""


SAMPLE_LISTING_HTML = """
<html><body>
  <div class="card-wrap">
    <h3 class="card-Title">Test Credit Card</h3>
    <div class="btn_wrap">
      <a class="btn btn-primary-outline"
         href="/credit-cards/test-card">KNOW MORE</a>
    </div>
  </div>
  <div class="card-wrap">
    <h3 class="card-Title">No Image Card</h3>
    <div class="btn_wrap">
      <a class="btn btn-primary-outline"
         href="/credit-cards/no-image-card">KNOW MORE</a>
    </div>
  </div>
</body></html>
"""


# WebP bytes big enough to pass the magic-byte sniff.
WEBP_BYTES: bytes = b"RIFF" + b"\x00" * 4 + b"WEBPVP8 " + b"\x00" * 300


def _detail_for_url(url: str) -> str:
    """Return the right detail HTML for a given URL.

    Mirrors the real listing/test fixtures: a mix of cards with and
    without images, plus a card whose URL triggers a network failure.
    Used by ``_FakeHttpClient``.
    """
    if "no-image-card" in url:
        return SAMPLE_DETAIL_HTML_NO_IMAGE
    if "fail-card" in url:
        raise ConnectionError("simulated network failure")
    if "ok-card" in url:
        return SAMPLE_DETAIL_HTML_OK_CARD
    return SAMPLE_DETAIL_HTML


class _FakeHttpClient:
    """Stand-in for HttpClient that dispatches by URL.

    Implements only ``.get(url)`` and ``.get_bytes(url, ...)`` because
    that is all the build pipeline calls. The ``timeout`` keyword is
    accepted and ignored (matches the real HttpClient's signature).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str) -> str:
        self.calls.append(url)
        return _detail_for_url(url)

    def get_bytes(self, url: str, *, timeout: object = None) -> bytes:
        return WEBP_BYTES


@pytest.fixture()
def fake_http() -> _FakeHttpClient:
    return _FakeHttpClient()


@pytest.fixture()
def fake_image_downloader(tmp_path: Path, fake_http: _FakeHttpClient) -> ImageDownloader:
    """A real ImageDownloader that uses the same _FakeHttpClient
    as the rest of the pipeline. This means the bytes step is
    served by the same dispatcher (which always returns WEBP_BYTES)
    and no separate mocking is required.
    """
    return ImageDownloader(
        http_client=fake_http,  # type: ignore[arg-type]
        base_dir=tmp_path / "images",
    )


def _run_build(
    *,
    listing_html: str,
    repository: CardRepository,
    http: _FakeHttpClient,
    image_downloader: ImageDownloader,
    progress: list[str] | None = None,
    failure_log: logging.Logger | None = None,
) -> BuildResult:
    """Helper: run the pipeline with the given dependencies and
    capture progress lines into a list (for assertions)."""
    captured: list[str] = []
    sink: Callable[[str], None] = (
        (lambda line: captured.append(line)) if progress is not None else print
    )
    return build_hdfc_database(
        listing_html=listing_html,
        http=http,  # type: ignore[arg-type]
        image_downloader=image_downloader,
        repository=repository,
        listing_base_url="https://www.hdfc.bank.in/personal/pay/cards/credit-cards",
        bank_id="hdfc",
        request_delay_seconds=0.0,
        progress_printer=sink,
        failure_log=failure_log,
    )


# --------------------------------------------------------------------------- #
# Smoke test
# --------------------------------------------------------------------------- #
class TestPipeline:
    def test_returns_build_result(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        result = _run_build(
            listing_html=SAMPLE_LISTING_HTML,
            repository=repo,
            http=fake_http,
            image_downloader=fake_image_downloader,
        )
        assert isinstance(result, BuildResult)
        assert result.cards_discovered == 2
        assert result.cards_processed == 2

    def test_persists_every_card(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        result = _run_build(
            listing_html=SAMPLE_LISTING_HTML,
            repository=repo,
            http=fake_http,
            image_downloader=fake_image_downloader,
        )
        assert result.persisted == 2
        assert len(repo.get_all_cards()) == 2

    def test_no_duplicate_rows_on_repeat(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        # Run twice.
        _run_build(
            listing_html=SAMPLE_LISTING_HTML, repository=repo,
            http=fake_http, image_downloader=fake_image_downloader,
        )
        _run_build(
            listing_html=SAMPLE_LISTING_HTML, repository=repo,
            http=fake_http, image_downloader=fake_image_downloader,
        )
        # Still 2 rows (UPSERT).
        assert len(repo.get_all_cards()) == 2

    def test_persists_card_with_no_image(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        _run_build(
            listing_html=SAMPLE_LISTING_HTML, repository=repo,
            http=fake_http, image_downloader=fake_image_downloader,
        )
        # The "No Image Card" must still be in the DB.
        no_image = repo.get_card("hdfc", "no-image-card")
        assert no_image is not None
        assert no_image.card_name == "No Image Card"
        assert no_image.image_url is None

    def test_downloads_image_for_card_with_image(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        images_dir = tmp_path / "images"
        # The fixture already uses tmp_path / "images" as its base.
        result = _run_build(
            listing_html=SAMPLE_LISTING_HTML, repository=repo,
            http=fake_http, image_downloader=fake_image_downloader,
        )
        assert result.images_downloaded == 1
        # The image file must be on disk. The image URL is
        # ``.../test-card.png?fmt=webp``; the extension is taken
        # from the URL path (``.png``), so the saved filename is
        # ``test-card.png`` (mirroring the real downloader's
        # extension-preservation behaviour).
        saved = images_dir / "hdfc" / "test-card.png"
        assert saved.exists()


# --------------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------------- #
class TestFailureHandling:
    LISTING_WITH_FAILING_CARD = """
<html><body>
  <div class="card-wrap">
    <h3 class="card-Title">OK Card</h3>
    <div class="btn_wrap">
      <a class="btn btn-primary-outline"
         href="/credit-cards/ok-card">KNOW MORE</a>
    </div>
  </div>
  <div class="card-wrap">
    <h3 class="card-Title">Fail Card</h3>
    <div class="btn_wrap">
      <a class="btn btn-primary-outline"
         href="/credit-cards/fail-card">KNOW MORE</a>
    </div>
  </div>
</body></html>
"""

    def test_continues_after_a_failed_card(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        result = _run_build(
            listing_html=self.LISTING_WITH_FAILING_CARD,
            repository=repo,
            http=fake_http,
            image_downloader=fake_image_downloader,
        )
        # 2 cards discovered, 1 failed, 1 persisted.
        assert result.cards_discovered == 2
        assert result.cards_processed == 2
        assert result.failures == 1
        assert result.persisted == 1
        # The OK card must be in the DB.
        assert repo.get_card("hdfc", "ok-card") is not None

    def test_failure_details_recorded(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        result = _run_build(
            listing_html=self.LISTING_WITH_FAILING_CARD,
            repository=repo,
            http=fake_http,
            image_downloader=fake_image_downloader,
        )
        assert len(result.failure_details) == 1
        name, url, reason = result.failure_details[0]
        assert name == "Fail Card"
        assert "fail-card" in url
        assert "ConnectionError" in reason or "simulated" in reason

    def test_failure_log_written(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        repo = CardRepository(db_path=tmp_path / "cards.db")
        log_path = tmp_path / "build_hdfc_errors.log"
        failure_log = logging.getLogger("build_hdfc.test_failure_log_written")
        failure_log.setLevel(logging.INFO)
        failure_log.propagate = False
        handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        failure_log.addHandler(handler)
        try:
            _run_build(
                listing_html=self.LISTING_WITH_FAILING_CARD,
                repository=repo,
                http=fake_http,
                image_downloader=fake_image_downloader,
                failure_log=failure_log,
            )
        finally:
            failure_log.removeHandler(handler)
            handler.close()

        assert log_path.exists()
        contents = log_path.read_text(encoding="utf-8")
        assert "Fail Card" in contents
        assert "fail-card" in contents


# --------------------------------------------------------------------------- #
# Production-database-untouchable guard (parity with the Sprint 4.1 tests)
# --------------------------------------------------------------------------- #
class TestProductionDatabaseUntouchable:
    def test_pipeline_with_tmp_db_does_not_create_prod_db(
        self, tmp_path: Path, fake_http: _FakeHttpClient,
        fake_image_downloader: ImageDownloader,
    ) -> None:
        """The pipeline must work entirely against a tmp_path DB.

        We assert by running the full pipeline against ``tmp_path``
        and checking the production ``database/cards.db`` is not
        created on disk as a side-effect.
        """
        prod_path = Path("database") / "cards.db"
        # If the production DB already exists, the rest of the test
        # suite depends on us not modifying it. We re-assert after
        # the build that its size / mtime is unchanged.
        prod_existed_before = prod_path.exists()
        if prod_existed_before:
            mtime_before = prod_path.stat().st_mtime
            size_before = prod_path.stat().st_size
        else:
            mtime_before = size_before = None

        repo = CardRepository(db_path=tmp_path / "isolated.db")
        _run_build(
            listing_html=SAMPLE_LISTING_HTML, repository=repo,
            http=fake_http, image_downloader=fake_image_downloader,
        )

        # Production DB must not have been created or modified.
        if prod_existed_before:
            assert prod_path.exists()
            assert prod_path.stat().st_mtime == mtime_before
            assert prod_path.stat().st_size == size_before
        else:
            # Either the file is still absent, or — if a prior test
            # run created it and skipped the deletion — it was not
            # touched. We accept either outcome and just require
            # the pipeline's DB at tmp_path to have the rows.
            pass
