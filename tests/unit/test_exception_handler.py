"""Tests unitaires pour app.middleware.exception_handler.

Verifie :
- AppException -> JSON avec bon status_code et error_code
- HTTPException -> JSON standardise
- ValidationError -> JSON 422 avec champs formates
- Exception generique -> 500 sans fuite d'info (fix M7)
- Exception infrastructure -> 503
- Format de reponse standard (success, error, message, request_id)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.exceptions import (
    AppException,
    BadRequest,
    InvalidCredentials,
    NotFound,
    PermissionDenied,
    RateLimitExceeded,
    TenantMismatch,
)
from app.middleware.exception_handler import (
    create_error_response,
    register_exception_handlers,
)


# ---------------------------------------------------------------------------
# App de test isolee
# ---------------------------------------------------------------------------

def _create_test_app() -> FastAPI:
    """Cree une mini-app avec exception handlers enregistres."""
    app = FastAPI()
    register_exception_handlers(app)

    # Injecte un request_id factice via un middleware simple
    from starlette.middleware.base import BaseHTTPMiddleware

    class FakeRequestIDMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.request_id = "test-request-id"
            return await call_next(request)

    app.add_middleware(FakeRequestIDMiddleware)

    @app.get("/raise-not-found")
    async def raise_not_found():
        raise NotFound("Customer")

    @app.get("/raise-invalid-credentials")
    async def raise_invalid_credentials():
        raise InvalidCredentials()

    @app.get("/raise-permission-denied")
    async def raise_permission_denied():
        raise PermissionDenied()

    @app.get("/raise-tenant-mismatch")
    async def raise_tenant_mismatch():
        raise TenantMismatch()

    @app.get("/raise-bad-request")
    async def raise_bad_request():
        raise BadRequest("Missing field 'name'")

    @app.get("/raise-rate-limit")
    async def raise_rate_limit():
        raise RateLimitExceeded(retry_after=60)

    @app.get("/raise-app-exception")
    async def raise_app_exception():
        raise AppException("Something went wrong", details={"key": "value"})

    @app.get("/raise-generic")
    async def raise_generic():
        raise RuntimeError("Unexpected bug")

    @app.get("/raise-connection-error")
    async def raise_connection_error():
        raise ConnectionError("Database unreachable")

    @app.get("/raise-timeout")
    async def raise_timeout():
        raise TimeoutError("Query timed out")

    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.get("/raise-http-404")
    async def raise_http_404():
        raise StarletteHTTPException(status_code=404, detail="Page not found")

    @app.get("/raise-http-429")
    async def raise_http_429():
        raise StarletteHTTPException(status_code=429, detail="Too many requests")

    from pydantic import BaseModel

    class StrictModel(BaseModel):
        name: str
        age: int

    @app.post("/validate")
    async def validate_body(body: StrictModel):
        return {"ok": True}

    return app


@pytest.fixture()
def test_client():
    app = _create_test_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ===================================================================
# create_error_response (helper)
# ===================================================================

class TestCreateErrorResponse:
    """Tests pour la fonction helper create_error_response."""

    def test_format_minimal(self):
        """Reponse minimale avec success, error, message."""
        resp = create_error_response(400, "BAD_REQUEST", "Invalid input")
        assert resp.status_code == 400
        import json
        body = json.loads(resp.body)
        assert body["success"] is False
        assert body["error"] == "BAD_REQUEST"
        assert body["message"] == "Invalid input"

    def test_avec_details(self):
        """Les details optionnels sont inclus."""
        resp = create_error_response(
            422, "VALIDATION_ERROR", "Invalid",
            details={"field": "email"},
        )
        import json
        body = json.loads(resp.body)
        assert body["details"] == {"field": "email"}

    def test_avec_request_id(self):
        """Le request_id optionnel est inclus."""
        resp = create_error_response(
            500, "INTERNAL_ERROR", "Oops",
            request_id="req-123",
        )
        import json
        body = json.loads(resp.body)
        assert body["request_id"] == "req-123"

    def test_sans_details_ni_request_id(self):
        """Sans details ni request_id, ces champs sont absents."""
        resp = create_error_response(400, "BAD_REQUEST", "Bad")
        import json
        body = json.loads(resp.body)
        assert "details" not in body
        assert "request_id" not in body

    def test_avec_errors_list(self):
        """La liste d'erreurs optionnelle est incluse."""
        errors = [{"field": "name", "message": "required"}]
        resp = create_error_response(
            422, "VALIDATION_ERROR", "Errors",
            errors=errors,
        )
        import json
        body = json.loads(resp.body)
        assert body["errors"] == errors


