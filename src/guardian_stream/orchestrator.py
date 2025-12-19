"""Orchestrator for Guardian-to-Kinesis pipeline."""

from datetime import date
from typing import Any

from guardian_stream.guardian_client import GuardianClient
from guardian_stream.models import Article
from guardian_stream.publisher import KinesisPublisher


def run(
    search_term: str,
    date_from: date | None = None,
    client: GuardianClient | Any | None = None,
    publisher: KinesisPublisher | Any | None = None,
) -> dict[str, int]:
    """Execute the Guardian-to-Kinesis pipeline.

    Args:
        search_term: Query to search for.
        date_from: Optional date filter.
        client: GuardianClient instance (or mock for testing).
        publisher: KinesisPublisher instance (or mock for testing).

    Returns:
        Dictionary with 'articles_found' and 'articles_published' counts.

    Raises:
        GuardianAPIError: If the Guardian API returns an error.
        PublisherError: If Kinesis publishing fails.
    """
    articles: list[Article] = client.search(
        query=search_term,
        date_from=date_from,
    )

    articles_found = len(articles)

    if articles:
        articles_published = publisher.publish(articles)
    else:
        articles_published = 0

    return {
        "articles_found": articles_found,
        "articles_published": articles_published,
    }
