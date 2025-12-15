"""Custom exceptions for Guardian API client."""


class GuardianAPIError(Exception):
    """Raised when the Guardian API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class RateLimitError(GuardianAPIError):
    """Raised when the Guardian API returns a 429 rate limit response."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, status_code=429)