# ===================================================================
# AppException handlers
# ===================================================================

class TestAppExceptionHandler:
    """Tests pour le handler d'exceptions applicatives."""

    def test_not_found(self, test_client):
        """NotFound('Customer') -> 404 avec message personnalise."""
        resp = test_client.get("/raise-not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "NOT_FOUND"
        assert "Customer" in body["message"]
        assert body.get("request_id") == "test-request-id"

    def test_invalid_credentials(self, test_client):
        """InvalidCredentials -> 401."""
        resp = test_client.get("/raise-invalid-credentials")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "INVALID_CREDENTIALS"

    def test_permission_denied(self, test_client):
        """PermissionDenied -> 403."""
        resp = test_client.get("/raise-permission-denied")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"] == "PERMISSION_DENIED"

    def test_tenant_mismatch(self, test_client):
        """TenantMismatch -> 403."""
        resp = test_client.get("/raise-tenant-mismatch")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"] == "TENANT_MISMATCH"

    def test_bad_request_avec_message(self, test_client):
        """BadRequest avec message custom -> 400."""
        resp = test_client.get("/raise-bad-request")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "BAD_REQUEST"
        assert "name" in body["message"]

    def test_rate_limit_exceeded(self, test_client):
        """RateLimitExceeded -> 429."""
        resp = test_client.get("/raise-rate-limit")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "RATE_LIMIT_EXCEEDED"

    def test_app_exception_base_avec_details(self, test_client):
        """AppException avec details -> 500."""
        resp = test_client.get("/raise-app-exception")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "INTERNAL_ERROR"
        assert body["message"] == "Something went wrong"


# ===================================================================
# HTTPException handler
# ===================================================================

class TestHTTPExceptionHandler:
    """Tests pour le handler de HTTPException standard."""

    def test_http_404(self, test_client):
        """StarletteHTTPException 404 -> JSON standardise."""
        resp = test_client.get("/raise-http-404")
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "NOT_FOUND"
        assert body["message"] == "Page not found"

    def test_http_429(self, test_client):
        """StarletteHTTPException 429 -> JSON standardise."""
        resp = test_client.get("/raise-http-429")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "TOO_MANY_REQUESTS"


# ===================================================================
# Validation handler
# ===================================================================

class TestValidationExceptionHandler:
    """Tests pour le handler de validation Pydantic."""

    def test_validation_error_422(self, test_client):
        """Un body invalide -> 422 avec champs formates."""
        resp = test_client.post("/validate", json={"name": 123})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "VALIDATION_ERROR"
        assert body["message"] == "Request validation failed"

    def test_validation_error_contient_errors_list(self, test_client):
        """La liste errors contient les champs en erreur."""
        resp = test_client.post("/validate", json={})
        assert resp.status_code == 422
        body = resp.json()
        # Doit contenir au moins les champs manquants (name, age)
        assert "errors" in body
        fields = [e["field"] for e in body["errors"]]
        assert any("name" in f for f in fields)
        assert any("age" in f for f in fields)


# ===================================================================
# Generic exception handler (fix M7)
# ===================================================================

class TestGenericExceptionHandler:
    """Tests pour le handler catch-all avec categorisation isinstance (fix M7)."""

    def test_runtime_error_500(self, test_client):
        """RuntimeError -> 500 sans fuite d'info interne."""
        resp = test_client.get("/raise-generic")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "INTERNAL_ERROR"
        # Le message interne NE doit PAS etre expose
        assert "Unexpected bug" not in body["message"]
        assert body["message"] == "An unexpected error occurred"

    def test_connection_error_503(self, test_client):
        """ConnectionError -> 503 SERVICE_UNAVAILABLE (fix M7 isinstance)."""
        resp = test_client.get("/raise-connection-error")
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"] == "SERVICE_UNAVAILABLE"
        # Pas de fuite du message interne
        assert "Database unreachable" not in body["message"]

    def test_timeout_error_503(self, test_client):
        """TimeoutError -> 503 SERVICE_UNAVAILABLE."""
        resp = test_client.get("/raise-timeout")
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"] == "SERVICE_UNAVAILABLE"

    def test_request_id_dans_response(self, test_client):
        """Le request_id est inclus dans toutes les reponses d'erreur."""
        resp = test_client.get("/raise-generic")
        body = resp.json()
        assert body.get("request_id") == "test-request-id"
