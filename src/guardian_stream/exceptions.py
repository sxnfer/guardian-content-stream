"""Custom exceptions for Guardian Stream service."""


class GuardianAPIError(Exception):
    """Raised when the Guardian API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class RateLimitError(GuardianAPIError):
    """Raised when the Guardian API returns a 429 rate limit response."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, status_code=429)


class PublisherError(Exception):
    """Raised when publishing to Kinesis fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        self.original_error = original_error
        super().__init__(message)


class RecordTooLargeError(PublisherError):
    """Raised when a record exceeds Kinesis maximum size (1MB)."""

    MAX_RECORD_SIZE = 1024 * 1024  # 1MB in bytes

    def __init__(self, record_size: int) -> None:
        self.record_size = record_size
        message = f"Record size {record_size} bytes exceeds maximum {self.MAX_RECORD_SIZE} bytes"
        super().__init__(message)
