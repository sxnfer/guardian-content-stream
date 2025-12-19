"""Unit tests for the Lambda handler.

Tests verify event parsing, response formatting, error handling,
and proper integration with the orchestrator. Module-level initialization
is mocked to test the handler in isolation.
"""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from guardian_stream.exceptions import GuardianAPIError, PublisherError, RateLimitError


class TestEventParsing:
    """Tests for Lambda event parsing and validation."""

    @pytest.fixture
    def mock_dependencies(self):
        """Patch module-level dependencies for isolated testing.

        This fixture mocks out all the module-level initialization
        that happens at import time, allowing us to test the handler
        logic without real AWS connections.
        """
        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 5,
                            "articles_published": 5,
                        }
                        yield {"run": mock_run}

    def test_handler_returns_400_for_missing_search_term(self, mock_dependencies):
        """Empty event should return 400 with helpful error message."""
        from guardian_stream.handler import handler

        response = handler({}, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "search_term" in body["error"].lower()

    def test_handler_returns_400_for_empty_search_term(self, mock_dependencies):
        """Empty string search term should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": ""}, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_handler_extracts_search_term_from_event(self, mock_dependencies):
        """Valid search term should be passed to orchestrator."""
        from guardian_stream.handler import handler

        handler({"search_term": "climate change"}, None)

        mock_dependencies["run"].assert_called_once()
        call_kwargs = mock_dependencies["run"].call_args.kwargs
        assert call_kwargs["search_term"] == "climate change"

    def test_handler_extracts_date_from_when_present(self, mock_dependencies):
        """Optional date_from should be parsed and passed to orchestrator."""
        from guardian_stream.handler import handler

        handler({"search_term": "test", "date_from": "2024-01-15"}, None)

        call_kwargs = mock_dependencies["run"].call_args.kwargs
        assert call_kwargs["date_from"] == date(2024, 1, 15)

    def test_handler_accepts_missing_date_from(self, mock_dependencies):
        """Missing date_from should pass None to orchestrator."""
        from guardian_stream.handler import handler

        handler({"search_term": "test"}, None)

        call_kwargs = mock_dependencies["run"].call_args.kwargs
        assert call_kwargs["date_from"] is None

    def test_handler_returns_400_for_invalid_date_format(self, mock_dependencies):
        """Invalid date format should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": "not-a-date"}, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "date" in body["error"].lower()


class TestResponseFormat:
    """Tests for Lambda response structure."""

    @pytest.fixture
    def mock_dependencies(self):
        """Patch module-level dependencies."""
        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 10,
                            "articles_published": 10,
                        }
                        yield {"run": mock_run}

    def test_handler_success_returns_200(self, mock_dependencies):
        """Successful execution should return statusCode 200."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 200

    def test_handler_returns_dict_with_status_code_and_body(self, mock_dependencies):
        """Response should have both statusCode and body keys."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test"}, None)

        assert "statusCode" in response
        assert "body" in response

    def test_handler_body_is_json_string(self, mock_dependencies):
        """Body should be a JSON string, not a dict."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test"}, None)

        assert isinstance(response["body"], str)
        parsed = json.loads(response["body"])
        assert isinstance(parsed, dict)

    def test_handler_success_includes_article_counts(self, mock_dependencies):
        """Success response body should include article counts."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test"}, None)

        body = json.loads(response["body"])
        assert body["articles_found"] == 10
        assert body["articles_published"] == 10


class TestErrorHandling:
    """Tests for error mapping and security."""

    @pytest.fixture
    def mock_init_success(self):
        """Patch initialization to succeed."""
        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    yield

    def test_handler_returns_500_for_guardian_api_error_without_status(
        self, mock_init_success
    ):
        """GuardianAPIError without status_code should return 500."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler.run") as mock_run:
            mock_run.side_effect = GuardianAPIError("API failed")

            response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 500

    def test_handler_returns_503_for_guardian_503_error(self, mock_init_success):
        """GuardianAPIError with 503 status should pass through."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler.run") as mock_run:
            mock_run.side_effect = GuardianAPIError("Service unavailable", status_code=503)

            response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 503

    def test_handler_returns_429_for_rate_limit_error(self, mock_init_success):
        """RateLimitError should return 429."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler.run") as mock_run:
            mock_run.side_effect = RateLimitError("Rate limited")

            response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 429

    def test_handler_returns_500_for_publisher_error(self, mock_init_success):
        """PublisherError should return 500."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler.run") as mock_run:
            mock_run.side_effect = PublisherError("Kinesis failed")

            response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 500

    def test_handler_returns_500_for_config_error(self):
        """Configuration errors should return 500."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler._init_error", ValueError("Missing config")):
            response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 500

    def test_handler_does_not_leak_api_key_in_error(self, mock_init_success):
        """Error messages must not contain sensitive values."""
        from guardian_stream.handler import handler

        secret_key = "super-secret-api-key-12345"

        with patch("guardian_stream.handler.run") as mock_run:
            mock_run.side_effect = GuardianAPIError(
                f"Auth failed with key {secret_key}", status_code=401
            )

            response = handler({"search_term": "test"}, None)

        body = response["body"]
        assert secret_key not in body
        assert "secret" not in body.lower()
        assert "key" not in body.lower() or "api" not in body.lower()

    def test_handler_error_body_is_json_with_error_key(self, mock_init_success):
        """Error response body should be JSON with 'error' key."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler.run") as mock_run:
            mock_run.side_effect = PublisherError("Failed")

            response = handler({"search_term": "test"}, None)

        body = json.loads(response["body"])
        assert "error" in body
        assert isinstance(body["error"], str)


