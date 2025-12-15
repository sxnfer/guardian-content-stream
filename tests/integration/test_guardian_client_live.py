"""Integration tests for Guardian API client against live API.

These tests are skipped by default. To run them:
    GUARDIAN_API_KEY=your-key pytest tests/integration/ -v

You can obtain a free API key from: https://open-platform.theguardian.com/
"""

import os
from datetime import date, timedelta

import pytest

from guardian_stream.guardian_client import GuardianClient
from guardian_stream.models import Article


GUARDIAN_API_KEY = os.environ.get("GUARDIAN_API_KEY")

skip_without_api_key = pytest.mark.skipif(
    not GUARDIAN_API_KEY,
    reason="GUARDIAN_API_KEY environment variable not set",
)


@pytest.fixture
def live_client() -> GuardianClient:
    """Create a GuardianClient with real API key."""
    assert GUARDIAN_API_KEY is not None
    return GuardianClient(api_key=GUARDIAN_API_KEY)


@skip_without_api_key
def test_live_search_returns_articles(live_client: GuardianClient):
    """Verify we can fetch real articles from the Guardian API."""
    results = live_client.search("technology")

    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(article, Article) for article in results)


@skip_without_api_key
def test_live_search_with_date_filter(live_client: GuardianClient):
    """Verify date filtering works with real API."""
    one_week_ago = date.today() - timedelta(days=7)
    results = live_client.search("news", date_from=one_week_ago)

    assert isinstance(results, list)
    for article in results:
        assert article.webPublicationDate.date() >= one_week_ago


@skip_without_api_key
def test_live_search_respects_max_results(live_client: GuardianClient):
    """Verify we never return more than 10 results."""
    results = live_client.search("the")

    assert len(results) <= 10
