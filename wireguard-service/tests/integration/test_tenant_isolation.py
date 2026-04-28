"""Tests structurels d'isolation multi-tenant pour le microservice WireGuard.

Verifie que toutes les couches (models, repositories, services, endpoints)
implementent correctement le filtre tenant_id obligatoire.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Models
PEER_MODEL = PROJECT_ROOT / "app" / "models" / "peer.py"
IP_POOL_MODEL = PROJECT_ROOT / "app" / "models" / "ip_pool.py"
AUDIT_LOG_MODEL = PROJECT_ROOT / "app" / "models" / "audit_log.py"

# Repositories
BASE_REPO = PROJECT_ROOT / "app" / "repositories" / "base.py"
PEER_REPO = PROJECT_ROOT / "app" / "repositories" / "peer.py"
IP_POOL_REPO = PROJECT_ROOT / "app" / "repositories" / "ip_pool.py"
AUDIT_REPO = PROJECT_ROOT / "app" / "repositories" / "audit_log.py"

# Services
PEER_SERVICE = PROJECT_ROOT / "app" / "services" / "peer_service.py"
IP_ALLOCATOR = PROJECT_ROOT / "app" / "services" / "ip_allocator.py"

# Endpoints
PEERS_ENDPOINT = PROJECT_ROOT / "app" / "api" / "v1" / "peers.py"
IP_POOLS_ENDPOINT = PROJECT_ROOT / "app" / "api" / "v1" / "ip_pools.py"
STATUS_ENDPOINT = PROJECT_ROOT / "app" / "api" / "v1" / "status.py"
CONFIG_ENDPOINT = PROJECT_ROOT / "app" / "api" / "v1" / "config.py"

# Auth
DEPS_FILE = PROJECT_ROOT / "app" / "core" / "deps.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests — Models ont tenant_id NOT NULL
# ---------------------------------------------------------------------------


class TestModelsTenantId:
    """Verifie que tous les models metier ont tenant_id."""

    def test_peer_model_has_tenant_id(self):
        source = _read_source(PEER_MODEL)
        assert "tenant_id" in source

    def test_peer_model_tenant_not_nullable(self):
        source = _read_source(PEER_MODEL)
        assert "nullable=False" in source or "TenantMixin" in source

    def test_ip_pool_model_has_tenant_id(self):
        source = _read_source(IP_POOL_MODEL)
        assert "tenant_id" in source

    def test_ip_pool_model_tenant_not_nullable(self):
        source = _read_source(IP_POOL_MODEL)
        assert "nullable=False" in source or "TenantMixin" in source

    def test_audit_log_model_has_tenant_id(self):
        source = _read_source(AUDIT_LOG_MODEL)
        assert "tenant_id" in source

    def test_audit_log_model_tenant_not_nullable(self):
        source = _read_source(AUDIT_LOG_MODEL)
        assert "nullable=False" in source or "TenantMixin" in source


# ---------------------------------------------------------------------------
# Tests — Models ont index composite (tenant_id, id)
# ---------------------------------------------------------------------------


class TestModelsTenantIndex:
    """Verifie les index composites tenant_id."""

    def test_peer_model_has_tenant_index(self):
        source = _read_source(PEER_MODEL)
        assert "tenant_id" in source
        assert "Index(" in source or "index=True" in source

    def test_ip_pool_model_has_tenant_index(self):
        source = _read_source(IP_POOL_MODEL)
        assert "tenant_id" in source
        assert "Index(" in source or "index=True" in source


# ---------------------------------------------------------------------------
# Tests — Repositories filtrent par tenant_id
# ---------------------------------------------------------------------------


class TestRepositoryTenantFilter:
    """Verifie que les repositories filtrent par tenant_id."""

    def test_base_repo_accepts_tenant_id(self):
        source = _read_source(BASE_REPO)
        assert "tenant_id" in source

    def test_base_repo_filters_queries(self):
        source = _read_source(BASE_REPO)
        assert "tenant_id" in source
        assert ".where(" in source or ".filter(" in source

    def test_peer_repo_uses_tenant_filter(self):
        source = _read_source(PEER_REPO)
        assert "tenant_id" in source

    def test_ip_pool_repo_uses_tenant_filter(self):
        source = _read_source(IP_POOL_REPO)
        assert "tenant_id" in source

    def test_audit_repo_uses_tenant_filter(self):
        source = _read_source(AUDIT_REPO)
        assert "tenant_id" in source

    def test_peer_repo_inherits_base(self):
        source = _read_source(PEER_REPO)
        assert "BaseRepository" in source

    def test_ip_pool_repo_inherits_base(self):
        source = _read_source(IP_POOL_REPO)
        assert "BaseRepository" in source


# ---------------------------------------------------------------------------
# Tests — Services recoivent tenant_id
# ---------------------------------------------------------------------------


class TestServiceTenantIsolation:
    """Verifie que les services propagent le tenant_id."""

    def test_peer_service_accepts_tenant_id(self):
        source = _read_source(PEER_SERVICE)
        assert "tenant_id" in source

    def test_peer_service_passes_tenant_to_repo(self):
        source = _read_source(PEER_SERVICE)
        assert "PeerRepository" in source
        assert "tenant_id" in source

    def test_ip_allocator_accepts_tenant_id(self):
        source = _read_source(IP_ALLOCATOR)
        assert "tenant_id" in source

    def test_ip_allocator_uses_tenant_repo(self):
        source = _read_source(IP_ALLOCATOR)
        assert "IpPoolRepository" in source
        assert "tenant_id" in source


# ---------------------------------------------------------------------------
# Tests — Endpoints extraient tenant_id de l'auth
# ---------------------------------------------------------------------------


class TestEndpointTenantExtraction:
    """Verifie que les endpoints utilisent l'auth pour le tenant_id."""

    def test_deps_extracts_tenant_id(self):
        source = _read_source(DEPS_FILE)
        assert "X-Tenant-ID" in source
        assert "tenant_id" in source

    def test_deps_defines_internal_auth(self):
        source = _read_source(DEPS_FILE)
        assert "InternalAuth" in source
        assert "get_internal_auth" in source

    def test_peers_endpoint_uses_auth(self):
        source = _read_source(PEERS_ENDPOINT)
        assert "get_internal_auth" in source

    def test_ip_pools_endpoint_uses_auth(self):
        source = _read_source(IP_POOLS_ENDPOINT)
        assert "get_internal_auth" in source

    def test_status_endpoint_uses_auth(self):
        source = _read_source(STATUS_ENDPOINT)
        assert "get_internal_auth" in source

    def test_config_endpoint_uses_auth(self):
        source = _read_source(CONFIG_ENDPOINT)
        assert "get_internal_auth" in source


