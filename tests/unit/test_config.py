"""Unit tests for configuration loading."""

import pytest
from pydantic import ValidationError

from guardian_stream.config import Config


class TestConfig:
    """Tests for the Config model."""

    def test_config_requires_api_key(self, monkeypatch):
        """Config without GUARDIAN_API_KEY should raise ValidationError."""
        monkeypatch.delenv("GUARDIAN_API_KEY", raising=False)
        monkeypatch.setenv("KINESIS_STREAM_NAME", "test-stream")

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "guardian_api_key" in str(exc_info.value).lower()

    def test_config_requires_stream_name(self, monkeypatch):
        """Config without KINESIS_STREAM_NAME should raise ValidationError."""
        monkeypatch.setenv("GUARDIAN_API_KEY", "test-api-key")
        monkeypatch.delenv("KINESIS_STREAM_NAME", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "kinesis_stream_name" in str(exc_info.value).lower()

    def test_config_loads_from_environment(self, monkeypatch):
        """Config should load values from environment variables."""
        monkeypatch.setenv("GUARDIAN_API_KEY", "my-api-key")
        monkeypatch.setenv("KINESIS_STREAM_NAME", "my-stream")

        config = Config()

        assert config.guardian_api_key == "my-api-key"
        assert config.kinesis_stream_name == "my-stream"

    def test_config_rejects_empty_api_key(self, monkeypatch):
        """Config with empty string API key should raise ValidationError."""
        monkeypatch.setenv("GUARDIAN_API_KEY", "")
        monkeypatch.setenv("KINESIS_STREAM_NAME", "test-stream")

        with pytest.raises(ValidationError):
            Config()

    def test_config_rejects_whitespace_api_key(self, monkeypatch):
        """Config with whitespace-only API key should raise ValidationError."""
        monkeypatch.setenv("GUARDIAN_API_KEY", "   ")
        monkeypatch.setenv("KINESIS_STREAM_NAME", "test-stream")

        with pytest.raises(ValidationError):
            Config()
