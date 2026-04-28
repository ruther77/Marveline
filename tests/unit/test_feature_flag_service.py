"""Tests unitaires pour FeatureFlagService."""
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.models.feature_flag import FeatureFlag
from app.services.feature_flag import FeatureFlagService
from app.schemas.feature_flag import FeatureFlagCreate, FeatureFlagUpdate


@pytest.fixture
def service(async_db):
    """FeatureFlagService instance."""
    return FeatureFlagService(async_db)


@pytest.fixture
def sample_flag_data():
    """Valid feature flag creation payload."""
    return FeatureFlagCreate(
        name="stripe_payments",
        description="Active Stripe Checkout pour le tenant",
        is_enabled=True,
        target_tenants=[1, 2],
        rollout_pct=100,
    )


@pytest.mark.asyncio
class TestCreateFlag:
    """Tests pour creation de feature flags."""

    @patch("app.services.feature_flag.redis_client")
    async def test_create_flag_success(self, mock_redis, service, async_db,
                                       sample_flag_data):
        """create_flag() cree un flag valide."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()
        await async_db.refresh(flag)

        assert flag.id is not None
        assert flag.name == "stripe_payments"
        assert flag.description == "Active Stripe Checkout pour le tenant"
        assert flag.is_enabled is True
        assert flag.target_tenants == [1, 2]
        assert flag.rollout_pct == 100
        assert flag.created_at is not None
        assert flag.updated_at is not None

    @patch("app.services.feature_flag.redis_client")
    async def test_create_flag_defaults(self, mock_redis, service, async_db):
        """create_flag() utilise les valeurs par defaut."""
        data = FeatureFlagCreate(name="basic_flag")
        flag = await service.create_flag(data)
        await async_db.commit()
        await async_db.refresh(flag)

        assert flag.is_enabled is False
        assert flag.target_tenants is None
        assert flag.rollout_pct == 100
        assert flag.metadata_json is None

    @patch("app.services.feature_flag.redis_client")
    async def test_create_flag_duplicate_name_409(self, mock_redis, service, async_db,
                                                   sample_flag_data):
        """create_flag() leve 409 si le nom existe deja."""
        await service.create_flag(sample_flag_data)
        await async_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            await service.create_flag(sample_flag_data)

        assert exc_info.value.status_code == 409
        assert "existe deja" in exc_info.value.detail

    def test_create_flag_invalid_name_format(self):
        """FeatureFlagCreate rejette un nom avec format invalide."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FeatureFlagCreate(name="InvalidName")

        with pytest.raises(ValidationError):
            FeatureFlagCreate(name="123_starts_with_digit")

    def test_create_flag_invalid_rollout_pct(self):
        """FeatureFlagCreate rejette rollout_pct hors bornes."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FeatureFlagCreate(name="test_flag", rollout_pct=101)

        with pytest.raises(ValidationError):
            FeatureFlagCreate(name="test_flag", rollout_pct=-1)


@pytest.mark.asyncio
class TestUpdateFlag:
    """Tests pour mise a jour de feature flags."""

    @patch("app.services.feature_flag.redis_client")
    async def test_update_flag_description(self, mock_redis, service, async_db,
                                           sample_flag_data):
        """update_flag() met a jour la description."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        updated = await service.update_flag(flag.id,
                                            FeatureFlagUpdate(description="Nouvelle desc"))
        await async_db.commit()
        await async_db.refresh(updated)

        assert updated.description == "Nouvelle desc"
        assert updated.name == "stripe_payments"  # Inchange

    @patch("app.services.feature_flag.redis_client")
    async def test_update_flag_is_enabled(self, mock_redis, service, async_db,
                                          sample_flag_data):
        """update_flag() bascule is_enabled."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        updated = await service.update_flag(flag.id, FeatureFlagUpdate(is_enabled=False))
        await async_db.commit()
        await async_db.refresh(updated)

        assert updated.is_enabled is False

    @patch("app.services.feature_flag.redis_client")
    async def test_update_flag_rollout_pct(self, mock_redis, service, async_db,
                                           sample_flag_data):
        """update_flag() met a jour le rollout_pct."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        updated = await service.update_flag(flag.id, FeatureFlagUpdate(rollout_pct=50))
        await async_db.commit()
        await async_db.refresh(updated)

        assert updated.rollout_pct == 50

    @patch("app.services.feature_flag.redis_client")
    async def test_update_flag_target_tenants(self, mock_redis, service, async_db,
                                              sample_flag_data):
        """update_flag() met a jour target_tenants."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        updated = await service.update_flag(
            flag.id, FeatureFlagUpdate(target_tenants=[3, 4, 5])
        )
        await async_db.commit()
        await async_db.refresh(updated)

        assert updated.target_tenants == [3, 4, 5]

    @patch("app.services.feature_flag.redis_client")
    async def test_update_flag_not_found_404(self, mock_redis, service):
        """update_flag() leve 404 si flag inexistant."""
        with pytest.raises(HTTPException) as exc_info:
            await service.update_flag(99999, FeatureFlagUpdate(is_enabled=False))

        assert exc_info.value.status_code == 404

    @patch("app.services.feature_flag.redis_client")
    async def test_update_flag_invalidates_cache(self, mock_redis, service, async_db,
                                                  sample_flag_data):
        """update_flag() invalide le cache Redis."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        await service.update_flag(flag.id, FeatureFlagUpdate(is_enabled=False))
        await async_db.commit()

        mock_redis.client.delete.assert_called()


