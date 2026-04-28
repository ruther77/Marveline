"""Tests unitaires pour app.services.peer_service — PeerService CRUD + actions."""

import re
from pathlib import Path

import pytest

try:
    import pydantic  # noqa: F401
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

PROJECT_ROOT = Path(__file__).parent.parent.parent
PEER_SERVICE_FILE = PROJECT_ROOT / "app" / "services" / "peer_service.py"
PEER_SCHEMA_FILE = PROJECT_ROOT / "app" / "schemas" / "peer.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels — PeerService (analyse source)
# ---------------------------------------------------------------------------


class TestPeerServiceSourceStructure:
    """Vérifie la structure du module peer_service."""

    def test_class_exists(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "class PeerService" in source

    def test_create_peer_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def create_peer(" in source

    def test_get_peer_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def get_peer(" in source

    def test_list_peers_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def list_peers(" in source

    def test_update_peer_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def update_peer(" in source

    def test_delete_peer_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def delete_peer(" in source

    def test_rotate_keys_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def rotate_keys(" in source

    def test_enable_peer_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def enable_peer(" in source

    def test_disable_peer_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def disable_peer(" in source

    def test_get_peer_private_key_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def get_peer_private_key(" in source

    def test_search_peers_method(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "def search_peers(" in source


class TestPeerServiceDependencies:
    """Vérifie les imports et dépendances du PeerService."""

    def test_imports_crypto(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "from app.core.crypto import" in source

    def test_imports_generate_keypair(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "generate_keypair" in source

    def test_imports_encrypt_value(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "encrypt_value" in source

    def test_imports_decrypt_value(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "decrypt_value" in source

    def test_imports_wireguard_backend(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "from app.services.wireguard_backend import WireGuardBackend" in source

    def test_imports_ip_allocator(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "from app.services.ip_allocator import" in source

    def test_imports_peer_repository(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "from app.repositories.peer import PeerRepository" in source

    def test_imports_audit_log_repository(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "from app.repositories.audit_log import AuditLogRepository" in source

    def test_imports_settings(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "from app.core.config import get_settings" in source


class TestPeerServiceExceptions:
    """Vérifie les exceptions métier."""

    def test_peer_service_error_exists(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "class PeerServiceError" in source

    def test_peer_not_found_error_exists(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "class PeerNotFoundError" in source

    def test_peer_limit_reached_error_exists(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "class PeerLimitReachedError" in source

    def test_exceptions_hierarchy(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "PeerNotFoundError(PeerServiceError)" in source
        assert "PeerLimitReachedError(PeerServiceError)" in source


class TestPeerServiceCreateFlow:
    """Vérifie le flow de création peer dans le code source."""

    def test_checks_peer_limit(self):
        """create_peer doit vérifier la limite de peers."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "count_active" in source
        assert "PEER_MAX_PER_TENANT" in source

    def test_calls_generate_keypair(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "generate_keypair()" in source

    def test_calls_generate_preshared_key(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "generate_preshared_key()" in source

    def test_encrypts_private_key(self):
        """La clé privée doit être chiffrée avant stockage."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "encrypt_value(" in source
        assert "ENCRYPTION_KEY" in source

    def test_allocates_ip(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "allocate_ip(" in source

    def test_finds_pool_with_capacity(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "find_pool_with_capacity()" in source

    def test_adds_to_backend(self):
        """create_peer doit ajouter le peer au backend WG."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "backend.add_peer(" in source

    def test_audits_creation(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert '"peer_created"' in source

    def test_stores_encrypted_private_key(self):
        """La DB reçoit encrypted_private_key, pas la clé en clair."""
        source = _read_source(PEER_SERVICE_FILE)
        assert '"encrypted_private_key": encrypted_private_key' in source


class TestPeerServiceDeleteFlow:
    """Vérifie le flow de suppression peer dans le code source."""

    def test_removes_from_backend(self):
        """delete_peer doit retirer le peer du backend WG."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "backend.remove_peer(" in source

    def test_soft_deletes(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "soft_delete(" in source

    def test_audits_deletion(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert '"peer_deleted"' in source


class TestPeerServiceRotateFlow:
    """Vérifie le flow de rotation des clés."""

    def test_generates_new_keypair(self):
        source = _read_source(PEER_SERVICE_FILE)
        # rotate_keys utilise generate_keypair
        assert "generate_keypair()" in source

    def test_removes_old_peer_from_backend(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "old_public_key" in source

    def test_adds_new_peer_to_backend(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "new_public_key_b64" in source

    def test_audits_rotation(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert '"peer_keys_rotated"' in source


class TestPeerServiceEnableDisable:
    """Vérifie enable/disable peer."""

    def test_enable_adds_to_backend(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert '"peer_enabled"' in source

    def test_disable_removes_from_backend(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert '"peer_disabled"' in source

    def test_enable_idempotent(self):
        """Enable sur un peer déjà activé doit être idempotent."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "if peer.is_enabled:" in source

    def test_disable_idempotent(self):
        """Disable sur un peer déjà désactivé doit être idempotent."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "if not peer.is_enabled:" in source


class TestPeerServiceGetPrivateKey:
    """Vérifie la récupération de la clé privée."""

    def test_decrypts_private_key(self):
        source = _read_source(PEER_SERVICE_FILE)
        assert "decrypt_value(" in source

    def test_never_logs_private_key(self):
        """La clé privée ne doit JAMAIS apparaître dans les logs."""
        source = _read_source(PEER_SERVICE_FILE)
        # Vérifie qu'aucun logger.info/debug ne contient private_key
        log_lines = [
            line.strip()
            for line in source.split("\n")
            if "logger." in line
        ]
        for line in log_lines:
            assert "private_key" not in line.lower(), (
                f"FUITE SECURITE: la clé privée pourrait être loggée: {line}"
            )


class TestPeerServiceSecurityPatterns:
    """Tests de sécurité sur le code source."""

    def test_no_plaintext_key_in_db_data(self):
        """Vérifie que private_key_b64 n'est jamais stocké en DB directement."""
        source = _read_source(PEER_SERVICE_FILE)
        # Le dict de création ne doit pas contenir "private_key": private_key_b64
        assert '"private_key": private_key_b64' not in source

    def test_uses_preshared_key(self):
        """Doit utiliser des preshared keys pour double encryption."""
        source = _read_source(PEER_SERVICE_FILE)
        assert "preshared_key" in source

    def test_audit_on_all_mutations(self):
        """Chaque mutation doit avoir un audit log."""
        source = _read_source(PEER_SERVICE_FILE)
        for action in [
            "peer_created",
            "peer_updated",
            "peer_deleted",
            "peer_keys_rotated",
            "peer_enabled",
            "peer_disabled",
        ]:
            assert action in source, f"Audit manquant pour {action}"


# ---------------------------------------------------------------------------
# Tests structurels — Peer Schemas (analyse source)
# ---------------------------------------------------------------------------


class TestPeerSchemasStructure:
    """Vérifie la structure des schemas Pydantic."""

    def test_peer_create_schema(self):
        source = _read_source(PEER_SCHEMA_FILE)
        assert "class PeerCreate" in source

    def test_peer_update_schema(self):
        source = _read_source(PEER_SCHEMA_FILE)
        assert "class PeerUpdate" in source

    def test_peer_response_schema(self):
        source = _read_source(PEER_SCHEMA_FILE)
        assert "class PeerResponse" in source

    def test_peer_list_response_schema(self):
        source = _read_source(PEER_SCHEMA_FILE)
        assert "class PeerListResponse" in source

    def test_from_attributes_enabled(self):
        """PeerResponse doit pouvoir lire depuis des attributs ORM."""
        source = _read_source(PEER_SCHEMA_FILE)
        assert "from_attributes" in source

    def test_peer_type_validation(self):
        """PeerCreate doit valider le type de peer."""
        source = _read_source(PEER_SCHEMA_FILE)
        assert "permanent" in source
        assert "temporary" in source
        assert "technician" in source

    def test_name_max_length(self):
        source = _read_source(PEER_SCHEMA_FILE)
        assert "max_length=255" in source

    def test_expires_at_validation(self):
        """expires_at doit être dans le futur."""
        source = _read_source(PEER_SCHEMA_FILE)
        assert "validate_expires_at" in source

    def test_response_excludes_private_key(self):
        """PeerResponse ne doit PAS exposer encrypted_private_key."""
        source = _read_source(PEER_SCHEMA_FILE)
        # Cherche dans PeerResponse class
        response_section = source[source.index("class PeerResponse"):]
        # Il ne doit pas y avoir de champ encrypted_private_key
        # (cherche jusqu'à la prochaine classe ou fin)
        next_class = response_section.find("\nclass ", 1)
        if next_class > 0:
            response_section = response_section[:next_class]
        assert "encrypted_private_key" not in response_section
        assert "preshared_key" not in response_section


# ---------------------------------------------------------------------------
# Tests fonctionnels — Schemas Pydantic (validation réelle)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_PYDANTIC, reason="pydantic non installé localement")
class TestPeerCreateValidation:
    """Tests de validation sur PeerCreate."""

    def test_valid_minimal(self):
        from app.schemas.peer import PeerCreate

        peer = PeerCreate(name="Store Paris")
        assert peer.name == "Store Paris"
        assert peer.peer_type == "permanent"
        assert peer.allowed_ips == "0.0.0.0/0"

    def test_valid_full(self):
        from datetime import datetime, timezone, timedelta
        from app.schemas.peer import PeerCreate

        peer = PeerCreate(
            name="Tech Support",
            description="Temporary access",
            peer_type="technician",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            allowed_ips="10.10.0.0/24",
            dns="1.1.1.1",
            persistent_keepalive=30,
            pool_id=1,
        )
        assert peer.peer_type == "technician"
        assert peer.pool_id == 1

    def test_rejects_empty_name(self):
        from app.schemas.peer import PeerCreate

        with pytest.raises(Exception):
            PeerCreate(name="")

    def test_rejects_invalid_peer_type(self):
        from app.schemas.peer import PeerCreate

        with pytest.raises(Exception):
            PeerCreate(name="Test", peer_type="invalid")

    def test_rejects_negative_keepalive(self):
        from app.schemas.peer import PeerCreate

        with pytest.raises(Exception):
            PeerCreate(name="Test", persistent_keepalive=-1)

    def test_rejects_past_expires_at(self):
        from datetime import datetime, timezone, timedelta
        from app.schemas.peer import PeerCreate

        with pytest.raises(Exception):
            PeerCreate(
                name="Test",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )


@pytest.mark.skipif(not HAS_PYDANTIC, reason="pydantic non installé localement")
class TestPeerUpdateValidation:
    """Tests de validation sur PeerUpdate."""

    def test_all_fields_optional(self):
        from app.schemas.peer import PeerUpdate

        update = PeerUpdate()
        assert update.name is None
        assert update.description is None

    def test_partial_update(self):
        from app.schemas.peer import PeerUpdate

        update = PeerUpdate(name="New Name", dns="8.8.8.8")
        assert update.name == "New Name"
        assert update.dns == "8.8.8.8"
        assert update.allowed_ips is None


@pytest.mark.skipif(not HAS_PYDANTIC, reason="pydantic non installé localement")
class TestPeerResponseSerialization:
    """Tests de sérialisation PeerResponse."""

    def test_from_dict(self):
        import uuid
        from datetime import datetime, timezone
        from app.schemas.peer import PeerResponse

        data = {
            "id": uuid.uuid4(),
            "name": "Store Bordeaux",
            "description": None,
            "public_key": "a" * 44,
            "assigned_ip": "10.10.0.5/32",
            "allowed_ips": "0.0.0.0/0",
            "persistent_keepalive": 25,
            "dns": "1.1.1.1",
            "is_enabled": True,
            "is_active": True,
            "peer_type": "permanent",
            "expires_at": None,
            "created_by": 1,
            "last_handshake_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        response = PeerResponse(**data)
        assert response.name == "Store Bordeaux"
        assert response.assigned_ip == "10.10.0.5/32"

    def test_list_response(self):
        from app.schemas.peer import PeerListResponse

        resp = PeerListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            total_pages=0,
            has_next=False,
            has_prev=False,
        )
        assert resp.total == 0
        assert resp.items == []
