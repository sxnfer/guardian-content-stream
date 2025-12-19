"""Unit tests for the orchestrator module.

These tests verify that the orchestrator correctly wires together
the GuardianClient and KinesisPublisher components. We mock both
dependencies to test the orchestration logic in isolation.

Key testing concepts used here:
- unittest.mock: Python's built-in mocking library
- MagicMock: Creates mock objects that record how they're called
- patch: Temporarily replaces real objects with mocks during tests
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from guardian_stream.models import Article


class TestOrchestrator:
    """Tests for the orchestrator's run() function."""

    # =========================================================================
    # FIXTURES: Reusable test setup
    # =========================================================================

    @pytest.fixture
    def sample_articles(self) -> list[Article]:
        """Create sample articles that our mock client will return.

        In real usage, these would come from the Guardian API.
        Here, we create them directly to control test data.
        """
        return [
            Article(
                webPublicationDate="2024-03-15T10:30:00Z",
                webTitle="Test Article 1",
                webUrl="https://www.theguardian.com/test/article-1",
            ),
            Article(
                webPublicationDate="2024-03-14T09:00:00Z",
                webTitle="Test Article 2",
                webUrl="https://www.theguardian.com/test/article-2",
            ),
        ]

    @pytest.fixture
    def mock_client(self, sample_articles: list[Article]) -> MagicMock:
        """Create a mock GuardianClient.

        MagicMock is a powerful testing tool that:
        - Records every method call made to it
        - Can be configured to return specific values
        - Tracks call arguments for assertions

        We configure search() to return our sample articles.
        """
        client = MagicMock()
        client.search.return_value = sample_articles
        return client

    @pytest.fixture
    def mock_publisher(self) -> MagicMock:
        """Create a mock KinesisPublisher.

        We configure publish() to return the count of articles passed to it.
        This mimics real behavior where publish returns the count.
        """
        publisher = MagicMock()
        # When publish is called, return the length of articles passed
        publisher.publish.side_effect = lambda articles: len(articles)
        return publisher

    # =========================================================================
    # TEST: Happy Path - Normal operation
    # =========================================================================

    def test_orchestrator_calls_client_then_publisher(
        self, mock_client: MagicMock, mock_publisher: MagicMock
    ):
        """Should fetch from Guardian, then publish to Kinesis.

        This test verifies the basic flow:
        1. Orchestrator calls client.search() with the search term
        2. Orchestrator calls publisher.publish() with the results

        We're testing the WIRING, not the components themselves.
        """
        from guardian_stream.orchestrator import run

        run(
            search_term="climate change",
            client=mock_client,
            publisher=mock_publisher,
        )

        # Verify client was called with correct search term
        mock_client.search.assert_called_once()
        call_args = mock_client.search.call_args
        assert call_args.kwargs.get("query") == "climate change" or \
               (call_args.args and call_args.args[0] == "climate change")

        # Verify publisher was called
        mock_publisher.publish.assert_called_once()

    def test_orchestrator_passes_articles_to_publisher(
        self,
        mock_client: MagicMock,
        mock_publisher: MagicMock,
        sample_articles: list[Article],
    ):
        """Publisher should receive exactly what client returned.

        This test ensures data flows correctly from client to publisher.
        The orchestrator shouldn't modify the articles in between.
        """
        from guardian_stream.orchestrator import run

        run(
            search_term="technology",
            client=mock_client,
            publisher=mock_publisher,
        )

        # Get the articles that were passed to publisher.publish()
        publish_call_args = mock_publisher.publish.call_args
        published_articles = publish_call_args.args[0] if publish_call_args.args else \
                            publish_call_args.kwargs.get("articles")

        # Should be exactly what the client returned
        assert published_articles == sample_articles

    def test_orchestrator_returns_result_with_counts(
        self, mock_client: MagicMock, mock_publisher: MagicMock
    ):
        """Should report how many articles were found and published.

        The orchestrator returns a result object/dict so callers
        know what happened without parsing logs.
        """
        from guardian_stream.orchestrator import run

        result = run(
            search_term="science",
            client=mock_client,
            publisher=mock_publisher,
        )

        # Result should contain useful information
        assert result["articles_found"] == 2
        assert result["articles_published"] == 2

    def test_orchestrator_passes_date_filter_to_client(
        self, mock_client: MagicMock, mock_publisher: MagicMock
    ):
        """Optional date_from should be passed to client.search().

        The orchestrator should forward the date filter to the client.
        """
        from guardian_stream.orchestrator import run

        test_date = date(2024, 1, 1)

        run(
            search_term="politics",
            date_from=test_date,
            client=mock_client,
            publisher=mock_publisher,
        )

        # Verify date was passed to client
        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs.get("date_from") == test_date

    # =========================================================================
    # TEST: Error Handling
    # =========================================================================

    def test_orchestrator_handles_client_error(
        self, mock_publisher: MagicMock
    ):
        """Guardian failure should not attempt publish.

        If the client raises an exception, we should:
        1. NOT call the publisher (why publish nothing?)
        2. Let the exception propagate to the caller

        This tests error isolation - a failure in one component
        shouldn't cause undefined behavior in another.
        """
        from guardian_stream.exceptions import GuardianAPIError
        from guardian_stream.orchestrator import run

        # Create a client that raises an error
        failing_client = MagicMock()
        failing_client.search.side_effect = GuardianAPIError(
            "API unavailable", status_code=503
        )

        with pytest.raises(GuardianAPIError):
            run(
                search_term="test",
                client=failing_client,
                publisher=mock_publisher,
            )

        # Publisher should NOT have been called
        mock_publisher.publish.assert_not_called()

    def test_orchestrator_handles_publisher_error(
        self, mock_client: MagicMock
    ):
        """Kinesis failure should propagate, not silently fail.

        If publishing fails, the caller needs to know. Silent failures
        are dangerous because they give false confidence that data
        was saved when it wasn't.
        """
        from guardian_stream.exceptions import PublisherError
        from guardian_stream.orchestrator import run

        # Create a publisher that raises an error
        failing_publisher = MagicMock()
        failing_publisher.publish.side_effect = PublisherError(
            "Kinesis unavailable"
        )

        with pytest.raises(PublisherError):
            run(
                search_term="test",
                client=mock_client,
                publisher=failing_publisher,
            )

    # =========================================================================
    # TEST: Edge Cases
    # =========================================================================

    def test_orchestrator_handles_no_articles_found(
        self, mock_publisher: MagicMock
    ):
        """Empty search results should be handled gracefully.

        When the Guardian API returns no articles:
        - Publisher should be called with empty list (or not called)
        - Result should show 0 found, 0 published
        - No errors should be raised
        """
        from guardian_stream.orchestrator import run

        # Client returns empty results
        empty_client = MagicMock()
        empty_client.search.return_value = []

        result = run(
            search_term="xyznonexistent",
            client=empty_client,
            publisher=mock_publisher,
        )

        assert result["articles_found"] == 0
        assert result["articles_published"] == 0
