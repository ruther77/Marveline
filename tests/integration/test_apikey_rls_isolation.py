"""Tests intégration — F02 ApiKey set_tenant_context (B1.S1.T2).

Couvre la friction F02 (cf. `01-core-foundations.md` §F02 ligne 245) :
  - Avant fix : `_resolve_api_key_async` (et son pendant sync) ne nourrissaient
    PAS le contexte RLS PostgreSQL via `set_tenant_context()`. Une fois RLS
    activée (B1.S2), toutes les requêtes via ApiKey contournaient les policies
    tenant_id côté DB → fuite cross-tenant garantie.
  - Après fix : symétrie avec le chemin JWT (`get_current_user`) — appel
    obligatoire à `set_tenant_context(api_key.tenant_id)` + populate
    `request.state.{api_key_id, tenant_id}` (pré-requis F111 rate-limit identity).

Tests (validation du comportement de `_resolve_api_key_async`, indépendant
de RLS active — B1.S2 n'est pas encore livré) :
  1. Après résolution réussie : ContextVar `_current_tenant_id` = api_key.tenant_id
  2. Après résolution réussie : request.state.api_key_id + tenant_id populés
  3. Tenant_id du contexte = celui de l'ApiKey, pas un autre
  4. ApiKey expirée : pas de set_tenant_context (échec auth avant)
  5. ApiKey inexistante : pas de set_tenant_context (échec auth avant)
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import hashlib
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import _current_tenant_id, clear_tenant_context
from app.core.deps import _resolve_api_key_async
from app.models.api_key import ApiKey

from tests.conftest import ASYNC_TEST_DATABASE_URL


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def fake_request():
    """Mock FastAPI Request avec .state mutable et .client.host."""
    req = MagicMock()
    req.state = MagicMock()
    req.client.host = "127.0.0.1"
    return req


@pytest.fixture(autouse=True)
def _reset_tenant_context():
    """Reset _current_tenant_id avant ET après chaque test (isolation)."""
    clear_tenant_context()
    yield
    clear_tenant_context()


async def _create_api_key(
    db: AsyncSession,
    *,
    tenant_id: int = 1,
    name: str = "test-key",
    raw_key: str = "test-raw-key-value",
    is_active: bool = True,
    expires_at=None,
    scopes: list[str] | None = None,
    key_prefix: str | None = None,
) -> tuple[ApiKey, str]:
    """Helper : crée un ApiKey en DB avec hash calculé, retourne (key, raw)."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key = ApiKey(
        tenant_id=tenant_id,
        name=name,
        key_prefix=key_prefix or f"tk_{key_hash[:8]}",
        key_hash=key_hash,
        is_active=is_active,
        expires_at=expires_at,
        scopes=scopes or [],
        created_by=1,  # placeholder admin id (tests sans Account)
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key, raw_key


# ── Tests F02 régression ─────────────────────────────────────────────────────


class TestApiKeySetTenantContext:
    @pytest.mark.asyncio
    async def test_resolve_sets_current_tenant_id_contextvar(
        self, async_db, fake_request
    ):
        """F02 : après résolution réussie, _current_tenant_id = api_key.tenant_id."""
        api_key, raw = await _create_api_key(async_db, tenant_id=42)

        assert _current_tenant_id.get() is None  # baseline
        client = await _resolve_api_key_async(raw, async_db, fake_request)

        assert _current_tenant_id.get() == 42, (
            "F02 régression : _current_tenant_id non set après résolution ApiKey"
        )
        assert client.tenant_id == 42

    @pytest.mark.asyncio
    async def test_resolve_populates_request_state(
        self, async_db, fake_request
    ):
        """F02 : request.state.api_key_id et tenant_id populés (pré-requis F111)."""
        api_key, raw = await _create_api_key(async_db, tenant_id=7, name="kebabkey")

        await _resolve_api_key_async(raw, async_db, fake_request)

        assert fake_request.state.api_key_id == api_key.id
        assert fake_request.state.tenant_id == 7

    @pytest.mark.asyncio
    async def test_tenant_id_matches_apikey_tenant_not_other(
        self, async_db, fake_request
    ):
        """Régression cross-tenant : ApiKey du tenant A → contexte tenant A, pas autre."""
        # 2 ApiKeys sur 2 tenants distincts
        api_key_a, raw_a = await _create_api_key(
            async_db, tenant_id=100, name="a", raw_key="key-a-secret",
        )
        api_key_b, raw_b = await _create_api_key(
            async_db, tenant_id=200, name="b", raw_key="key-b-secret",
        )

        # Résoudre A → contexte = 100
        await _resolve_api_key_async(raw_a, async_db, fake_request)
        assert _current_tenant_id.get() == 100

        # Résoudre B → contexte = 200 (overwrite OK)
        await _resolve_api_key_async(raw_b, async_db, fake_request)
        assert _current_tenant_id.get() == 200

    @pytest.mark.asyncio
    async def test_expired_apikey_does_not_set_context(
        self, async_db, fake_request
    ):
        """ApiKey expirée → 401 levé AVANT set_tenant_context."""
        await _create_api_key(
            async_db, tenant_id=99,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_api_key_async("test-raw-key-value", async_db, fake_request)

        assert exc_info.value.status_code == 401
        assert _current_tenant_id.get() is None, (
            "set_tenant_context appelé sur ApiKey expirée — leak potentiel"
        )

    @pytest.mark.asyncio
    async def test_unknown_apikey_does_not_set_context(
        self, async_db, fake_request
    ):
        """ApiKey inexistante → 401 levé, contexte intouché."""
        with pytest.raises(HTTPException) as exc_info:
            await _resolve_api_key_async(
                "non-existent-key-value", async_db, fake_request
            )

        assert exc_info.value.status_code == 401
        assert _current_tenant_id.get() is None

    @pytest.mark.asyncio
    async def test_inactive_apikey_does_not_set_context(
        self, async_db, fake_request
    ):
        """ApiKey is_active=False → 401, contexte intouché.

        Note : la query filtre déjà sur is_active.is_(True), donc même retour
        que clé inexistante. Test explicite pour documenter l'invariant.
        """
        await _create_api_key(async_db, tenant_id=5, is_active=False)

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_api_key_async("test-raw-key-value", async_db, fake_request)

        assert exc_info.value.status_code == 401
        assert _current_tenant_id.get() is None
