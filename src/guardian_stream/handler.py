"""AWS Lambda handler for Guardian Content Stream.

This module serves as the entry point for AWS Lambda invocations.
It parses incoming events, calls the orchestrator, and returns
properly formatted responses.

Module-level initialization is used for cold start optimization:
heavy resources (API clients, config) are initialized once when
the Lambda container starts, not on every invocation.
"""

import json
import os
from datetime import date
from typing import Any

import boto3

from guardian_stream.exceptions import GuardianAPIError, PublisherError
from guardian_stream.guardian_client import GuardianClient
from guardian_stream.orchestrator import run
from guardian_stream.publisher import KinesisPublisher

_api_key: str | None = None
_client: GuardianClient | None = None
_publisher: KinesisPublisher | None = None
_init_error: Exception | None = None


def _get_secret(secret_name: str) -> str:
    """Retrieve secret value from AWS Secrets Manager.

    Args:
        secret_name: The name or ARN of the secret to retrieve.

    Returns:
        The secret string value.

    Raises:
        ClientError: If the secret cannot be retrieved.
    """
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return response["SecretString"]


def _initialize() -> None:
    """Initialize module-level resources at container startup.

    This function runs once when the Lambda container starts (cold start).
    Errors are captured rather than raised so the handler can return
    proper error responses instead of crashing.
    """
    global _api_key, _client, _publisher, _init_error

    try:
        secret_name = os.environ.get("GUARDIAN_API_KEY_SECRET_NAME")
        if not secret_name:
            raise ValueError("GUARDIAN_API_KEY_SECRET_NAME not set")

        _api_key = _get_secret(secret_name)

        stream_name = os.environ.get("KINESIS_STREAM_NAME")
        if not stream_name:
            raise ValueError("KINESIS_STREAM_NAME not set")

        _client = GuardianClient(api_key=_api_key)
        _publisher = KinesisPublisher(stream_name=stream_name)

    except Exception as e:
        _init_error = e


_initialize()


def _parse_date(value: str | None) -> date | None | bool:
    """Parse date string in YYYY-MM-DD format.

    Args:
        value: Date string or None.

    Returns:
        - date object if parsing succeeds
        - None if value is None
        - False if parsing fails (sentinel for error handling)
    """
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return False


def _success_response(result: dict[str, int]) -> dict[str, Any]:
    """Build a successful Lambda response.

    Args:
        result: The orchestrator result with article counts.

    Returns:
        API Gateway-style response with statusCode 200.
    """
    return {
        "statusCode": 200,
        "body": json.dumps(result),
    }


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build an error Lambda response.

    Error messages are generic to avoid leaking sensitive information
    like API keys, internal paths, or stack traces.

    Args:
        status_code: HTTP status code (400, 429, 500, etc.)
        message: User-safe error message.

    Returns:
        API Gateway-style error response.
    """
    return {
        "statusCode": status_code,
        "body": json.dumps({"error": message}),
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point.

    Args:
        event: Lambda event containing:
            - search_term (required): The query to search for
            - date_from (optional): Filter articles from this date (YYYY-MM-DD)
        context: Lambda context (unused but required by AWS).

    Returns:
        API Gateway-style response with statusCode and JSON body.

    Response codes:
        200: Success - body contains article counts
        400: Bad request - missing/invalid parameters
        429: Rate limited by Guardian API
        500: Server error - configuration or internal failure
        503: Guardian API temporarily unavailable
    """
    if _init_error is not None:
        return _error_response(500, "Service configuration error")

    search_term = event.get("search_term")
    if not search_term or not str(search_term).strip():
        return _error_response(400, "search_term is required")

    date_from = _parse_date(event.get("date_from"))
    if date_from is False:
        return _error_response(400, "Invalid date format. Use YYYY-MM-DD.")

    try:
        result = run(
            search_term=search_term,
            date_from=date_from,
            client=_client,
            publisher=_publisher,
        )
        return _success_response(result)

    except GuardianAPIError as e:
        status_code = e.status_code if e.status_code else 500
        return _error_response(status_code, "Guardian API error")

    except PublisherError:
        return _error_response(500, "Publishing failed")

    except Exception:
        return _error_response(500, "Internal server error")