@pytest.mark.asyncio
class TestDeleteFlag:
    """Tests pour suppression de feature flags."""

    @patch("app.services.feature_flag.redis_client")
    async def test_delete_flag_success(self, mock_redis, service, async_db,
                                       sample_flag_data):
        """delete_flag() supprime le flag physiquement."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()
        flag_id = flag.id

        await service.delete_flag(flag_id)
        await async_db.commit()

        # Flag plus en base
        assert await async_db.get(FeatureFlag, flag_id) is None

    @patch("app.services.feature_flag.redis_client")
    async def test_delete_flag_not_found_404(self, mock_redis, service):
        """delete_flag() leve 404 si flag inexistant."""
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_flag(99999)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestGetFlag:
    """Tests pour recuperation de feature flags."""

    @patch("app.services.feature_flag.redis_client")
    async def test_get_flag_by_id(self, mock_redis, service, async_db, sample_flag_data):
        """get_flag() retourne le flag par ID."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        result = await service.get_flag(flag.id)
        assert result.id == flag.id
        assert result.name == "stripe_payments"

    @patch("app.services.feature_flag.redis_client")
    async def test_get_flag_not_found_404(self, mock_redis, service):
        """get_flag() leve 404 si inexistant."""
        with pytest.raises(HTTPException) as exc_info:
            await service.get_flag(99999)

        assert exc_info.value.status_code == 404

    @patch("app.services.feature_flag.redis_client")
    async def test_get_flag_by_name(self, mock_redis, service, async_db,
                                    sample_flag_data):
        """get_flag_by_name() retourne le flag par nom."""
        flag = await service.create_flag(sample_flag_data)
        await async_db.commit()

        result = await service.get_flag_by_name("stripe_payments")
        assert result.id == flag.id

    @patch("app.services.feature_flag.redis_client")
    async def test_get_flag_by_name_not_found_404(self, mock_redis, service):
        """get_flag_by_name() leve 404 si inexistant."""
        with pytest.raises(HTTPException) as exc_info:
            await service.get_flag_by_name("nonexistent_flag")

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestListFlags:
    """Tests pour listing de feature flags."""

    @patch("app.services.feature_flag.redis_client")
    async def test_list_flags_empty(self, mock_redis, service):
        """list_flags() retourne liste vide si aucun flag."""
        flags, total = await service.list_flags()
        assert flags == []
        assert total == 0

    @patch("app.services.feature_flag.redis_client")
    async def test_list_flags_multiple(self, mock_redis, service, async_db):
        """list_flags() retourne tous les flags."""
        await service.create_flag(FeatureFlagCreate(name="flag_a", is_enabled=True))
        await service.create_flag(FeatureFlagCreate(name="flag_b", is_enabled=False))
        await service.create_flag(FeatureFlagCreate(name="flag_c", is_enabled=True))
        await async_db.commit()

        flags, total = await service.list_flags()
        assert total == 3
        assert len(flags) == 3
        # Tri par nom
        names = [f.name for f in flags]
        assert names == sorted(names)

    @patch("app.services.feature_flag.redis_client")
    async def test_list_flags_pagination(self, mock_redis, service, async_db):
        """list_flags() respecte skip/limit."""
        for i in range(5):
            await service.create_flag(FeatureFlagCreate(name=f"flag_{chr(97+i)}"))
        await async_db.commit()

        flags, total = await service.list_flags(skip=2, limit=2)
        assert total == 5
        assert len(flags) == 2


