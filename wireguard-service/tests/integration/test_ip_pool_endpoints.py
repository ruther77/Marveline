"""Tests structurels pour les endpoints IP pools et status WireGuard."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
IP_POOLS_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "ip_pools.py"
STATUS_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "status.py"
ROUTER_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "router.py"
SCHEMA_STATUS_FILE = PROJECT_ROOT / "app" / "schemas" / "status.py"
SCHEMA_IP_POOL_FILE = PROJECT_ROOT / "app" / "schemas" / "ip_pool.py"
SCHEMAS_INIT_FILE = PROJECT_ROOT / "app" / "schemas" / "__init__.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels — Status endpoint
# ---------------------------------------------------------------------------


class TestStatusEndpointStructure:
    """Verifie la structure de l'endpoint status."""

    def test_file_exists(self):
        assert STATUS_FILE.exists()

    def test_router_defined(self):
        source = _read_source(STATUS_FILE)
        assert "router = APIRouter(" in source

    def test_router_has_status_tag(self):
        source = _read_source(STATUS_FILE)
        assert 'tags=["status"]' in source

    def test_get_status_endpoint(self):
        source = _read_source(STATUS_FILE)
        assert '"/status"' in source
        assert "def get_server_status(" in source

    def test_returns_server_status_response(self):
        source = _read_source(STATUS_FILE)
        assert "response_model=ServerStatusResponse" in source

    def test_imports_backend(self):
        source = _read_source(STATUS_FILE)
        assert "from app.services.wireguard_backend import" in source
        assert "get_backend" in source

    def test_imports_settings(self):
        source = _read_source(STATUS_FILE)
        assert "from app.core.config import get_settings" in source

    def test_imports_auth(self):
        source = _read_source(STATUS_FILE)
        assert "from app.core.deps import" in source
        assert "get_internal_auth" in source

    def test_checks_backend_availability(self):
        source = _read_source(STATUS_FILE)
        assert "is_available" in source

    def test_lists_peers(self):
        source = _read_source(STATUS_FILE)
        assert "list_peers" in source

    def test_returns_peer_stats(self):
        source = _read_source(STATUS_FILE)
        assert "PeerStatusResponse" in source


class TestStatusSchemaStructure:
    """Verifie la structure des schemas status."""

    def test_file_exists(self):
        assert SCHEMA_STATUS_FILE.exists()

    def test_server_status_response(self):
        source = _read_source(SCHEMA_STATUS_FILE)
        assert "class ServerStatusResponse(BaseModel):" in source

    def test_server_status_fields(self):
        source = _read_source(SCHEMA_STATUS_FILE)
        assert "backend_available" in source
        assert "interface" in source
        assert "active_peers_count" in source
        assert "peers" in source

    def test_peer_status_response(self):
        source = _read_source(SCHEMA_STATUS_FILE)
        assert "class PeerStatusResponse(BaseModel):" in source

    def test_peer_status_fields(self):
        source = _read_source(SCHEMA_STATUS_FILE)
        assert "public_key" in source
        assert "latest_handshake" in source
        assert "transfer_rx" in source
        assert "transfer_tx" in source
        assert "endpoint" in source


# ---------------------------------------------------------------------------
# Tests structurels — IP Pools endpoints
# ---------------------------------------------------------------------------


class TestIpPoolsEndpointStructure:
    """Verifie la structure des endpoints IP pools."""

    def test_file_exists(self):
        assert IP_POOLS_FILE.exists()

    def test_router_defined(self):
        source = _read_source(IP_POOLS_FILE)
        assert 'router = APIRouter(prefix="/ip-pools"' in source

    def test_router_has_tag(self):
        source = _read_source(IP_POOLS_FILE)
        assert 'tags=["ip-pools"]' in source

    def test_list_ip_pools_endpoint(self):
        source = _read_source(IP_POOLS_FILE)
        assert "def list_ip_pools(" in source

    def test_list_returns_ip_pool_list_response(self):
        source = _read_source(IP_POOLS_FILE)
        assert "response_model=IpPoolListResponse" in source

    def test_create_ip_pool_endpoint(self):
        source = _read_source(IP_POOLS_FILE)
        assert "def create_ip_pool(" in source

    def test_create_returns_201(self):
        source = _read_source(IP_POOLS_FILE)
        assert "HTTP_201_CREATED" in source

    def test_create_returns_ip_pool_response(self):
        source = _read_source(IP_POOLS_FILE)
        assert "response_model=IpPoolResponse" in source

    def test_imports_ip_pool_repository(self):
        source = _read_source(IP_POOLS_FILE)
        assert "from app.repositories.ip_pool import IpPoolRepository" in source

    def test_imports_schemas(self):
        source = _read_source(IP_POOLS_FILE)
        assert "from app.schemas.ip_pool import" in source
        assert "IpPoolCreate" in source
        assert "IpPoolResponse" in source
        assert "IpPoolListResponse" in source

    def test_imports_auth(self):
        source = _read_source(IP_POOLS_FILE)
        assert "from app.core.deps import" in source
        assert "get_internal_auth" in source
        assert "get_db" in source


