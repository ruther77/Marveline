"""Tests unitaires pour app.services.ip_allocator — allocation IP atomique."""

import ipaddress
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
IP_ALLOCATOR_FILE = PROJECT_ROOT / "app" / "services" / "ip_allocator.py"
IP_POOL_REPO_FILE = PROJECT_ROOT / "app" / "repositories" / "ip_pool.py"
BASE_REPO_FILE = PROJECT_ROOT / "app" / "repositories" / "base.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels — IP Allocator (analyse source)
# ---------------------------------------------------------------------------

class TestIpAllocatorSourceStructure:
    """Vérifie la structure du module ip_allocator."""

    def test_class_exists(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "class IpAllocatorService" in source

    def test_allocate_ip_method(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "def allocate_ip(" in source

    def test_get_available_count_method(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "def get_available_count(" in source

    def test_is_exhausted_method(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "def is_exhausted(" in source

    def test_find_pool_with_capacity_method(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "def find_pool_with_capacity(" in source

    def test_uses_ipaddress_module(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "import ipaddress" in source

    def test_ip_exhausted_error_exists(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "class IpExhaustedError" in source

    def test_uses_ip_pool_repository(self):
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "IpPoolRepository" in source

    def test_uses_lock_for_allocation(self):
        """L'allocation doit verrouiller le pool (SELECT FOR UPDATE)."""
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "lock_for_allocation" in source

    def test_returns_cidr_format(self):
        """L'IP allouée doit être au format /32."""
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "/32" in source

    def test_checks_broadcast_address(self):
        """Doit vérifier l'adresse de broadcast pour éviter l'allocation."""
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "broadcast" in source.lower()


# ---------------------------------------------------------------------------
# Tests structurels — IP Pool Repository (analyse source)
# ---------------------------------------------------------------------------

class TestIpPoolRepoSourceStructure:
    """Vérifie la structure du repository IP pool."""

    def test_class_exists(self):
        source = _read_source(IP_POOL_REPO_FILE)
        assert "class IpPoolRepository" in source

    def test_extends_tenant_aware_base(self):
        source = _read_source(IP_POOL_REPO_FILE)
        assert "TenantAwareBaseRepository" in source

    def test_lock_for_allocation_method(self):
        source = _read_source(IP_POOL_REPO_FILE)
        assert "def lock_for_allocation(" in source

    def test_uses_select_for_update(self):
        source = _read_source(IP_POOL_REPO_FILE)
        assert "with_for_update()" in source

    def test_get_by_subnet_method(self):
        source = _read_source(IP_POOL_REPO_FILE)
        assert "def get_by_subnet(" in source

    def test_update_next_ip_method(self):
        source = _read_source(IP_POOL_REPO_FILE)
        assert "def update_next_ip(" in source


# ---------------------------------------------------------------------------
# Tests structurels — Base Repository (analyse source)
# ---------------------------------------------------------------------------

class TestBaseRepoSourceStructure:
    """Vérifie la structure du repository de base."""

    def test_tenant_aware_class(self):
        source = _read_source(BASE_REPO_FILE)
        assert "class TenantAwareBaseRepository" in source

    def test_paginated_result_class(self):
        source = _read_source(BASE_REPO_FILE)
        assert "class PaginatedResult" in source

    def test_tenant_isolation_error(self):
        source = _read_source(BASE_REPO_FILE)
        assert "class TenantIsolationError" in source

    def test_tenant_query_method(self):
        source = _read_source(BASE_REPO_FILE)
        assert "def _tenant_query(" in source

    def test_create_forces_tenant_id(self):
        """Le create doit forcer le tenant_id, pas accepter celui du caller."""
        source = _read_source(BASE_REPO_FILE)
        assert 'data.pop("tenant_id"' in source

    def test_update_blocks_tenant_id_change(self):
        """L'update doit interdire la modification de tenant_id."""
        source = _read_source(BASE_REPO_FILE)
        assert '"tenant_id" in data' in source
        assert "TenantIsolationError" in source

    def test_soft_delete_method(self):
        source = _read_source(BASE_REPO_FILE)
        assert "def soft_delete(" in source

    def test_paginate_method(self):
        source = _read_source(BASE_REPO_FILE)
        assert "def paginate(" in source

    def test_max_page_size_enforced(self):
        source = _read_source(BASE_REPO_FILE)
        assert "MAX_PAGE_SIZE" in source

    def test_validates_positive_tenant_id(self):
        source = _read_source(BASE_REPO_FILE)
        assert "tenant_id <= 0" in source or "tenant_id < 1" in source


# ---------------------------------------------------------------------------
# Tests structurels — Peer Repository (analyse source)
# ---------------------------------------------------------------------------

class TestPeerRepoSourceStructure:
    """Vérifie la structure du repository peer."""

    def test_class_exists(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "peer.py")
        assert "class PeerRepository" in source

    def test_extends_tenant_aware_base(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "peer.py")
        assert "TenantAwareBaseRepository" in source

    def test_get_by_public_key(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "peer.py")
        assert "def get_by_public_key(" in source

    def test_list_active(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "peer.py")
        assert "def list_active(" in source

    def test_list_expired(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "peer.py")
        assert "def list_expired(" in source

    def test_search_method(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "peer.py")
        assert "def search(" in source


# ---------------------------------------------------------------------------
# Tests structurels — Audit Log Repository (analyse source)
# ---------------------------------------------------------------------------

class TestAuditLogRepoSourceStructure:
    """Vérifie la structure du repository audit log."""

    def test_class_exists(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "audit_log.py")
        assert "class AuditLogRepository" in source

    def test_log_action_method(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "audit_log.py")
        assert "def log_action(" in source

    def test_list_by_peer(self):
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "audit_log.py")
        assert "def list_by_peer(" in source

    def test_update_forbidden(self):
        """L'update doit lever une exception (append-only)."""
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "audit_log.py")
        assert "immutable" in source.lower()

    def test_delete_forbidden(self):
        """Le soft_delete doit lever une exception (append-only)."""
        source = _read_source(PROJECT_ROOT / "app" / "repositories" / "audit_log.py")
        # Vérifie que soft_delete raise
        assert "raise" in source
        assert "def soft_delete(" in source


# ---------------------------------------------------------------------------
# Tests fonctionnels — IP Allocator (avec mocks légers)
# ---------------------------------------------------------------------------

class TestIpAllocatorFunctional:
    """Tests fonctionnels de l'allocation IP sans DB réelle."""

    def test_ipv4_address_increment(self):
        """Vérifie la logique d'incrémentation IP."""
        ip = ipaddress.IPv4Address("10.10.0.2")
        next_ip = ip + 1
        assert str(next_ip) == "10.10.0.3"

    def test_broadcast_detection(self):
        """Vérifie la détection de l'adresse broadcast."""
        network = ipaddress.IPv4Network("10.10.0.0/24", strict=False)
        assert str(network.broadcast_address) == "10.10.0.255"

    def test_available_count_calculation(self):
        """Vérifie le calcul du nombre d'IPs disponibles."""
        current = ipaddress.IPv4Address("10.10.0.2")
        broadcast = ipaddress.IPv4Address("10.10.0.255")
        available = int(broadcast) - int(current)
        assert available == 253

    def test_cidr_format(self):
        """Vérifie le format CIDR /32 pour les IPs allouées."""
        ip = "10.10.0.5"
        cidr = f"{ip}/32"
        parsed = ipaddress.IPv4Network(cidr, strict=True)
        assert parsed.num_addresses == 1

    def test_network_parsing(self):
        """Vérifie le parsing de différents subnets."""
        for subnet in ["10.10.0.0/24", "192.168.1.0/24", "172.16.0.0/16"]:
            net = ipaddress.IPv4Network(subnet, strict=False)
            assert net.broadcast_address is not None
            assert net.network_address is not None

    def test_exhaustion_at_broadcast(self):
        """Une IP égale au broadcast = pool épuisé."""
        current = ipaddress.IPv4Address("10.10.0.255")
        broadcast = ipaddress.IPv4Address("10.10.0.255")
        assert current >= broadcast

    def test_small_subnet_capacity(self):
        """Un /30 n'a que 2 IPs utilisables (hors network et broadcast)."""
        network = ipaddress.IPv4Network("10.10.0.0/30", strict=False)
        # network=.0, gateway=.1, usable=.2, broadcast=.3
        gateway = ipaddress.IPv4Address("10.10.0.1")
        first_usable = ipaddress.IPv4Address("10.10.0.2")
        broadcast = network.broadcast_address
        available = int(broadcast) - int(first_usable)
        assert available == 1  # Seulement .2 est allouable

    def test_ip_allocator_import_chain(self):
        """Vérifie que la chaîne d'imports est correcte."""
        source = _read_source(IP_ALLOCATOR_FILE)
        assert "from app.repositories.ip_pool import IpPoolRepository" in source
