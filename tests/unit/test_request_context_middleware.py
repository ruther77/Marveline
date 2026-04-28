"""Tests unitaires pour app.middleware.request_context.

Verifie :
- X-Request-ID genere si absent, propage si present
- tenant_id et user_id extraits depuis le JWT
- ContextVars positionnees et nettoyees correctement
- Response contient le header X-Request-ID
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.logging import request_id_var, tenant_id_var, user_id_var
from app.core.security import create_access_token
from app.middleware.request_context import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    _extract_jwt_claims,
)


# ---------------------------------------------------------------------------
# App de test isolee (pas l'app principale)
# ---------------------------------------------------------------------------

def _create_test_app() -> FastAPI:
    """Cree une mini-app FastAPI avec uniquement le RequestContextMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        """Retourne les valeurs du contexte pour verification."""
        return JSONResponse({
            "request_id": getattr(request.state, "request_id", None),
            "tenant_id": getattr(request.state, "tenant_id", None),
            "user_id": getattr(request.state, "user_id", None),
            "ctx_request_id": request_id_var.get(),
            "ctx_tenant_id": tenant_id_var.get(),
            "ctx_user_id": user_id_var.get(),
        })

    return app


@pytest.fixture()
def test_app():
    return _create_test_app()


@pytest.fixture()
def test_client(test_app):
    with TestClient(test_app) as client:
        yield client


# ===================================================================
# X-Request-ID
# ===================================================================

class TestRequestID:
    """Tests pour la generation et propagation du X-Request-ID."""

    def test_genere_request_id_si_absent(self, test_client):
        """Un UUID v4 est genere quand le header X-Request-ID est absent."""
        response = test_client.get("/test")
        assert response.status_code == 200

        # Le header doit etre present dans la response
        assert REQUEST_ID_HEADER in response.headers
        request_id = response.headers[REQUEST_ID_HEADER]

        # Doit etre un UUID v4 valide
        parsed = uuid.UUID(request_id, version=4)
        assert str(parsed) == request_id

    def test_propage_request_id_si_present(self, test_client):
        """Le X-Request-ID fourni par le client est propage."""
        custom_id = "custom-request-id-123"
        response = test_client.get("/test", headers={REQUEST_ID_HEADER: custom_id})
        assert response.status_code == 200

        # Le meme ID doit etre retourne dans la response
        assert response.headers[REQUEST_ID_HEADER] == custom_id

        # Et dans le body (request.state)
        body = response.json()
        assert body["request_id"] == custom_id

    def test_request_id_dans_request_state(self, test_client):
        """Le request_id est accessible via request.state."""
        response = test_client.get("/test")
        body = response.json()
        assert body["request_id"] is not None
        assert len(body["request_id"]) > 0


# ===================================================================
# JWT Claims extraction
# ===================================================================

