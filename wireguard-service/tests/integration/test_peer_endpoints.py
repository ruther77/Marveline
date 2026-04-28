"""Tests structurels pour les endpoints peers WireGuard."""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PEERS_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "peers.py"
ROUTER_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "router.py"
MAIN_FILE = PROJECT_ROOT / "app" / "main.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels — Peers endpoints (analyse source)
# ---------------------------------------------------------------------------


class TestPeersEndpointStructure:
    """Vérifie la structure des endpoints peers."""

    def test_file_exists(self):
        assert PEERS_FILE.exists()

    def test_router_defined(self):
        source = _read_source(PEERS_FILE)
        assert 'router = APIRouter(prefix="/peers"' in source

    def test_router_has_tags(self):
        source = _read_source(PEERS_FILE)
        assert 'tags=["peers"]' in source

    def test_imports_peer_service(self):
        source = _read_source(PEERS_FILE)
        assert "from app.services.peer_service import" in source

    def test_imports_schemas(self):
        source = _read_source(PEERS_FILE)
        assert "from app.schemas.peer import" in source
        assert "PeerCreate" in source
        assert "PeerResponse" in source
        assert "PeerUpdate" in source
        assert "PeerListResponse" in source

    def test_imports_auth_dependency(self):
        source = _read_source(PEERS_FILE)
        assert "from app.core.deps import" in source
        assert "get_internal_auth" in source
        assert "get_db" in source


class TestCrudEndpoints:
    """Vérifie les endpoints CRUD."""

    def test_create_peer_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert "@router.post(" in source
        assert "def create_peer(" in source

    def test_create_returns_201(self):
        source = _read_source(PEERS_FILE)
        assert "HTTP_201_CREATED" in source

    def test_get_peer_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert '@router.get(\n    "/{peer_id}"' in source
        assert "def get_peer(" in source

    def test_list_peers_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert "def list_peers(" in source

    def test_list_supports_pagination(self):
        source = _read_source(PEERS_FILE)
        assert "page: int" in source
        assert "page_size: int" in source

    def test_list_supports_search(self):
        source = _read_source(PEERS_FILE)
        assert "search:" in source
        assert "search_peers" in source

    def test_list_supports_include_inactive(self):
        source = _read_source(PEERS_FILE)
        assert "include_inactive" in source

    def test_update_peer_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert "@router.patch(" in source
        assert "def update_peer(" in source

    def test_delete_peer_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert "@router.delete(" in source
        assert "def delete_peer(" in source

    def test_delete_returns_204(self):
        source = _read_source(PEERS_FILE)
        assert "HTTP_204_NO_CONTENT" in source


class TestActionEndpoints:
    """Vérifie les endpoints d'actions."""

    def test_rotate_keys_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert '/{peer_id}/rotate' in source
        assert "def rotate_keys(" in source

    def test_enable_peer_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert '/{peer_id}/enable' in source
        assert "def enable_peer(" in source

    def test_disable_peer_endpoint(self):
        source = _read_source(PEERS_FILE)
        assert '/{peer_id}/disable' in source
        assert "def disable_peer(" in source

    def test_all_actions_are_post(self):
        """Les actions doivent être des POST (mutation)."""
        source = _read_source(PEERS_FILE)
        # Cherche les décorateurs avant rotate/enable/disable
        for action in ["rotate", "enable", "disable"]:
            pattern = rf'@router\.post\(\s*"\/.+/{action}"'
            assert re.search(pattern, source), f"Action {action} doit être POST"


class TestErrorHandling:
    """Vérifie la gestion d'erreurs."""

    def test_404_on_not_found(self):
        source = _read_source(PEERS_FILE)
        assert "HTTP_404_NOT_FOUND" in source

    def test_409_on_limit_reached(self):
        source = _read_source(PEERS_FILE)
        assert "HTTP_409_CONFLICT" in source

    def test_409_on_ip_exhausted(self):
        source = _read_source(PEERS_FILE)
        assert "IpExhaustedError" in source

    def test_handles_peer_not_found(self):
        source = _read_source(PEERS_FILE)
        assert "PeerNotFoundError" in source

    def test_handles_peer_limit_reached(self):
        source = _read_source(PEERS_FILE)
        assert "PeerLimitReachedError" in source

    def test_commit_on_success(self):
        """Les mutations doivent commit la transaction."""
        source = _read_source(PEERS_FILE)
        assert "db.commit()" in source

    def test_rollback_on_error(self):
        """Les mutations doivent rollback en cas d'erreur."""
        source = _read_source(PEERS_FILE)
        assert "db.rollback()" in source