@pytest.mark.asyncio
class TestIsFeatureEnabled:
    """Tests pour evaluation de feature flags."""

    @patch("app.services.feature_flag.redis_client")
    async def test_kill_switch_disabled(self, mock_redis, service, async_db):
        """is_enabled=False retourne (False, 'kill_switch')."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="disabled_flag",
            is_enabled=False,
            target_tenants=[1, 2],
        ))
        await async_db.commit()

        enabled, reason = await service.is_feature_enabled("disabled_flag", tenant_id=1)
        assert enabled is False
        assert reason == "kill_switch"

    @patch("app.services.feature_flag.redis_client")
    async def test_whitelist_tenant_in_list(self, mock_redis, service, async_db):
        """Tenant dans target_tenants retourne (True, 'whitelist')."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="whitelist_flag",
            is_enabled=True,
            target_tenants=[1, 2, 3],
        ))
        await async_db.commit()

        enabled, reason = await service.is_feature_enabled("whitelist_flag", tenant_id=2)
        assert enabled is True
        assert reason == "whitelist"

    @patch("app.services.feature_flag.redis_client")
    async def test_whitelist_tenant_not_in_list(self, mock_redis, service, async_db):
        """Tenant hors target_tenants retourne (False, 'not_in_whitelist')."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="whitelist_flag2",
            is_enabled=True,
            target_tenants=[1, 2],
        ))
        await async_db.commit()

        enabled, reason = await service.is_feature_enabled("whitelist_flag2", tenant_id=99)
        assert enabled is False
        assert reason == "not_in_whitelist"

    @patch("app.services.feature_flag.redis_client")
    async def test_whitelist_empty_list(self, mock_redis, service, async_db):
        """target_tenants=[] retourne (False, 'not_in_whitelist') pour tous."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="empty_whitelist",
            is_enabled=True,
            target_tenants=[],
        ))
        await async_db.commit()

        enabled, reason = await service.is_feature_enabled("empty_whitelist", tenant_id=1)
        assert enabled is False
        assert reason == "not_in_whitelist"

    @patch("app.services.feature_flag.redis_client")
    async def test_rollout_100_percent(self, mock_redis, service, async_db):
        """rollout_pct=100 retourne (True, 'rollout') pour tous."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="full_rollout",
            is_enabled=True,
            target_tenants=None,
            rollout_pct=100,
        ))
        await async_db.commit()

        enabled, reason = await service.is_feature_enabled("full_rollout", tenant_id=42)
        assert enabled is True
        assert reason == "rollout"

    @patch("app.services.feature_flag.redis_client")
    async def test_rollout_0_percent(self, mock_redis, service, async_db):
        """rollout_pct=0 retourne (False, 'rollout') pour tous."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="no_rollout",
            is_enabled=True,
            target_tenants=None,
            rollout_pct=0,
        ))
        await async_db.commit()

        enabled, reason = await service.is_feature_enabled("no_rollout", tenant_id=42)
        assert enabled is False
        assert reason == "rollout"

    @patch("app.services.feature_flag.redis_client")
    async def test_rollout_deterministic(self, mock_redis, service, async_db):
        """Le rollout est deterministe (meme resultat pour meme tenant)."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="partial_rollout",
            is_enabled=True,
            target_tenants=None,
            rollout_pct=50,
        ))
        await async_db.commit()

        results = []
        for _ in range(10):
            enabled, _ = await service.is_feature_enabled("partial_rollout", tenant_id=42)
            results.append(enabled)

        # Toutes les evaluations sont identiques (deterministe)
        assert all(r == results[0] for r in results)

    @patch("app.services.feature_flag.redis_client")
    async def test_rollout_different_tenants(self, mock_redis, service, async_db):
        """Differents tenants obtiennent des resultats differents avec rollout partiel."""
        mock_redis.client.get.return_value = None

        await service.create_flag(FeatureFlagCreate(
            name="varied_rollout",
            is_enabled=True,
            target_tenants=None,
            rollout_pct=50,
        ))
        await async_db.commit()

        results = set()
        for tid in range(1, 101):
            enabled, _ = await service.is_feature_enabled("varied_rollout", tenant_id=tid)
            results.add(enabled)

        # Avec 100 tenants et 50%, on devrait avoir True et False
        assert True in results
        assert False in results

    @patch("app.services.feature_flag.redis_client")
    async def test_flag_not_found(self, mock_redis, service, async_db):
        """Flag inexistant retourne (False, 'not_found')."""
        mock_redis.client.get.return_value = None

        enabled, reason = await service.is_feature_enabled("nonexistent_flag", tenant_id=1)
        assert enabled is False
        assert reason == "not_found"


class TestSchemaValidation:
    """Tests pour validation des schemas Pydantic."""

    def test_create_schema_valid_name(self):
        """FeatureFlagCreate accepte un nom snake_case."""
        data = FeatureFlagCreate(name="my_feature_flag")
        assert data.name == "my_feature_flag"

    def test_create_schema_invalid_name(self):
        """FeatureFlagCreate rejette un nom invalide."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FeatureFlagCreate(name="Invalid-Name")

    def test_create_schema_deduplicate_tenants(self):
        """FeatureFlagCreate deduplique et trie les tenant IDs."""
        data = FeatureFlagCreate(
            name="test_flag",
            target_tenants=[3, 1, 2, 1, 3],
        )
        assert data.target_tenants == [1, 2, 3]

    def test_create_schema_negative_tenant_id(self):
        """FeatureFlagCreate rejette les tenant IDs negatifs."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FeatureFlagCreate(
                name="test_flag",
                target_tenants=[1, -1],
            )

    def test_update_schema_optional_fields(self):
        """FeatureFlagUpdate permet des champs optionnels."""
        data = FeatureFlagUpdate(is_enabled=True)
        assert data.is_enabled is True
        assert data.description is None
        assert data.rollout_pct is None
        assert data.target_tenants is None

    def test_create_schema_with_metadata(self):
        """FeatureFlagCreate accepte metadata_json."""
        data = FeatureFlagCreate(
            name="premium_flag",
            metadata_json={"tier": "premium", "min_plan": "business"},
        )
        assert data.metadata_json["tier"] == "premium"
