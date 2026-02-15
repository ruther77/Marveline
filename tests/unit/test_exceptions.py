"""Tests unitaires pour app.core.exceptions.

Verifie :
- Chaque exception a le bon status_code et error_code
- to_dict() retourne le bon format
- NotFound("Customer") -> "Customer not found"
- AccountLocked avec until/minutes -> details remplis
- RateLimitExceeded avec retry_after -> details remplis
- Heritage : EmailAlreadyExists herite de AlreadyExists
"""

from datetime import datetime, timezone

import pytest

from app.core.exceptions import (
    AccountInactive,
    AccountLocked,
    AlreadyExists,
    AppException,
    BadRequest,
    BusinessValidationError,
    EmailAlreadyExists,
    InvalidCredentials,
    NotFound,
    PasswordTooWeak,
    PermissionDenied,
    RateLimitExceeded,
    TenantMismatch,
    TokenExpired,
    TokenInvalid,
)


# ===================================================================
# AppException (base)
# ===================================================================

class TestAppException:
    """Tests pour la classe de base AppException."""

    def test_defaults(self):
        """AppException a les defaults corrects."""
        exc = AppException()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.message == "An unexpected error occurred"
        assert exc.details == {}

    def test_message_custom(self):
        """On peut passer un message custom."""
        exc = AppException(message="Custom error")
        assert exc.message == "Custom error"

    def test_details_custom(self):
        """On peut passer des details."""
        exc = AppException(details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_to_dict_sans_details(self):
        """to_dict sans details ne contient que error et message."""
        exc = AppException()
        d = exc.to_dict()
        assert d == {
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        }
        assert "details" not in d

    def test_to_dict_avec_details(self):
        """to_dict avec details les inclut."""
        exc = AppException(details={"reason": "test"})
        d = exc.to_dict()
        assert d["details"] == {"reason": "test"}

    def test_str_est_message(self):
        """str(exc) retourne le message."""
        exc = AppException(message="boom")
        assert str(exc) == "boom"


# ===================================================================
# Authentication (401)
# ===================================================================

class TestAuthExceptions:
    """Tests pour les exceptions 401."""

    def test_invalid_credentials(self):
        exc = InvalidCredentials()
        assert exc.status_code == 401
        assert exc.error_code == "INVALID_CREDENTIALS"
        assert exc.message == "Invalid email or password"

    def test_token_expired(self):
        exc = TokenExpired()
        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_EXPIRED"

    def test_token_invalid(self):
        exc = TokenInvalid()
        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_INVALID"


# ===================================================================
# Authorisation (403)
# ===================================================================

class TestAuthzExceptions:
    """Tests pour les exceptions 403."""

    def test_account_locked_sans_details(self):
        """AccountLocked sans params a le bon message."""
        exc = AccountLocked()
        assert exc.status_code == 403
        assert exc.error_code == "ACCOUNT_LOCKED"
        assert exc.message == "Account is temporarily locked"
        assert exc.details == {}

    def test_account_locked_avec_until(self):
        """AccountLocked avec until peuple details.locked_until."""
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        exc = AccountLocked(until=dt)
        assert exc.details["locked_until"] == dt.isoformat()

    def test_account_locked_avec_minutes(self):
        """AccountLocked avec minutes peuple details.retry_after_minutes."""
        exc = AccountLocked(minutes=15)
        assert exc.details["retry_after_minutes"] == 15

    def test_account_locked_avec_les_deux(self):
        """AccountLocked avec until + minutes peuple les deux."""
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        exc = AccountLocked(until=dt, minutes=15)
        assert "locked_until" in exc.details
        assert exc.details["retry_after_minutes"] == 15

    def test_account_inactive(self):
        exc = AccountInactive()
        assert exc.status_code == 403
        assert exc.error_code == "ACCOUNT_INACTIVE"

    def test_permission_denied(self):
        exc = PermissionDenied()
        assert exc.status_code == 403
        assert exc.error_code == "PERMISSION_DENIED"

    def test_tenant_mismatch(self):
        exc = TenantMismatch()
        assert exc.status_code == 403
        assert exc.error_code == "TENANT_MISMATCH"


# ===================================================================
# Resources (404 / 409)
# ===================================================================

class TestResourceExceptions:
    """Tests pour les exceptions de resources."""

    def test_not_found_default(self):
        """NotFound sans resource -> message generique."""
        exc = NotFound()
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"
        assert exc.message == "Resource not found"

    def test_not_found_avec_resource(self):
        """NotFound('Customer') -> 'Customer not found'."""
        exc = NotFound("Customer")
        assert exc.message == "Customer not found"

    def test_not_found_to_dict(self):
        """to_dict de NotFound('Product')."""
        exc = NotFound("Product")
        d = exc.to_dict()
        assert d["error"] == "NOT_FOUND"
        assert d["message"] == "Product not found"

    def test_already_exists(self):
        exc = AlreadyExists()
        assert exc.status_code == 409
        assert exc.error_code == "ALREADY_EXISTS"

    def test_email_already_exists_herite(self):
        """EmailAlreadyExists herite de AlreadyExists."""
        exc = EmailAlreadyExists()
        assert isinstance(exc, AlreadyExists)
        assert exc.status_code == 409
        assert exc.error_code == "EMAIL_ALREADY_EXISTS"
        assert exc.message == "Email is already registered"


# ===================================================================
# Validation (400 / 422)
# ===================================================================

class TestValidationExceptions:
    """Tests pour les exceptions de validation."""

    def test_bad_request(self):
        exc = BadRequest()
        assert exc.status_code == 400
        assert exc.error_code == "BAD_REQUEST"

    def test_bad_request_message_custom(self):
        exc = BadRequest(message="Invalid date format")
        assert exc.message == "Invalid date format"

    def test_business_validation_error(self):
        exc = BusinessValidationError()
        assert exc.status_code == 422
        assert exc.error_code == "BUSINESS_VALIDATION_ERROR"

    def test_password_too_weak(self):
        exc = PasswordTooWeak()
        assert exc.status_code == 422
        assert exc.error_code == "PASSWORD_TOO_WEAK"


# ===================================================================
# Rate Limiting (429)
# ===================================================================

class TestRateLimitExceeded:
    """Tests pour RateLimitExceeded."""

    def test_sans_retry_after(self):
        exc = RateLimitExceeded()
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.details == {}

    def test_avec_retry_after(self):
        """retry_after peuple details.retry_after_seconds."""
        exc = RateLimitExceeded(retry_after=60)
        assert exc.details["retry_after_seconds"] == 60

    def test_to_dict_avec_retry(self):
        """to_dict inclut les details retry."""
        exc = RateLimitExceeded(retry_after=30)
        d = exc.to_dict()
        assert d["details"]["retry_after_seconds"] == 30


# ===================================================================
# Heritage et isinstance
# ===================================================================

class TestHierarchie:
    """Tests pour l'heritage des exceptions."""

    def test_toutes_heritent_de_app_exception(self):
        """Toutes les exceptions heritent de AppException."""
        exceptions = [
            InvalidCredentials(),
            TokenExpired(),
            TokenInvalid(),
            AccountLocked(),
            AccountInactive(),
            PermissionDenied(),
            TenantMismatch(),
            NotFound(),
            AlreadyExists(),
            EmailAlreadyExists(),
            BadRequest(),
            BusinessValidationError(),
            PasswordTooWeak(),
            RateLimitExceeded(),
        ]
        for exc in exceptions:
            assert isinstance(exc, AppException), f"{type(exc).__name__} n'herite pas de AppException"

    def test_toutes_heritent_de_exception(self):
        """Toutes les exceptions heritent de Exception (catchable)."""
        exc = NotFound("test")
        assert isinstance(exc, Exception)