class TestJWTClaimsExtraction:
    """Tests pour l'extraction des claims JWT."""

    def test_tenant_id_extrait_du_jwt(self, test_client):
        """Le tenant_id est extrait des claims JWT (fix M2)."""
        token = create_access_token({
            "sub": 42,
            "tenant_id": 7,
            "email": "test@example.com",
            "role": "staff",
        })
        response = test_client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = response.json()
        assert body["tenant_id"] == 7

    def test_user_id_extrait_du_jwt(self, test_client):
        """Le user_id (sub) est extrait et converti en int."""
        token = create_access_token({
            "sub": 42,
            "tenant_id": 1,
            "email": "test@example.com",
            "role": "staff",
        })
        response = test_client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = response.json()
        assert body["user_id"] == 42

    def test_pas_de_jwt_donne_none(self, test_client):
        """Sans header Authorization, tenant_id et user_id sont None."""
        response = test_client.get("/test")
        body = response.json()
        assert body["tenant_id"] is None
        assert body["user_id"] is None

    def test_jwt_invalide_donne_none(self, test_client):
        """Un JWT invalide ne bloque pas — retourne None."""
        response = test_client.get(
            "/test",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        body = response.json()
        assert body["tenant_id"] is None
        assert body["user_id"] is None

    def test_bearer_vide_donne_none(self, test_client):
        """'Bearer ' sans token retourne None."""
        response = test_client.get(
            "/test",
            headers={"Authorization": "Bearer "},
        )
        body = response.json()
        assert body["tenant_id"] is None
        assert body["user_id"] is None

    def test_pas_bearer_prefix_donne_none(self, test_client):
        """Un header Authorization sans 'Bearer ' prefix est ignore."""
        response = test_client.get(
            "/test",
            headers={"Authorization": "Basic abc123"},
        )
        body = response.json()
        assert body["tenant_id"] is None
        assert body["user_id"] is None


# ===================================================================
# ContextVars
# ===================================================================

class TestContextVars:
    """Tests pour la propagation des ContextVars."""

    def test_context_vars_positionnees_avec_jwt(self, test_client):
        """Les ContextVars refletent les claims JWT pendant la requete."""
        token = create_access_token({
            "sub": 10,
            "tenant_id": 3,
            "email": "ctx@example.com",
            "role": "admin",
        })
        response = test_client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = response.json()
        assert body["ctx_request_id"] is not None
        assert body["ctx_tenant_id"] == 3
        assert body["ctx_user_id"] == 10

    def test_context_vars_nettoyees_apres_requete(self, test_client):
        """Les ContextVars sont remises a None apres la requete (finally)."""
        token = create_access_token({
            "sub": 10,
            "tenant_id": 3,
            "email": "clean@example.com",
            "role": "staff",
        })
        test_client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Apres la requete, les ContextVars doivent etre nettoyees
        assert request_id_var.get() is None
        assert tenant_id_var.get() is None
        assert user_id_var.get() is None

    def test_context_vars_sans_jwt(self, test_client):
        """Sans JWT, request_id est set mais tenant/user restent None."""
        response = test_client.get("/test")
        body = response.json()
        assert body["ctx_request_id"] is not None
        assert body["ctx_tenant_id"] is None
        assert body["ctx_user_id"] is None


# ===================================================================
# _extract_jwt_claims (helper interne)
# ===================================================================

class TestExtractJWTClaims:
    """Tests pour le helper _extract_jwt_claims."""

    def test_claims_valides(self):
        """Retourne les claims pour un JWT valide."""
        from starlette.testclient import TestClient as _TC
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        token = create_access_token({
            "sub": 1,
            "tenant_id": 5,
            "email": "test@test.com",
            "role": "staff",
        })

        async def endpoint(request):
            claims = _extract_jwt_claims(request)
            return PlainTextResponse(str(claims.get("tenant_id")))

        app = Starlette(routes=[Route("/", endpoint)])
        client = _TC(app)
        response = client.get("/", headers={"Authorization": f"Bearer {token}"})
        assert response.text == "5"

    def test_pas_de_header_retourne_dict_vide(self):
        """Sans header Authorization, retourne {}."""
        from starlette.testclient import TestClient as _TC
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        async def endpoint(request):
            claims = _extract_jwt_claims(request)
            return PlainTextResponse(str(len(claims)))

        app = Starlette(routes=[Route("/", endpoint)])
        client = _TC(app)
        response = client.get("/")
        assert response.text == "0"

    def test_decode_token_exception_retourne_dict_vide(self):
        """Si decode_token leve une exception, retourne {} sans bloquer."""
        from starlette.testclient import TestClient as _TC
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import PlainTextResponse

        async def endpoint(request):
            claims = _extract_jwt_claims(request)
            return PlainTextResponse(str(len(claims)))

        app = Starlette(routes=[Route("/", endpoint)])
        client = _TC(app)
        response = client.get("/", headers={"Authorization": "Bearer bad.token"})
        assert response.text == "0"
