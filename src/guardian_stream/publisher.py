"""Kinesis publisher for Guardian articles."""

import boto3
from botocore.exceptions import ClientError

from guardian_stream.exceptions import PublisherError, RecordTooLargeError
from guardian_stream.models import Article


class KinesisPublisher:
    """Publishes articles to an AWS Kinesis stream."""

    MAX_RECORD_SIZE = 1024 * 1024  # 1MB Kinesis limit

    def __init__(self, stream_name: str, region_name: str = "eu-west-2") -> None:
        """Initialize the publisher with a stream name.

        Args:
            stream_name: The name of the Kinesis stream to publish to.
            region_name: AWS region where the stream exists.

        Raises:
            ValueError: If stream_name is empty or whitespace.
        """
        if not stream_name or not stream_name.strip():
            raise ValueError("Stream name must not be empty or whitespace")

        self.stream_name = stream_name
        self._client = boto3.client("kinesis", region_name=region_name)

    def publish(self, articles: Article | list[Article]) -> int:
        """Publish one or more articles to Kinesis.

        Args:
            articles: A single Article or list of Articles to publish.

        Returns:
            The number of records successfully published.

        Raises:
            PublisherError: If Kinesis returns an error.
            RecordTooLargeError: If any article exceeds 1MB when serialized.
        """
        # Normalize to list
        if isinstance(articles, Article):
            articles = [articles]

        if not articles:
            return 0

        published_count = 0

        for article in articles:
            self._publish_single(article)
            published_count += 1

        return published_count

    def _publish_single(self, article: Article) -> None:
        """Publish a single article to Kinesis.

        Args:
            article: The Article to publish.

        Raises:
            PublisherError: If Kinesis returns an error.
            RecordTooLargeError: If the article exceeds 1MB when serialized.
        """
        data = article.model_dump_json().encode("utf-8")

        if len(data) > self.MAX_RECORD_SIZE:
            raise RecordTooLargeError(len(data))

        try:
            self._client.put_record(
                StreamName=self.stream_name,
                Data=data,
                PartitionKey=article.webUrl,
            )
        except ClientError as e:
            raise PublisherError(
                f"Failed to publish to stream '{self.stream_name}': {e}",
                original_error=e,
            ) from e
