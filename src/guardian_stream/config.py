"""Configuration management via environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    guardian_api_key: str
    kinesis_stream_name: str

    @field_validator("guardian_api_key", "kinesis_stream_name")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        """Reject empty or whitespace-only values."""
        if not v or not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v
