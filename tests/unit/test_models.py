"""Unit tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from guardian_stream.models import Article


class TestArticleModel:
    """Tests for the Article Pydantic model."""

    def test_valid_article_is_accepted(self):
        """Article with all required fields should validate."""
        article = Article(
            webPublicationDate="2023-11-21T11:11:31Z",
            webTitle="Test Article Title",
            webUrl="https://www.theguardian.com/test/article",
        )

        assert article.webTitle == "Test Article Title"
        assert article.webUrl == "https://www.theguardian.com/test/article"

    def test_article_requires_web_url(self):
        """Article without webUrl should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Article(
                webPublicationDate="2023-11-21T11:11:31Z",
                webTitle="Test Article Title",
            )

        assert "webUrl" in str(exc_info.value)

    def test_article_requires_web_title(self):
        """Article without webTitle should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Article(
                webPublicationDate="2023-11-21T11:11:31Z",
                webUrl="https://www.theguardian.com/test/article",
            )

        assert "webTitle" in str(exc_info.value)

    def test_article_requires_publication_date(self):
        """Article without webPublicationDate should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Article(
                webTitle="Test Article Title",
                webUrl="https://www.theguardian.com/test/article",
            )

        assert "webPublicationDate" in str(exc_info.value)

    def test_publication_date_must_be_valid_datetime(self):
        """Article with malformed date should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Article(
                webPublicationDate="not-a-valid-date",
                webTitle="Test Article Title",
                webUrl="https://www.theguardian.com/test/article",
            )

        assert "webPublicationDate" in str(exc_info.value)

    def test_article_accepts_optional_content_preview(self):
        """Article should accept optional content_preview field."""
        article = Article(
            webPublicationDate="2023-11-21T11:11:31Z",
            webTitle="Test Article Title",
            webUrl="https://www.theguardian.com/test/article",
            content_preview="This is a preview of the article content...",
        )

        assert article.content_preview == "This is a preview of the article content..."

    def test_article_without_content_preview_is_valid(self):
        """Article without content_preview should still be valid."""
        article = Article(
            webPublicationDate="2023-11-21T11:11:31Z",
            webTitle="Test Article Title",
            webUrl="https://www.theguardian.com/test/article",
        )

        assert article.content_preview is None