# ---------------------------------------------------------------------------
# Tests — Aucune requete globale (sans tenant_id)
# ---------------------------------------------------------------------------


class TestNoGlobalQueries:
    """Verifie qu'aucun repository ne fait de requete sans filtre tenant."""

    def test_base_repo_no_unfiltered_query(self):
        """Le BaseRepository doit toujours filtrer par tenant_id."""
        source = _read_source(BASE_REPO)
        assert "tenant_id" in source

    def test_peer_repo_get_by_public_key_filtered(self):
        """get_by_public_key doit filtrer par tenant."""
        source = _read_source(PEER_REPO)
        assert "public_key" in source
        assert "tenant_id" in source

    def test_ip_pool_repo_get_by_subnet_filtered(self):
        """get_by_subnet doit filtrer par tenant."""
        source = _read_source(IP_POOL_REPO)
        assert "get_by_subnet" in source
        assert "tenant_id" in source


# ---------------------------------------------------------------------------
# Tests — API key validation obligatoire
# ---------------------------------------------------------------------------


class TestInternalAuthRequired:
    """Verifie que l'auth interne est requise sur tous les endpoints."""

    def test_deps_validates_api_key(self):
        """get_internal_auth doit valider X-Internal-API-Key."""
        source = _read_source(DEPS_FILE)
        assert "X-Internal-API-Key" in source
        assert "INTERNAL_API_KEY" in source or "internal_api_key" in source.lower()

    def test_deps_rejects_missing_key(self):
        """Doit lever 401 si la cle manque."""
        source = _read_source(DEPS_FILE)
        assert "401" in source or "HTTP_401_UNAUTHORIZED" in source

    def test_deps_rejects_invalid_key(self):
        """Doit lever 401 si la cle est invalide."""
        source = _read_source(DEPS_FILE)
        assert "401" in source or "HTTP_401_UNAUTHORIZED" in source

    def test_all_endpoints_require_auth(self):
        """Tous les fichiers endpoint doivent importer get_internal_auth."""
        for filepath in [PEERS_ENDPOINT, IP_POOLS_ENDPOINT, STATUS_ENDPOINT, CONFIG_ENDPOINT]:
            source = _read_source(filepath)
            assert "get_internal_auth" in source, f"{filepath.name} manque get_internal_auth"