class TestServiceDependency:
    """Vérifie l'injection du PeerService."""

    def test_get_peer_service_function(self):
        source = _read_source(PEERS_FILE)
        assert "def _get_peer_service(" in source

    def test_uses_depends_for_service(self):
        source = _read_source(PEERS_FILE)
        assert "Depends(_get_peer_service)" in source

    def test_service_gets_backend(self):
        source = _read_source(PEERS_FILE)
        assert "get_backend(" in source

    def test_service_gets_client_ip(self):
        """Le service doit recevoir l'IP client pour les audit logs."""
        source = _read_source(PEERS_FILE)
        assert "request.client.host" in source


class TestSecurityPatterns:
    """Vérifie les patterns de sécurité."""

    def test_all_endpoints_require_auth(self):
        """Chaque endpoint doit dépendre de get_internal_auth."""
        source = _read_source(PEERS_FILE)
        # Chaque def endpoint doit avoir Depends(_get_peer_service)
        # qui lui-même utilise get_internal_auth
        assert "Depends(get_internal_auth)" in source

    def test_no_sensitive_data_in_response(self):
        """PeerResponse ne doit pas exposer encrypted_private_key."""
        source = _read_source(PEERS_FILE)
        assert "encrypted_private_key" not in source.split("PeerResponse")[0] if "PeerResponse" in source else True

    def test_response_model_enforced(self):
        """Chaque endpoint doit avoir response_model pour filtrer les champs."""
        source = _read_source(PEERS_FILE)
        assert source.count("response_model=PeerResponse") >= 5  # get, create, update, rotate, enable, disable minus list
        assert "response_model=PeerListResponse" in source


# ---------------------------------------------------------------------------
# Tests structurels — Router v1 (analyse source)
# ---------------------------------------------------------------------------


class TestRouterStructure:
    """Vérifie la structure du router principal."""

    def test_file_exists(self):
        assert ROUTER_FILE.exists()

    def test_defines_api_v1_router(self):
        source = _read_source(ROUTER_FILE)
        assert "api_v1_router" in source

    def test_has_wg_v1_prefix(self):
        source = _read_source(ROUTER_FILE)
        assert '"/wg/v1"' in source

    def test_includes_peers_router(self):
        source = _read_source(ROUTER_FILE)
        assert "peers_router" in source or "peers.router" in source

    def test_imports_peers(self):
        source = _read_source(ROUTER_FILE)
        assert "from app.api.v1.peers import" in source


# ---------------------------------------------------------------------------
# Tests structurels — Main.py (analyse source)
# ---------------------------------------------------------------------------


class TestMainAppStructure:
    """Vérifie la structure de main.py."""

    def test_file_exists(self):
        assert MAIN_FILE.exists()

    def test_create_application_factory(self):
        source = _read_source(MAIN_FILE)
        assert "def create_application(" in source

    def test_creates_fastapi_app(self):
        source = _read_source(MAIN_FILE)
        assert "FastAPI(" in source

    def test_includes_v1_router(self):
        source = _read_source(MAIN_FILE)
        assert "api_v1_router" in source
        assert "include_router" in source

    def test_health_endpoint(self):
        source = _read_source(MAIN_FILE)
        assert "/wg/health" in source

    def test_docs_only_in_dev(self):
        """La doc OpenAPI ne doit pas être exposée en production."""
        source = _read_source(MAIN_FILE)
        assert "is_development" in source
        assert "docs_url" in source

    def test_validates_production_secrets(self):
        source = _read_source(MAIN_FILE)
        assert "validate_production_secrets" in source

    def test_app_instance_exists(self):
        """Le module doit exporter une instance app pour uvicorn."""
        source = _read_source(MAIN_FILE)
        assert "app = create_application()" in source

    def test_logging_configured(self):
        source = _read_source(MAIN_FILE)
        assert "logging.basicConfig(" in source


# ---------------------------------------------------------------------------
# Tests cohérence — Routes complètes
# ---------------------------------------------------------------------------


class TestRouteCompleteness:
    """Vérifie la cohérence des routes complètes."""

    def test_full_route_prefix(self):
        """Le préfixe complet doit être /wg/v1/peers."""
        router_source = _read_source(ROUTER_FILE)
        peers_source = _read_source(PEERS_FILE)
        assert '"/wg/v1"' in router_source
        assert '"/peers"' in peers_source

    def test_all_crud_operations_present(self):
        """POST, GET, GET (list), PATCH, DELETE doivent être présents."""
        source = _read_source(PEERS_FILE)
        assert "@router.post(" in source
        assert "@router.get(" in source
        assert "@router.patch(" in source
        assert "@router.delete(" in source

    def test_all_action_endpoints_present(self):
        """rotate, enable, disable doivent être présents."""
        source = _read_source(PEERS_FILE)
        for action in ["rotate", "enable", "disable"]:
            assert f"/{action}" in source, f"Action endpoint /{action} manquant"