class TestIpPoolValidation:
    """Verifie la validation dans les endpoints IP pools."""

    def test_validates_subnet(self):
        source = _read_source(IP_POOLS_FILE)
        assert "IPv4Network" in source

    def test_validates_gateway(self):
        source = _read_source(IP_POOLS_FILE)
        assert "IPv4Address" in source

    def test_gateway_in_subnet_check(self):
        source = _read_source(IP_POOLS_FILE)
        assert "gateway" in source.lower()
        assert "network" in source.lower()

    def test_duplicate_check(self):
        source = _read_source(IP_POOLS_FILE)
        assert "get_by_subnet" in source
        assert "HTTP_409_CONFLICT" in source

    def test_computes_first_client_ip(self):
        source = _read_source(IP_POOLS_FILE)
        assert "first_client_ip" in source or "next_ip" in source

    def test_400_on_invalid_input(self):
        source = _read_source(IP_POOLS_FILE)
        assert "HTTP_400_BAD_REQUEST" in source

    def test_commit_on_success(self):
        source = _read_source(IP_POOLS_FILE)
        assert "db.commit()" in source

    def test_rollback_on_error(self):
        source = _read_source(IP_POOLS_FILE)
        assert "db.rollback()" in source


class TestIpPoolSchemaStructure:
    """Verifie la structure des schemas IP pool."""

    def test_file_exists(self):
        assert SCHEMA_IP_POOL_FILE.exists()

    def test_ip_pool_create(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "class IpPoolCreate(BaseModel):" in source

    def test_ip_pool_create_fields(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "subnet" in source
        assert "gateway_ip" in source

    def test_subnet_validation(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "pattern" in source

    def test_ip_pool_response(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "class IpPoolResponse(BaseModel):" in source

    def test_ip_pool_response_fields(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "id" in source
        assert "tenant_id" in source
        assert "subnet" in source
        assert "gateway_ip" in source
        assert "next_ip" in source
        assert "subnet_mask" in source

    def test_ip_pool_response_from_attributes(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "from_attributes=True" in source

    def test_ip_pool_list_response(self):
        source = _read_source(SCHEMA_IP_POOL_FILE)
        assert "class IpPoolListResponse(BaseModel):" in source
        assert "items" in source
        assert "total" in source


# ---------------------------------------------------------------------------
# Tests structurels — Router integration
# ---------------------------------------------------------------------------


class TestRouterIntegration:
    """Verifie que tous les routers sont integres."""

    def test_router_includes_status(self):
        source = _read_source(ROUTER_FILE)
        assert "status_router" in source

    def test_router_imports_status(self):
        source = _read_source(ROUTER_FILE)
        assert "from app.api.v1.status import" in source

    def test_router_includes_ip_pools(self):
        source = _read_source(ROUTER_FILE)
        assert "ip_pools_router" in source

    def test_router_imports_ip_pools(self):
        source = _read_source(ROUTER_FILE)
        assert "from app.api.v1.ip_pools import" in source

    def test_router_includes_config(self):
        source = _read_source(ROUTER_FILE)
        assert "config_router" in source

    def test_router_includes_peers(self):
        source = _read_source(ROUTER_FILE)
        assert "peers_router" in source

    def test_all_four_routers_included(self):
        source = _read_source(ROUTER_FILE)
        assert source.count("include_router") == 4


class TestSchemasInit:
    """Verifie que schemas/__init__.py exporte tout."""

    def test_exports_config_schema(self):
        source = _read_source(SCHEMAS_INIT_FILE)
        assert "ClientConfigResponse" in source

    def test_exports_ip_pool_schemas(self):
        source = _read_source(SCHEMAS_INIT_FILE)
        assert "IpPoolCreate" in source
        assert "IpPoolResponse" in source
        assert "IpPoolListResponse" in source

    def test_exports_status_schemas(self):
        source = _read_source(SCHEMAS_INIT_FILE)
        assert "ServerStatusResponse" in source
        assert "PeerStatusResponse" in source

    def test_exports_peer_schemas(self):
        source = _read_source(SCHEMAS_INIT_FILE)
        assert "PeerCreate" in source
        assert "PeerResponse" in source
        assert "PeerUpdate" in source
        assert "PeerListResponse" in source


# ---------------------------------------------------------------------------
# Tests structurels — Routes completes
# ---------------------------------------------------------------------------


class TestRouteCompleteness:
    """Verifie la coherence des routes completes."""

    def test_status_route_prefix(self):
        """Le statut doit etre accessible via /wg/v1/status."""
        router_source = _read_source(ROUTER_FILE)
        status_source = _read_source(STATUS_FILE)
        assert '"/wg/v1"' in router_source
        assert '"/status"' in status_source

    def test_ip_pools_route_prefix(self):
        """Les IP pools doivent etre accessibles via /wg/v1/ip-pools."""
        router_source = _read_source(ROUTER_FILE)
        ip_pools_source = _read_source(IP_POOLS_FILE)
        assert '"/wg/v1"' in router_source
        assert '"/ip-pools"' in ip_pools_source

    def test_all_endpoints_require_auth(self):
        """Tous les endpoints doivent requérir get_internal_auth."""
        for filepath in [STATUS_FILE, IP_POOLS_FILE]:
            source = _read_source(filepath)
            assert "get_internal_auth" in source, f"{filepath.name} missing auth"
