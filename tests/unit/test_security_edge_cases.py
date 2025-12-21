"""Security-focused edge case tests.

Tests for input fuzzing, boundary conditions, and potential attack vectors.
These tests verify the system handles malicious or unusual input safely.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestSearchTermFuzzing:
    """Tests for unusual search term inputs."""

    @pytest.fixture
    def mock_handler_deps(self):
        """Mock handler dependencies for isolated testing."""
        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 0,
                            "articles_published": 0,
                        }
                        yield {"run": mock_run}

    def test_handler_rejects_whitespace_only_search_term(self, mock_handler_deps):
        """Whitespace-only search term should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "   "}, None)

        assert response["statusCode"] == 400

    def test_handler_accepts_unicode_search_term(self, mock_handler_deps):
        """Unicode characters in search term should be accepted."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "日本語テスト"}, None)

        assert response["statusCode"] == 200

    def test_handler_accepts_special_characters(self, mock_handler_deps):
        """Special characters should be accepted (API handles escaping)."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test & <script>alert('xss')</script>"}, None)

        # Should succeed - the Guardian API will handle encoding
        assert response["statusCode"] == 200

    def test_handler_accepts_sql_injection_attempt(self, mock_handler_deps):
        """SQL injection attempts should be passed through safely."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "'; DROP TABLE articles; --"}, None)

        # Should succeed - we don't use SQL, Guardian API handles this
        assert response["statusCode"] == 200

    def test_handler_accepts_very_long_search_term(self, mock_handler_deps):
        """Very long search terms should be accepted (API may truncate)."""
        from guardian_stream.handler import handler

        long_term = "a" * 1000
        response = handler({"search_term": long_term}, None)

        # Should succeed - Guardian API will handle length limits
        assert response["statusCode"] == 200

    def test_handler_accepts_newlines_in_search_term(self, mock_handler_deps):
        """Newlines in search term should be accepted."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test\nwith\nnewlines"}, None)

        assert response["statusCode"] == 200


class TestDateFuzzing:
    """Tests for unusual date inputs."""

    @pytest.fixture
    def mock_handler_deps(self):
        """Mock handler dependencies."""
        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 0,
                            "articles_published": 0,
                        }
                        yield {"run": mock_run}

    def test_handler_rejects_invalid_date_month(self, mock_handler_deps):
        """Invalid month should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": "2024-13-01"}, None)

        assert response["statusCode"] == 400

    def test_handler_rejects_invalid_date_day(self, mock_handler_deps):
        """Invalid day should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": "2024-02-30"}, None)

        assert response["statusCode"] == 400

    def test_handler_accepts_future_date(self, mock_handler_deps):
        """Future dates should be accepted (Guardian API returns empty)."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": "2099-01-01"}, None)

        # Should succeed - no articles will match, but that's fine
        assert response["statusCode"] == 200

    def test_handler_accepts_very_old_date(self, mock_handler_deps):
        """Very old dates should be accepted."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": "1900-01-01"}, None)

        assert response["statusCode"] == 200

    def test_handler_rejects_date_with_time(self, mock_handler_deps):
        """Date with time component should return 400."""
        from guardian_stream.handler import handler

        response = handler(
            {"search_term": "test", "date_from": "2024-01-01T12:00:00"}, None
        )

        assert response["statusCode"] == 400

    def test_handler_rejects_date_with_wrong_separator(self, mock_handler_deps):
        """Date with wrong separator should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": "2024/01/01"}, None)

        assert response["statusCode"] == 400


class TestEventStructureFuzzing:
    """Tests for unusual event structures."""

    @pytest.fixture
    def mock_handler_deps(self):
        """Mock handler dependencies."""
        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.return_value = {
                            "articles_found": 0,
                            "articles_published": 0,
                        }
                        yield {"run": mock_run}

    def test_handler_ignores_extra_fields(self, mock_handler_deps):
        """Extra fields in event should be ignored."""
        from guardian_stream.handler import handler

        response = handler(
            {
                "search_term": "test",
                "malicious_field": "ignored",
                "another_field": 12345,
            },
            None,
        )

        assert response["statusCode"] == 200

    def test_handler_handles_nested_search_term(self, mock_handler_deps):
        """Nested object as search_term should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": {"nested": "value"}}, None)

        # Should fail validation - not a string
        assert response["statusCode"] == 400

    def test_handler_handles_list_search_term(self, mock_handler_deps):
        """List as search_term should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": ["test", "values"]}, None)

        assert response["statusCode"] == 400

    def test_handler_handles_numeric_search_term(self, mock_handler_deps):
        """Numeric search_term should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": 12345}, None)

        assert response["statusCode"] == 400

    def test_handler_handles_boolean_search_term(self, mock_handler_deps):
        """Boolean search_term should return 400."""
        from guardian_stream.handler import handler

        response = handler({"search_term": True}, None)

        assert response["statusCode"] == 400

    def test_handler_handles_null_date_from(self, mock_handler_deps):
        """Explicit null date_from should be treated as missing."""
        from guardian_stream.handler import handler

        response = handler({"search_term": "test", "date_from": None}, None)

        assert response["statusCode"] == 200


class TestErrorMessageSecurity:
    """Tests ensuring error messages don't leak sensitive information."""

    def test_config_error_does_not_leak_secret_name(self):
        """Config errors should not expose environment variable names."""
        from guardian_stream.handler import handler

        secret_name = "my-super-secret-guardian-key"

        with patch(
            "guardian_stream.handler._init_error",
            ValueError(f"Could not find secret: {secret_name}"),
        ):
            response = handler({"search_term": "test"}, None)

        body = json.loads(response["body"])
        assert secret_name not in body["error"]
        assert "secret" not in body["error"].lower()

    def test_api_error_does_not_leak_endpoint(self):
        """API errors should not expose internal endpoints."""
        from guardian_stream.exceptions import GuardianAPIError
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.side_effect = GuardianAPIError(
                            "Failed to connect to https://content.guardianapis.com/search?api-key=SECRET",
                            status_code=500,
                        )

                        response = handler({"search_term": "test"}, None)

        body = json.loads(response["body"])
        assert "guardianapis.com" not in body["error"]
        assert "api-key" not in body["error"].lower()
        assert "SECRET" not in body["error"]

    def test_publisher_error_does_not_leak_stream_arn(self):
        """Publisher errors should not expose AWS resource ARNs."""
        from guardian_stream.exceptions import PublisherError
        from guardian_stream.handler import handler

        with patch("guardian_stream.handler._init_error", None):
            with patch("guardian_stream.handler._client", MagicMock()):
                with patch("guardian_stream.handler._publisher", MagicMock()):
                    with patch("guardian_stream.handler.run") as mock_run:
                        mock_run.side_effect = PublisherError(
                            "Failed to publish to arn:aws:kinesis:eu-west-2:123456789:stream/guardian-articles"
                        )

                        response = handler({"search_term": "test"}, None)

        body = json.loads(response["body"])
        assert "arn:aws" not in body["error"]
        assert "123456789" not in body["error"]
