"""Application exceptions for CaroCorp API.

Hierarchy of business exceptions automatically converted to HTTP responses
by the exception handler middleware.

Usage:
    from app.core.exceptions import NotFound, InvalidCredentials
    raise NotFound("Customer")
    raise InvalidCredentials()

Phase 1 only — MFA, Session, Storage, and Token-replay exceptions will be
added in later phases when the corresponding features are implemented.
"""

from datetime import datetime
from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for all application errors.

    Subclasses define ``status_code``, ``error_code``, and a default
    ``message`` as class attributes.  Instances can override the message
    and supply additional ``details``.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the exception for a JSON response body."""
        result: Dict[str, Any] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# ── Authentication (401) ─────────────────────────────────────────────────

class InvalidCredentials(AppException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"


class TokenExpired(AppException):
    status_code = 401
    error_code = "TOKEN_EXPIRED"
    message = "Token has expired"


class TokenInvalid(AppException):
    status_code = 401
    error_code = "TOKEN_INVALID"
    message = "Invalid token"


class TokenRevoked(AppException):
    status_code = 401
    error_code = "TOKEN_REVOKED"
    message = "Token has been revoked"


class TokenReplayDetected(AppException):
    status_code = 401
    error_code = "TOKEN_REPLAY_DETECTED"
    message = "Token reuse detected — all sessions revoked"


# ── Authorisation (403) ──────────────────────────────────────────────────

class AccountLocked(AppException):
    status_code = 403
    error_code = "ACCOUNT_LOCKED"
    message = "Account is temporarily locked"

    def __init__(
        self,
        until: Optional[datetime] = None,
        minutes: Optional[int] = None,
    ):
        details: Dict[str, Any] = {}
        if until is not None:
            details["locked_until"] = until.isoformat()
        if minutes is not None:
            details["retry_after_minutes"] = minutes
        super().__init__(details=details)


class AccountInactive(AppException):
    status_code = 403
    error_code = "ACCOUNT_INACTIVE"
    message = "Account is inactive"


class PermissionDenied(AppException):
    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "You don't have permission to perform this action"


class TenantMismatch(AppException):
    status_code = 403
    error_code = "TENANT_MISMATCH"
    message = "Tenant access denied"


# ── Resources (404 / 409) ────────────────────────────────────────────────

class NotFound(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"

    def __init__(self, resource: Optional[str] = None):
        message = f"{resource} not found" if resource else None
        super().__init__(message=message)


class AlreadyExists(AppException):
    status_code = 409
    error_code = "ALREADY_EXISTS"
    message = "Resource already exists"


class EmailAlreadyExists(AlreadyExists):
    error_code = "EMAIL_ALREADY_EXISTS"
    message = "Email is already registered"


# ── Validation (400 / 422) ───────────────────────────────────────────────

class BadRequest(AppException):
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "Invalid request"


class BusinessValidationError(AppException):
    status_code = 422
    error_code = "BUSINESS_VALIDATION_ERROR"
    message = "Business rule validation failed"


class PasswordTooWeak(AppException):
    status_code = 422
    error_code = "PASSWORD_TOO_WEAK"
    message = "Password does not meet security requirements"


# ── Rate Limiting (429) ──────────────────────────────────────────────────

class RateLimitExceeded(AppException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests"

    def __init__(self, retry_after: Optional[int] = None):
        details: Dict[str, Any] = {}
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after
        super().__init__(details=details)
