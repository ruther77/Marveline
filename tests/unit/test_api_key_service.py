"""Tests unitaires pour ApiKeyService."""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from app.models.api_key import ApiKey
from app.models.user import User
from app.services.api_key import ApiKeyService, KEY_PREFIX_MARKER
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate
from app.core.security import get_password_hash


@pytest.fixture
def admin_user(test_db):
    """Admin user for API key creation."""
    user = User(
        tenant_id=1,
        email="apikey-admin@carocorp.com",
        hashed_password=get_password_hash("admin123"),
        first_name="API Key",
        last_name="Admin",
        role="admin",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def admin_user_t2(test_db):
    """Admin user for tenant 2 (cross-tenant tests)."""
    user = User(
        tenant_id=2,
        email="admin@tenant2.com",
        hashed_password=get_password_hash("admin123"),
        first_name="Admin",
        last_name="T2",
        role="admin",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def service(test_db):
    """ApiKeyService instance."""
    return ApiKeyService(test_db)


@pytest.fixture
def create_data():
    """Valid API key creation payload."""
    return ApiKeyCreate(
        name="Caisse magasin 1",
        scopes=["products:read", "inventory:read"],
        rate_limit=500,
    )


class TestApiKeyGeneration:
    """Tests pour generation et hashing de cles."""

    def test_generate_key_format(self, service):
        """La cle generee a le bon format mk_live_xxx."""
        full_key, prefix, key_hash = service._generate_key()

        assert full_key.startswith(KEY_PREFIX_MARKER)
        assert len(prefix) == 12
        assert prefix == full_key[:12]
        assert len(key_hash) == 64  # SHA-256 hex

    def test_generate_key_unique(self, service):
        """Deux generations produisent des cles differentes."""
        k1 = service._generate_key()
        k2 = service._generate_key()

        assert k1[0] != k2[0]  # full_key
        assert k1[2] != k2[2]  # key_hash

    def test_hash_key_deterministic(self):
        """hash_key() est deterministe."""
        key = "mk_live_test123"
        h1 = ApiKeyService.hash_key(key)
        h2 = ApiKeyService.hash_key(key)

        assert h1 == h2
        assert h1 == hashlib.sha256(key.encode()).hexdigest()


class TestCreateKey:
    """Tests pour creation de cles."""

    @patch("app.services.api_key.redis_client")
    def test_create_key_success(self, mock_redis, service, test_db, admin_user, create_data):
        """create_key() cree une cle valide."""
        api_key, full_key = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()
        test_db.refresh(api_key)

        assert api_key.id is not None
        assert api_key.name == "Caisse magasin 1"
        assert api_key.tenant_id == 1
        assert api_key.created_by == admin_user.id
        assert "inventory:read" in api_key.scopes
        assert "products:read" in api_key.scopes
        assert api_key.rate_limit == 500
        assert api_key.is_active is True
        assert api_key.usage_count == 0

        # full_key commence par mk_live_
        assert full_key.startswith(KEY_PREFIX_MARKER)

        # key_hash correspond au hash du full_key
        assert api_key.key_hash == hashlib.sha256(full_key.encode()).hexdigest()

    def test_create_key_invalid_scopes(self, admin_user):
        """ApiKeyCreate rejette des scopes invalides au niveau Pydantic."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ApiKeyCreate(
                name="Bad key",
                scopes=["products:read", "invalid:scope"],
            )
        assert "invalid:scope" in str(exc_info.value)


class TestValidateKey:
    """Tests pour validation de cles."""

    @patch("app.services.api_key.redis_client")
    def test_validate_key_success(self, mock_redis, service, test_db, admin_user, create_data):
        """validate_key() retourne la cle si valide."""
        mock_redis.client.get.return_value = None  # Cache miss

        api_key, full_key = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        result = service.validate_key(full_key)

        assert result is not None
        assert result.id == api_key.id
        assert result.name == api_key.name

    @patch("app.services.api_key.redis_client")
    def test_validate_key_invalid(self, mock_redis, service):
        """validate_key() retourne None pour cle inexistante."""
        mock_redis.client.get.return_value = None  # Cache miss

        result = service.validate_key("mk_live_nonexistent_key_12345678")

        assert result is None

    @patch("app.services.api_key.redis_client")
    def test_validate_key_expired(self, mock_redis, service, test_db, admin_user):
        """validate_key() retourne None pour cle expiree."""
        mock_redis.client.get.return_value = None

        expired_data = ApiKeyCreate(
            name="Expired key",
            scopes=["products:read"],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        api_key, full_key = service.create_key(
            data=expired_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        result = service.validate_key(full_key)

        assert result is None

    @patch("app.services.api_key.redis_client")
    def test_validate_key_revoked(self, mock_redis, service, test_db, admin_user, create_data):
        """validate_key() retourne None pour cle revoquee."""
        mock_redis.client.get.return_value = None

        api_key, full_key = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        # Revoquer
        service.revoke_key(api_key.id, admin_user.tenant_id)
        test_db.commit()

        result = service.validate_key(full_key)

        assert result is None


class TestUpdateKey:
    """Tests pour mise a jour de cles."""

    @patch("app.services.api_key.redis_client")
    def test_update_key_name(self, mock_redis, service, test_db, admin_user, create_data):
        """update_key() met a jour le nom."""
        api_key, _ = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        updated = service.update_key(
            api_key.id,
            ApiKeyUpdate(name="Nouveau nom"),
            admin_user.tenant_id,
        )
        test_db.commit()
        test_db.refresh(updated)

        assert updated.name == "Nouveau nom"

    @patch("app.services.api_key.redis_client")
    def test_update_key_scopes(self, mock_redis, service, test_db, admin_user, create_data):
        """update_key() met a jour les scopes."""
        api_key, _ = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        updated = service.update_key(
            api_key.id,
            ApiKeyUpdate(scopes=["products:read"]),
            admin_user.tenant_id,
        )
        test_db.commit()
        test_db.refresh(updated)

        assert updated.scopes == ["products:read"]

    @patch("app.services.api_key.redis_client")
    def test_update_key_not_found(self, mock_redis, service, admin_user):
        """update_key() leve 404 si cle inexistante."""
        with pytest.raises(HTTPException) as exc_info:
            service.update_key(99999, ApiKeyUpdate(name="x"), admin_user.tenant_id)

        assert exc_info.value.status_code == 404

    @patch("app.services.api_key.redis_client")
    def test_update_key_cross_tenant(self, mock_redis, service, test_db, admin_user, admin_user_t2, create_data):
        """update_key() refuse la modification cross-tenant."""
        api_key, _ = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        # Tenant 2 essaie de modifier la cle de tenant 1
        with pytest.raises(HTTPException) as exc_info:
            service.update_key(api_key.id, ApiKeyUpdate(name="Hacked"), admin_user_t2.tenant_id)

        assert exc_info.value.status_code == 404


class TestRevokeKey:
    """Tests pour revocation de cles."""

    @patch("app.services.api_key.redis_client")
    def test_revoke_key_success(self, mock_redis, service, test_db, admin_user, create_data):
        """revoke_key() desactive la cle."""
        api_key, _ = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        revoked = service.revoke_key(api_key.id, admin_user.tenant_id)
        test_db.commit()
        test_db.refresh(revoked)

        assert revoked.is_active is False

    @patch("app.services.api_key.redis_client")
    def test_revoke_key_cross_tenant(self, mock_redis, service, test_db, admin_user, admin_user_t2, create_data):
        """revoke_key() refuse la revocation cross-tenant."""
        api_key, _ = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            service.revoke_key(api_key.id, admin_user_t2.tenant_id)

        assert exc_info.value.status_code == 404


class TestRotateKey:
    """Tests pour rotation de cles."""

    @patch("app.services.api_key.redis_client")
    def test_rotate_key_success(self, mock_redis, service, test_db, admin_user, create_data):
        """rotate_key() cree une nouvelle cle et revoque l'ancienne."""
        old_key, old_full = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()
        old_id = old_key.id

        new_key, new_full = service.rotate_key(old_id, admin_user.tenant_id)
        test_db.commit()
        test_db.refresh(new_key)

        # Nouvelle cle differente
        assert new_full != old_full
        assert new_key.id != old_id
        assert new_key.name == old_key.name
        assert new_key.scopes == old_key.scopes
        assert new_key.is_active is True

        # Ancienne cle revoquee
        test_db.refresh(old_key)
        assert old_key.is_active is False


class TestListKeys:
    """Tests pour listing de cles."""

    @patch("app.services.api_key.redis_client")
    def test_list_keys_tenant_isolation(self, mock_redis, service, test_db, admin_user, admin_user_t2, create_data):
        """list_keys() ne retourne que les cles du tenant."""
        # Cle tenant 1
        service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        # Cle tenant 2
        service.create_key(
            data=ApiKeyCreate(name="T2 key", scopes=["products:read"]),
            tenant_id=admin_user_t2.tenant_id,
            created_by=admin_user_t2.id,
        )
        test_db.commit()

        # Tenant 1 ne voit que sa cle
        keys_t1, total_t1 = service.list_keys(admin_user.tenant_id)
        assert total_t1 == 1
        assert keys_t1[0].tenant_id == 1

        # Tenant 2 ne voit que sa cle
        keys_t2, total_t2 = service.list_keys(admin_user_t2.tenant_id)
        assert total_t2 == 1
        assert keys_t2[0].tenant_id == 2

    @patch("app.services.api_key.redis_client")
    def test_list_keys_exclude_revoked(self, mock_redis, service, test_db, admin_user, create_data):
        """list_keys() exclut les cles revoquees par defaut."""
        key1, _ = service.create_key(
            data=create_data,
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        service.create_key(
            data=ApiKeyCreate(name="Active key", scopes=["products:read"]),
            tenant_id=admin_user.tenant_id,
            created_by=admin_user.id,
        )
        test_db.commit()

        service.revoke_key(key1.id, admin_user.tenant_id)
        test_db.commit()

        # Sans include_inactive
        keys, total = service.list_keys(admin_user.tenant_id)
        assert total == 1

        # Avec include_inactive
        keys_all, total_all = service.list_keys(admin_user.tenant_id, include_inactive=True)
        assert total_all == 2


class TestSchemaValidation:
    """Tests pour validation des schemas Pydantic."""

    def test_create_schema_valid_scopes(self):
        """ApiKeyCreate accepte des scopes valides."""
        data = ApiKeyCreate(
            name="Test",
            scopes=["products:read", "inventory:read"],
        )
        assert "inventory:read" in data.scopes
        assert "products:read" in data.scopes

    def test_create_schema_invalid_scopes(self):
        """ApiKeyCreate rejette des scopes invalides."""
        with pytest.raises(ValueError):
            ApiKeyCreate(
                name="Test",
                scopes=["invalid:scope"],
            )

    def test_create_schema_deduplicates_scopes(self):
        """ApiKeyCreate deduplique et trie les scopes."""
        data = ApiKeyCreate(
            name="Test",
            scopes=["products:read", "products:read", "inventory:read"],
        )
        assert data.scopes == ["inventory:read", "products:read"]

    def test_update_schema_optional_fields(self):
        """ApiKeyUpdate permet des champs optionnels."""
        data = ApiKeyUpdate(name="New name")
        assert data.name == "New name"
        assert data.scopes is None
        assert data.rate_limit is None
        assert data.is_active is None
