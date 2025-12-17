"""Tests for Kinesis publisher using moto for AWS mocking."""

import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from guardian_stream.exceptions import PublisherError, RecordTooLargeError
from guardian_stream.models import Article
from guardian_stream.publisher import KinesisPublisher


@pytest.fixture
def sample_article() -> Article:
    """Create a sample article for testing."""
    return Article(
        webPublicationDate=datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc),
        webTitle="Test Article Title",
        webUrl="https://www.theguardian.com/test/2024/mar/15/test-article",
    )


@pytest.fixture
def sample_articles() -> list[Article]:
    """Create multiple sample articles for testing."""
    return [
        Article(
            webPublicationDate=datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc),
            webTitle="First Article",
            webUrl="https://www.theguardian.com/test/2024/mar/15/first-article",
        ),
        Article(
            webPublicationDate=datetime(2024, 3, 15, 11, 0, 0, tzinfo=timezone.utc),
            webTitle="Second Article",
            webUrl="https://www.theguardian.com/test/2024/mar/15/second-article",
        ),
        Article(
            webPublicationDate=datetime(2024, 3, 15, 11, 30, 0, tzinfo=timezone.utc),
            webTitle="Third Article",
            webUrl="https://www.theguardian.com/test/2024/mar/15/third-article",
        ),
    ]


STREAM_NAME = "test-guardian-stream"


@pytest.fixture
def kinesis_stream():
    """Create a mocked Kinesis stream for testing."""
    with mock_aws():
        client = boto3.client("kinesis", region_name="eu-west-2")
        client.create_stream(StreamName=STREAM_NAME, ShardCount=1)
        # Wait for stream to become active (moto handles this instantly)
        waiter = client.get_waiter("stream_exists")
        waiter.wait(StreamName=STREAM_NAME)
        yield client


class TestPublishSingleArticle:
    """Tests for publishing a single article."""

    def test_publish_single_article_succeeds(
        self, kinesis_stream, sample_article: Article
    ):
        """Single article should be published to stream."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)

        result = publisher.publish(sample_article)

        assert result == 1  # One record published

    def test_publish_returns_record_count(self, kinesis_stream, sample_article: Article):
        """Publish should return the number of records successfully published."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)

        result = publisher.publish(sample_article)

        assert result == 1


class TestPublishMultipleArticles:
    """Tests for publishing multiple articles."""

    def test_publish_multiple_articles_succeeds(
        self, kinesis_stream, sample_articles: list[Article]
    ):
        """List of articles should all be published."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)

        result = publisher.publish(sample_articles)

        assert result == 3  # All three records published

    def test_publish_empty_list_is_noop(self, kinesis_stream):
        """Empty list should not error and return 0."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)

        result = publisher.publish([])

        assert result == 0


class TestPartitionKey:
    """Tests for partition key handling."""

    def test_publish_sets_partition_key_from_url(
        self, kinesis_stream, sample_article: Article
    ):
        """Each record should have partition key derived from article URL."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)
        publisher.publish(sample_article)

        # Read back from stream to verify partition key
        shard_iterator = kinesis_stream.get_shard_iterator(
            StreamName=STREAM_NAME,
            ShardId="shardId-000000000000",
            ShardIteratorType="TRIM_HORIZON",
        )["ShardIterator"]

        records = kinesis_stream.get_records(ShardIterator=shard_iterator)["Records"]

        assert len(records) == 1
        assert records[0]["PartitionKey"] == sample_article.webUrl


class TestJsonSerialization:
    """Tests for article JSON serialization."""

    def test_publish_serializes_article_to_json(
        self, kinesis_stream, sample_article: Article
    ):
        """Record data should be valid JSON matching Article schema."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)
        publisher.publish(sample_article)

        # Read back from stream
        shard_iterator = kinesis_stream.get_shard_iterator(
            StreamName=STREAM_NAME,
            ShardId="shardId-000000000000",
            ShardIteratorType="TRIM_HORIZON",
        )["ShardIterator"]

        records = kinesis_stream.get_records(ShardIterator=shard_iterator)["Records"]

        assert len(records) == 1
        data = json.loads(records[0]["Data"].decode("utf-8"))

        assert data["webTitle"] == sample_article.webTitle
        assert data["webUrl"] == sample_article.webUrl
        assert "webPublicationDate" in data


class TestErrorHandling:
    """Tests for error handling."""

    def test_publish_handles_kinesis_error(self, sample_article: Article):
        """Boto3 ClientError should raise PublisherError."""
        with mock_aws():
            # Don't create the stream - this will cause an error
            publisher = KinesisPublisher(stream_name="nonexistent-stream")

            with pytest.raises(PublisherError) as exc_info:
                publisher.publish(sample_article)

            assert "nonexistent-stream" in str(exc_info.value)

    def test_publish_handles_oversized_record(self, kinesis_stream):
        """Record exceeding 1MB should raise RecordTooLargeError."""
        # Create an article with content that exceeds 1MB
        oversized_article = Article(
            webPublicationDate=datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc),
            webTitle="Oversized Article",
            webUrl="https://www.theguardian.com/test/2024/mar/15/oversized",
            content_preview="x" * (1024 * 1024 + 1000),  # Just over 1MB
        )

        publisher = KinesisPublisher(stream_name=STREAM_NAME)

        with pytest.raises(RecordTooLargeError) as exc_info:
            publisher.publish(oversized_article)

        assert exc_info.value.record_size > RecordTooLargeError.MAX_RECORD_SIZE


class TestPublisherInitialization:
    """Tests for publisher initialization."""

    def test_publisher_requires_stream_name(self):
        """Publisher without stream name should refuse to instantiate."""
        with pytest.raises(ValueError) as exc_info:
            KinesisPublisher(stream_name="")

        assert "stream name" in str(exc_info.value).lower()

    def test_publisher_requires_non_whitespace_stream_name(self):
        """Publisher with whitespace-only stream name should refuse to instantiate."""
        with pytest.raises(ValueError) as exc_info:
            KinesisPublisher(stream_name="   ")

        assert "stream name" in str(exc_info.value).lower()

    def test_publisher_accepts_valid_stream_name(self, kinesis_stream):
        """Publisher with valid stream name should instantiate successfully."""
        publisher = KinesisPublisher(stream_name=STREAM_NAME)

        assert publisher.stream_name == STREAM_NAME
