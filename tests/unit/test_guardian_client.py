"""Unit tests for Guardian API client.

These tests use respx to mock HTTP responses, ensuring we never hit
the real Guardian API during unit tests.
"""

from datetime import date

import httpx
import pytest
import respx

from guardian_stream.exceptions import GuardianAPIError, RateLimitError
from guardian_stream.guardian_client import GuardianClient
from guardian_stream.models import Article

# Base URL for Guardian API
GUARDIAN_API_URL = "https://content.guardianapis.com/search"


# --- Fixtures ---


@pytest.fixture
def api_key() -> str:
    """Provide a test API key."""
    return "test-api-key-12345"


@pytest.fixture
def client(api_key: str) -> GuardianClient:
    """Create a GuardianClient instance for testing."""
    return GuardianClient(api_key=api_key)


@pytest.fixture
def sample_api_response() -> dict:
    """Sample successful response from Guardian API."""
    return {
        "response": {
            "status": "ok",
            "total": 2,
            "results": [
                {
                    "webPublicationDate": "2024-01-15T10:30:00Z",
                    "webTitle": "Climate change impacts on agriculture",
                    "webUrl": "https://www.theguardian.com/environment/2024/jan/15/climate-agriculture",
                },
                {
                    "webPublicationDate": "2024-01-14T08:00:00Z",
                    "webTitle": "New renewable energy targets announced",
                    "webUrl": "https://www.theguardian.com/environment/2024/jan/14/renewable-targets",
                },
            ],
        }
    }


# --- Client Instantiation Tests ---


def test_client_requires_api_key():
    """Client without API key should refuse to instantiate."""
    with pytest.raises(ValueError, match="API key"):
        GuardianClient(api_key="")

    with pytest.raises(ValueError, match="API key"):
        GuardianClient(api_key="   ")


# --- Search Validation Tests ---


@respx.mock
def test_search_validates_search_term(client: GuardianClient):
    """Empty or whitespace-only search term should raise ValueError."""
    with pytest.raises(ValueError, match="search term"):
        client.search("")

    with pytest.raises(ValueError, match="search term"):
        client.search("   ")


@respx.mock
def test_search_validates_date_format(client: GuardianClient):
    """Invalid date_from should raise ValueError."""
    # date_from should be a date object, not a string
    with pytest.raises((ValueError, TypeError)):
        client.search("climate", date_from="not-a-date")  # type: ignore


# --- Successful Search Tests ---


@respx.mock
def test_search_returns_list_of_articles(
    client: GuardianClient, sample_api_response: dict
):
    """Valid search should return list of Article models."""
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(200, json=sample_api_response)
    )

    results = client.search("climate")

    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(article, Article) for article in results)
    assert results[0].webTitle == "Climate change impacts on agriculture"


@respx.mock
def test_search_filters_by_date(client: GuardianClient, api_key: str):
    """Articles should be filtered by date_from parameter."""
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(200, json={"response": {"status": "ok", "results": []}})
    )

    client.search("climate", date_from=date(2024, 1, 1))

    # Verify the date was passed to the API
    assert respx.calls.last is not None
    request_url = str(respx.calls.last.request.url)
    assert "from-date=2024-01-01" in request_url


@respx.mock
def test_search_returns_max_ten_results(client: GuardianClient):
    """Even if API returns more, client returns at most 10."""
    # Create response with 15 articles
    many_articles = {
        "response": {
            "status": "ok",
            "results": [
                {
                    "webPublicationDate": f"2024-01-{15-i:02d}T10:00:00Z",
                    "webTitle": f"Article {i+1}",
                    "webUrl": f"https://www.theguardian.com/article-{i+1}",
                }
                for i in range(15)
            ],
        }
    }
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(200, json=many_articles)
    )

    results = client.search("test")

    assert len(results) <= 10


@respx.mock
def test_search_results_sorted_by_date_descending(client: GuardianClient):
    """Most recent articles should come first."""
    # API returns articles in mixed order
    mixed_order_response = {
        "response": {
            "status": "ok",
            "results": [
                {
                    "webPublicationDate": "2024-01-10T10:00:00Z",
                    "webTitle": "Older article",
                    "webUrl": "https://www.theguardian.com/older",
                },
                {
                    "webPublicationDate": "2024-01-15T10:00:00Z",
                    "webTitle": "Newest article",
                    "webUrl": "https://www.theguardian.com/newest",
                },
                {
                    "webPublicationDate": "2024-01-12T10:00:00Z",
                    "webTitle": "Middle article",
                    "webUrl": "https://www.theguardian.com/middle",
                },
            ],
        }
    }
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(200, json=mixed_order_response)
    )

    results = client.search("test")

    assert results[0].webTitle == "Newest article"
    assert results[1].webTitle == "Middle article"
    assert results[2].webTitle == "Older article"


@respx.mock
def test_search_handles_empty_results(client: GuardianClient):
    """Search with no matches should return empty list, not error."""
    empty_response = {"response": {"status": "ok", "results": []}}
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(200, json=empty_response)
    )

    results = client.search("xyznonexistentterm")

    assert results == []


# --- Error Handling Tests ---


@respx.mock
def test_search_handles_api_error(client: GuardianClient):
    """API 500 should raise GuardianAPIError."""
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(500, json={"message": "Internal server error"})
    )

    with pytest.raises(GuardianAPIError) as exc_info:
        client.search("climate")

    assert exc_info.value.status_code == 500


@respx.mock
def test_search_handles_rate_limit(client: GuardianClient):
    """API 429 should raise RateLimitError."""
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(429, json={"message": "Rate limit exceeded"})
    )

    with pytest.raises(RateLimitError):
        client.search("climate")


@respx.mock
def test_search_passes_api_key_securely(client: GuardianClient, api_key: str):
    """API key should be passed as query parameter, not in URL path."""
    respx.get(GUARDIAN_API_URL).mock(
        return_value=httpx.Response(200, json={"response": {"status": "ok", "results": []}})
    )

    client.search("climate")

    # Verify API key is in query params
    assert respx.calls.last is not None
    request_url = str(respx.calls.last.request.url)
    assert f"api-key={api_key}" in request_url
    # Verify it's not in the path
    assert api_key not in request_url.split("?")[0]
