"""Custom exceptions for Trade-Alpha API."""

from typing import Optional


class TradeAlphaException(Exception):
    """Base exception for all Trade-Alpha business errors."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    detail: str = "An internal error occurred"

    def __init__(self, detail: Optional[str] = None):
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundException(TradeAlphaException):
    """Resource not found exception."""
    status_code = 404
    error_code = "NOT_FOUND"
    detail = "Resource not found"


class BadRequestException(TradeAlphaException):
    """Bad request exception."""
    status_code = 400
    error_code = "BAD_REQUEST"
    detail = "Invalid request"


class ConflictException(TradeAlphaException):
    """Resource conflict exception."""
    status_code = 409
    error_code = "CONFLICT"
    detail = "Resource conflict"


class UnauthorizedException(TradeAlphaException):
    """Unauthorized exception."""
    status_code = 401
    error_code = "UNAUTHORIZED"
    detail = "Unauthorized"


class ForbiddenException(TradeAlphaException):
    """Forbidden exception."""
    status_code = 403
    error_code = "FORBIDDEN"
    detail = "Forbidden"


class ValidationException(TradeAlphaException):
    """Validation exception."""
    status_code = 422
    error_code = "VALIDATION_ERROR"
    detail = "Validation failed"

    def __init__(self, detail: str, field_errors: Optional[dict] = None):
        super().__init__(detail)
        self.field_errors = field_errors or {}
