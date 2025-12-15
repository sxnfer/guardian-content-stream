"""Guardian API client for querying The Guardian's Open Platform."""

from datetime import date

import httpx

from guardian_stream.exceptions import GuardianAPIError, RateLimitError
from guardian_stream.models import Article

GUARDIAN_API_URL = "https://content.guardianapis.com/search"


class GuardianClient:
    """Client for querying The Guardian's Open Platform API."""

    def __init__(self, api_key: str) -> None:
        """Initialize client with API key.

        Args:
            api_key: The Guardian API key for authentication.

        Raises:
            ValueError: If api_key is empty or whitespace-only.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty")
        self._api_key = api_key

    def search(
        self,
        query: str,
        date_from: date | None = None,
    ) -> list[Article]:
        """Search for articles matching the query.

        Args:
            query: Search term to find articles.
            date_from: Optional date to filter articles from.

        Returns:
            List of up to 10 Article objects, sorted by date descending.

        Raises:
            ValueError: If query is empty or whitespace-only.
            TypeError: If date_from is not a date object.
            GuardianAPIError: If the API returns an error response.
            RateLimitError: If the API returns a 429 rate limit response.
        """
        if not query or not query.strip():
            raise ValueError("search term must not be empty")

        if date_from is not None and not isinstance(date_from, date):
            raise TypeError("date_from must be a date object")

        params = {
            "api-key": self._api_key,
            "q": query,
            "page-size": 10,
            "order-by": "newest",
        }

        if date_from is not None:
            params["from-date"] = date_from.isoformat()

        response = httpx.get(GUARDIAN_API_URL, params=params)

        if response.status_code == 429:
            raise RateLimitError()

        if response.status_code >= 400:
            raise GuardianAPIError(
                f"Guardian API error: {response.status_code}",
                status_code=response.status_code,
            )

        data = response.json()
        results = data.get("response", {}).get("results", [])

        articles = [
            Article(
                webPublicationDate=item["webPublicationDate"],
                webTitle=item["webTitle"],
                webUrl=item["webUrl"],
            )
            for item in results
        ]

        articles.sort(key=lambda a: a.webPublicationDate, reverse=True)

        return articles[:10]
