"""Structured logging for CaroCorp API.

JSON structured logging with:
- Sensitive data sanitization
- Request context via ContextVars (request_id, tenant_id, user_id)
- ISO 8601 UTC timestamps
- Console formatter for development

Usage:
    from app.core.logging import get_logger, configure_logging

    logger = get_logger(__name__)
    logger.info("User action", extra={"user_id": 123})
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set


# ---------------------------------------------------------------------------
# Context variables — defaults are None (not 0 / "") to distinguish
# "not set" from "set to 0" in JSON output (fix M6).
# ---------------------------------------------------------------------------

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[Optional[int]] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


# ---------------------------------------------------------------------------
# Sensitive-data sanitization
# ---------------------------------------------------------------------------

SENSITIVE_FIELDS: Set[str] = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "session_id",
    "credit_card",
    "card_number",
    "cvv",
    "ssn",
    "social_security",
    "private_key",
    "encryption_key",
}

REDACTED = "[REDACTED]"


def sanitize_value(key: str, value: Any) -> Any:
    """Mask value if the key matches a sensitive field.

    Keeps the first 4 characters for debug when value is long enough.
    """
    key_lower = key.lower()
    if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
        if isinstance(value, str) and len(value) > 8:
            return f"{value[:4]}...{REDACTED}"
        return REDACTED
    return value


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize a dictionary, masking sensitive fields."""
    if not isinstance(data, dict):
        return data

    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = sanitize_value(key, value)
    return result


def mask_email(email: str) -> str:
    """Mask an email for logging: ``j***n@example.com``."""
    if not email or "@" not in email:
        return email or ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = f"{local[:1]}*"
    else:
        masked_local = f"{local[:1]}{'*' * (len(local) - 2)}{local[-1:]}"
    return f"{masked_local}@{domain}"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_LOGRECORD_BUILTIN_ATTRS = {
    "name", "msg", "args", "created", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs",
    "pathname", "process", "processName", "relativeCreated",
    "stack_info", "exc_info", "exc_text", "thread", "threadName",
    "message", "asctime", "taskName",
}


class JSONFormatter(logging.Formatter):
    """Produce structured JSON log lines.

    Automatically includes timestamp (UTC), level, logger name, message,
    and context vars (request_id, tenant_id, user_id) when set.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Context vars — only include when set
        request_id = request_id_var.get()
        if request_id is not None:
            log_entry["request_id"] = request_id

        tenant_id = tenant_id_var.get()
        if tenant_id is not None:
            log_entry["tenant_id"] = tenant_id

        user_id = user_id_var.get()
        if user_id is not None:
            log_entry["user_id"] = user_id

        # Extra fields (everything the caller passed that isn't a builtin)
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _LOGRECORD_BUILTIN_ATTRS and not k.startswith("_")
        }
        if extra_fields:
            log_entry["extra"] = sanitize_dict(extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable coloured output for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET

        parts = [
            f"{color}[{record.levelname}]{reset}",
            record.name,
            "-",
            record.getMessage(),
        ]

        request_id = request_id_var.get()
        if request_id is not None:
            parts.append(f"(request_id={request_id[:8]}...)")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
    include_console: bool = True,
) -> None:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: Use JSON formatter when True, console formatter when False.
        include_console: Add a stdout handler (almost always True).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplication on re-configure
    root_logger.handlers.clear()

    if include_console:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        handler.setFormatter(JSONFormatter() if json_format else ConsoleFormatter())
        root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger (typically called with ``__name__``)."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Request context helpers
# ---------------------------------------------------------------------------

def set_request_context(
    request_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """Set context vars for the current request (used by middleware)."""
    if request_id is not None:
        request_id_var.set(request_id)
    if tenant_id is not None:
        tenant_id_var.set(tenant_id)
    if user_id is not None:
        user_id_var.set(user_id)


def clear_request_context() -> None:
    """Reset context vars to ``None`` after request completes."""
    request_id_var.set(None)
    tenant_id_var.set(None)
    user_id_var.set(None)
