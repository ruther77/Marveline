"""Core modules CaroCorp."""

from app.core.rate_limiter import RateLimiter
from app.core.metrics import metrics_endpoint
from app.core.rate_limit_utils import (
    determine_rate_limit_scope,
    get_user_id_from_jwt,
)

from app.core.exceptions import (
    AppException,
    InvalidCredentials,
    TokenExpired,
    TokenInvalid,
    AccountLocked,
    AccountInactive,
    PermissionDenied,
    TenantMismatch,
    NotFound,
    AlreadyExists,
    EmailAlreadyExists,
    BadRequest,
    BusinessValidationError,
    PasswordTooWeak,
    RateLimitExceeded,
)

from app.core.logging import (
    configure_logging,
    get_logger,
    set_request_context,
    clear_request_context,
    sanitize_dict,
    mask_email,
    request_id_var,
    tenant_id_var,
    user_id_var,
)

from app.core.validators import (
    SecurityValidators,
    validate_email_safe,
    validate_text_safe,
    validate_username_safe,
    validate_path_safe,
)

from app.core.password_policy import validate_password

from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret

__all__ = [
    # Rate limiter & metrics
    "RateLimiter",
    "metrics_endpoint",
    "determine_rate_limit_scope",
    "get_user_id_from_jwt",
    # Exceptions
    "AppException",
    "InvalidCredentials",
    "TokenExpired",
    "TokenInvalid",
    "AccountLocked",
    "AccountInactive",
    "PermissionDenied",
    "TenantMismatch",
    "NotFound",
    "AlreadyExists",
    "EmailAlreadyExists",
    "BadRequest",
    "BusinessValidationError",
    "PasswordTooWeak",
    "RateLimitExceeded",
    # Logging
    "configure_logging",
    "get_logger",
    "set_request_context",
    "clear_request_context",
    "sanitize_dict",
    "mask_email",
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
    # Validators
    "SecurityValidators",
    "validate_email_safe",
    "validate_text_safe",
    "validate_username_safe",
    "validate_path_safe",
    # Password policy
    "validate_password",
    # Crypto
    "encrypt_totp_secret",
    "decrypt_totp_secret",
]
