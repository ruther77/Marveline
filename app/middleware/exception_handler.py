"""Gestionnaire global d'exceptions pour CaroCorp API.

Convertit toutes les exceptions en reponses JSON standardisees.
Fix M7 : utilise isinstance() au lieu de comparer les noms de type (string).

Format de reponse :
    {
        "success": false,
        "error": "ERROR_CODE",
        "message": "Description lisible",
        "details": {},
        "request_id": "uuid"
    }
"""

import logging
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    errors: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """Cree une reponse d'erreur JSON standardisee."""
    content: Dict[str, Any] = {
        "success": False,
        "error": error_code,
        "message": message,
        "detail": message,  # Compatibilite FastAPI (convention HTTPException)
    }

    if details:
        content["details"] = details

    if errors:
        content["errors"] = errors

    if request_id:
        content["request_id"] = request_id

    return JSONResponse(status_code=status_code, content=content)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler pour les exceptions applicatives (AppException et sous-classes)."""
    request_id = getattr(request.state, "request_id", None)

    if exc.status_code >= 500:
        logger.error(
            "AppException: %s - %s",
            exc.error_code,
            exc.message,
            extra={"request_id": request_id, "details": exc.details},
        )
    else:
        logger.info(
            "AppException: %s - %s",
            exc.error_code,
            exc.message,
            extra={"request_id": request_id},
        )

    return create_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details if exc.details else None,
        request_id=request_id,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handler pour les HTTPException standard de FastAPI/Starlette."""
    request_id = getattr(request.state, "request_id", None)

    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }
    error_code = error_codes.get(exc.status_code, "HTTP_ERROR")

    # Support structured detail (e.g. brute force escalation info)
    if isinstance(exc.detail, dict):
        message = exc.detail.get("message", "Error")
        content: Dict[str, Any] = {
            "success": False,
            "error": error_code,
            "message": message,
            "detail": exc.detail,
        }
        if request_id:
            content["request_id"] = request_id
        return JSONResponse(status_code=exc.status_code, content=content)

    return create_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=str(exc.detail),
        request_id=request_id,
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError],
) -> JSONResponse:
    """Handler pour les erreurs de validation Pydantic."""
    request_id = getattr(request.state, "request_id", None)

    raw_errors = exc.errors() if hasattr(exc, "errors") else []
    formatted_errors = [
        {
            "field": ".".join(str(part) for part in error.get("loc", [])),
            "message": error.get("msg", "Validation error"),
            "type": error.get("type", "unknown"),
        }
        for error in raw_errors
    ]

    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": formatted_errors},
        errors=formatted_errors,
        request_id=request_id,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler catch-all pour les exceptions non gerees.

    Fix M7 : categorisation par isinstance() au lieu de comparaison de noms.
    Ne jamais exposer les details internes en production.
    """
    request_id = getattr(request.state, "request_id", None)

    # Import paresseux pour eviter les imports circulaires au demarrage
    # et ne pas forcer la dependance sqlalchemy si pas utilise
    is_infra = False
    try:
        from sqlalchemy.exc import (
            DatabaseError,
            InterfaceError,
            OperationalError,
        )
        if isinstance(exc, (OperationalError, InterfaceError, DatabaseError)):
            is_infra = True
    except ImportError:
        pass

    if isinstance(exc, (ConnectionError, TimeoutError, BrokenPipeError, OSError)):
        is_infra = True

    if is_infra:
        logger.error(
            "Erreur infrastructure: %s: %s",
            type(exc).__name__,
            exc,
            extra={"request_id": request_id, "category": "infrastructure"},
        )
        return create_error_response(
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            message="An unexpected error occurred",
            request_id=request_id,
        )

    # Bug inattendu — log CRITICAL avec stack trace
    logger.critical(
        "Exception non geree: %s: %s",
        type(exc).__name__,
        exc,
        extra={"request_id": request_id, "category": "bug"},
        exc_info=True,
    )

    return create_error_response(
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# Enregistrement
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Enregistre tous les exception handlers sur l'application FastAPI."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
