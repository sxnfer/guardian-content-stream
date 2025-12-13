"""Pydantic models for Guardian API data."""

from datetime import datetime

from pydantic import BaseModel


class Article(BaseModel):
    """Represents a Guardian article for publishing to Kinesis."""

    webPublicationDate: datetime
    webTitle: str
    webUrl: str
    content_preview: str | None = None