class TestOrchestratorIntegration:
    """Tests for proper wiring to orchestrator."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock GuardianClient."""
        return MagicMock()

    @pytest.fixture
    def mock_publisher(self) -> MagicMock:
        """Create mock KinesisPublisher."""
        return MagicMock()

    def test_handler_calls_orchestrator_with_search_term(
        self, mock_client, mock_publisher
    ):
        """Orchestrator should receive the search term."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", mock_client):
                with patch("guardian_stream.handler._publisher", mock_publisher):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 0,
                            "articles_published": 0,
                        }

                        handler({"search_term": "technology"}, None)

                        mock_run.assert_called_once()
                        assert mock_run.call_args.kwargs["search_term"] == "technology"

    def test_handler_calls_orchestrator_with_date_from(
        self, mock_client, mock_publisher
    ):
        """Orchestrator should receive parsed date."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", mock_client):
                with patch("guardian_stream.handler._publisher", mock_publisher):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 0,
                            "articles_published": 0,
                        }

                        handler(
                            {"search_term": "test", "date_from": "2024-06-01"}, None
                        )

                        assert mock_run.call_args.kwargs["date_from"] == date(
                            2024, 6, 1
                        )

    def test_handler_passes_client_and_publisher_to_orchestrator(
        self, mock_client, mock_publisher
    ):
        """Orchestrator should receive the module-level client and publisher."""
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", mock_client):
                with patch("guardian_stream.handler._publisher", mock_publisher):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 0,
                            "articles_published": 0,
                        }

                        handler({"search_term": "test"}, None)

                        assert mock_run.call_args.kwargs["client"] is mock_client
                        assert mock_run.call_args.kwargs["publisher"] is mock_publisher


class TestModuleLevelInit:
    """Tests verifying cold start optimization is patchable."""

    def test_module_level_init_failure_returns_500(self):
        """If module initialization failed, handler returns 500."""
        from guardian_stream.handler import handler

        init_error = ValueError("GUARDIAN_API_KEY_SECRET_NAME not set")

        with patch("guardian_stream.handler._init_error", init_error):
            response = handler({"search_term": "test"}, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        assert "configuration" in body["error"].lower()
        assert "GUARDIAN_API_KEY" not in body["error"]


class TestSecretsManager:
    """Tests for AWS Secrets Manager integration."""

    @mock_aws
    def test_get_secret_retrieves_from_secrets_manager(self):
        """Secret value should be retrieved from Secrets Manager."""
        import os

        from guardian_stream.handler import _get_secret

        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "eu-west-2"}):
            client = boto3.client("secretsmanager", region_name="eu-west-2")
            client.create_secret(Name="test-secret", SecretString="my-api-key")

            result = _get_secret("test-secret")

            assert result == "my-api-key"

    @mock_aws
    def test_get_secret_handles_not_found_error(self):
        """Missing secret should raise appropriate error."""
        import os

        from botocore.exceptions import ClientError

        from guardian_stream.handler import _get_secret

        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "eu-west-2"}):
            boto3.client("secretsmanager", region_name="eu-west-2")

            with pytest.raises(ClientError) as exc_info:
                _get_secret("nonexistent-secret")

            assert "ResourceNotFoundException" in str(exc_info.value)

    @mock_aws
    def test_handler_uses_secret_for_api_key(self):
        """Handler initialization should use Secrets Manager for API key."""
        import os

        client = boto3.client("secretsmanager", region_name="eu-west-2")
        client.create_secret(Name="guardian-api-key", SecretString="real-api-key")

        with patch.dict(
            os.environ,
            {
                "GUARDIAN_API_KEY_SECRET_NAME": "guardian-api-key",
                "KINESIS_STREAM_NAME": "test-stream",
                "AWS_DEFAULT_REGION": "eu-west-2",
            },
        ):
            with patch("guardian_stream.handler.GuardianClient") as mock_client_cls:
                with patch("guardian_stream.handler.KinesisPublisher"):
                    from guardian_stream.handler import _initialize

                    _initialize()

                    mock_client_cls.assert_called_once_with(api_key="real-api-key")
