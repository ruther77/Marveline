"""Tests isolation cross-tenant VarianteSide (ISO-VARSIDE-01).

Bug découvert le 2026-04-14 : `AsyncVarianteSideRepo` n'appliquait aucun
filtre `tenant_id` sur ses 4 méthodes — un tenant pouvait lire/modifier
les associations plat-side d'un autre tenant.

Couverture :
  1. list_by_variante avec tenant mismatch → liste vide
  2. get avec tenant mismatch → None
  3. delete avec tenant mismatch → False (rien supprimé)
  4. create avec tenant explicite → scope correct
  5. update_side cross-tenant → NotFound (via service)
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.exceptions import NotFound
from app.models.restaurant.side_restaurant import SideRestaurant
from app.models.restaurant.variante_plat import VariantePlat
from app.models.restaurant.variante_side import VarianteSide
from app.repositories.restaurant.variante_side import AsyncVarianteSideRepo
from app.schemas.restaurant.variante_side import VarianteSideUpdate
from app.services.restaurant.variante_side import VarianteSideService

from tests.conftest import ASYNC_TEST_DATABASE_URL

# Deux tenants restaurant simulés (T3 = CaroCorp Restaurant, T99 = autre tenant)
_TENANT_A = 3
_TENANT_B = 99


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _seed_variante_plat(db: AsyncSession, tenant_id: int, nom: str) -> VariantePlat:
    plat = VariantePlat(
        tenant_id=tenant_id,
        nom=nom,
        type="plat",
        prix_vente_cts=150000,
        taux_tva=850,
        is_active=True,
    )
    db.add(plat)
    await db.flush()
    await db.refresh(plat)
    return plat


async def _seed_side(db: AsyncSession, tenant_id: int, nom: str) -> SideRestaurant:
    side = SideRestaurant(
        tenant_id=tenant_id,
        nom=nom,
        is_active=True,
    )
    db.add(side)
    await db.flush()
    await db.refresh(side)
    return side


async def _seed_variante_side(
    db: AsyncSession, tenant_id: int, variante_plat_id: int, side_id: int
) -> VarianteSide:
    vs = VarianteSide(
        tenant_id=tenant_id,
        variante_plat_id=variante_plat_id,
        side_id=side_id,
        supplement_cts=200,
        is_active=True,
    )
    db.add(vs)
    await db.flush()
    await db.refresh(vs)
    return vs


# ── Fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ── Tests repository ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_by_variante_isolates_tenant(async_db: AsyncSession):
    """list_by_variante du tenant A ne retourne PAS les entrées du tenant B."""
    plat_a = await _seed_variante_plat(async_db, _TENANT_A, "Plat A")
    plat_b = await _seed_variante_plat(async_db, _TENANT_B, "Plat B")
    side_a = await _seed_side(async_db, _TENANT_A, "Frites A")
    side_b = await _seed_side(async_db, _TENANT_B, "Frites B")

    await _seed_variante_side(async_db, _TENANT_A, plat_a.id, side_a.id)
    await _seed_variante_side(async_db, _TENANT_B, plat_b.id, side_b.id)

    repo = AsyncVarianteSideRepo(async_db)

    rows_a = await repo.list_by_variante(plat_a.id, _TENANT_A)
    rows_b = await repo.list_by_variante(plat_b.id, _TENANT_B)
    # Tenant A liste plat B → doit être vide (pas de fuite)
    rows_a_crosstenant = await repo.list_by_variante(plat_b.id, _TENANT_A)

    assert len(rows_a) == 1
    assert len(rows_b) == 1
    assert rows_a_crosstenant == []


@pytest.mark.asyncio
async def test_get_cross_tenant_returns_none(async_db: AsyncSession):
    """get() avec le mauvais tenant_id retourne None."""
    plat = await _seed_variante_plat(async_db, _TENANT_A, "Plat")
    side = await _seed_side(async_db, _TENANT_A, "Side")
    await _seed_variante_side(async_db, _TENANT_A, plat.id, side.id)

    repo = AsyncVarianteSideRepo(async_db)
    result_a = await repo.get(plat.id, side.id, _TENANT_A)
    result_b = await repo.get(plat.id, side.id, _TENANT_B)

    assert result_a is not None
    assert result_b is None


@pytest.mark.asyncio
async def test_delete_cross_tenant_fails_silently(async_db: AsyncSession):
    """delete() avec le mauvais tenant_id retourne False sans rien supprimer."""
    plat = await _seed_variante_plat(async_db, _TENANT_A, "Plat")
    side = await _seed_side(async_db, _TENANT_A, "Side")
    await _seed_variante_side(async_db, _TENANT_A, plat.id, side.id)

    repo = AsyncVarianteSideRepo(async_db)

    # Tentative de suppression cross-tenant
    deleted = await repo.delete(plat.id, side.id, _TENANT_B)
    assert deleted is False

    # L'entrée existe toujours côté tenant A
    still_there = await repo.get(plat.id, side.id, _TENANT_A)
    assert still_there is not None


@pytest.mark.asyncio
async def test_create_forces_tenant_id(async_db: AsyncSession):
    """create() exige tenant_id et l'assigne sur l'objet."""
    plat = await _seed_variante_plat(async_db, _TENANT_A, "Plat")
    side = await _seed_side(async_db, _TENANT_A, "Side")

    repo = AsyncVarianteSideRepo(async_db)
    obj = await repo.create(
        tenant_id=_TENANT_A,
        variante_plat_id=plat.id,
        side_id=side.id,
        supplement_cts=150,
    )
    assert obj.tenant_id == _TENANT_A


# ── Tests service ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_cross_tenant_raises_not_found(async_db: AsyncSession):
    """update_side cross-tenant → NotFound (et pas de mutation)."""
    plat = await _seed_variante_plat(async_db, _TENANT_A, "Plat")
    side = await _seed_side(async_db, _TENANT_A, "Side")
    vs = await _seed_variante_side(async_db, _TENANT_A, plat.id, side.id)
    original_supplement = vs.supplement_cts

    service = VarianteSideService(async_db)

    with pytest.raises(NotFound):
        await service.update_side(
            variante_plat_id=plat.id,
            side_id=side.id,
            tenant_id=_TENANT_B,
            payload=VarianteSideUpdate(supplement_cts=999),
        )

    # La valeur n'a pas été modifiée
    await async_db.refresh(vs)
    assert vs.supplement_cts == original_supplement


@pytest.mark.asyncio
async def test_remove_cross_tenant_returns_false(async_db: AsyncSession):
    """remove_side cross-tenant → False, entrée préservée."""
    plat = await _seed_variante_plat(async_db, _TENANT_A, "Plat")
    side = await _seed_side(async_db, _TENANT_A, "Side")
    await _seed_variante_side(async_db, _TENANT_A, plat.id, side.id)

    service = VarianteSideService(async_db)
    result = service.remove_side(plat.id, side.id, _TENANT_B)
    assert await result is False

    # Entrée toujours présente côté tenant A
    repo = AsyncVarianteSideRepo(async_db)
    still_there = await repo.get(plat.id, side.id, _TENANT_A)
    assert still_there is not None
