"""Tests repository EpicerieProduit EAN secondaires (multi-EAN).

Couvre :
  1. add_secondary_ean nominal
  2. add_secondary_ean idempotent (2x même ean/produit → 1 entrée)
  3. list_secondary_eans retourne les entrées
  4. get_by_ean_multi : EAN principal puis EAN secondaire
  5. Isolation cross-tenant (même EAN valeur, tenants différents OK)
"""
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.produit_ean import EpicerieProduitEan
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository

from tests.conftest import ASYNC_TEST_DATABASE_URL

_TENANT_A = 2
_TENANT_B = 3


async def _seed_produit(
    db: AsyncSession,
    tenant_id: int = _TENANT_A,
    designation: str = "PRODUIT TEST",
    ean: str | None = None,
) -> EpicerieProduit:
    produit = EpicerieProduit(
        tenant_id=tenant_id,
        designation_clean=designation,
        prix_unitaire_cts=500,
        unite_vente="U",
        ean=ean,
        actif=True,
    )
    db.add(produit)
    await db.flush()
    await db.refresh(produit)
    return produit


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_add_secondary_ean_nominal(async_db):
    """Ajout d'un EAN secondaire crée une entrée pivot."""
    db = async_db
    produit = await _seed_produit(db, ean="1000000000013")
    repo = AsyncEpicerieProduitRepository(db)

    entry = await repo.add_secondary_ean(
        produit_id=produit.id,
        ean="2000000000027",
        tenant_id=_TENANT_A,
        source_fournisseur="METRO",
    )

    assert entry.id is not None
    assert entry.produit_id == produit.id
    assert entry.ean == "2000000000027"
    assert entry.tenant_id == _TENANT_A
    assert entry.source_fournisseur == "METRO"


@pytest.mark.asyncio
async def test_add_secondary_ean_idempotent(async_db):
    """Ajouter 2x le même EAN pour le même produit → 1 seule entrée."""
    db = async_db
    produit = await _seed_produit(db)
    repo = AsyncEpicerieProduitRepository(db)

    first = await repo.add_secondary_ean(
        produit_id=produit.id, ean="3000000000031", tenant_id=_TENANT_A,
    )
    second = await repo.add_secondary_ean(
        produit_id=produit.id, ean="3000000000031", tenant_id=_TENANT_A,
    )

    assert first.id == second.id

    count = await db.execute(
        select(func.count()).select_from(EpicerieProduitEan).where(
            EpicerieProduitEan.ean == "3000000000031",
            EpicerieProduitEan.tenant_id == _TENANT_A,
        )
    )
    assert count.scalar_one() == 1


@pytest.mark.asyncio
async def test_list_secondary_eans(async_db):
    """list_secondary_eans retourne les EANs d'un produit, ordonnés par date."""
    db = async_db
    produit = await _seed_produit(db)
    repo = AsyncEpicerieProduitRepository(db)

    await repo.add_secondary_ean(
        produit_id=produit.id, ean="4000000000045", tenant_id=_TENANT_A,
        source_fournisseur="TAIYAT",
    )
    await repo.add_secondary_ean(
        produit_id=produit.id, ean="5000000000059", tenant_id=_TENANT_A,
    )

    eans = await repo.list_secondary_eans(produit.id, _TENANT_A)
    values = {e.ean for e in eans}
    assert values == {"4000000000045", "5000000000059"}


@pytest.mark.asyncio
async def test_get_by_ean_multi_principal_then_secondary(async_db):
    """get_by_ean_multi trouve via EAN principal, puis via pivot."""
    db = async_db
    produit = await _seed_produit(db, ean="6000000000066")
    repo = AsyncEpicerieProduitRepository(db)

    await repo.add_secondary_ean(
        produit_id=produit.id, ean="7000000000070", tenant_id=_TENANT_A,
    )

    via_principal = await repo.get_by_ean_multi("6000000000066", _TENANT_A)
    via_secondary = await repo.get_by_ean_multi("7000000000070", _TENANT_A)

    assert via_principal is not None and via_principal.id == produit.id
    assert via_secondary is not None and via_secondary.id == produit.id


@pytest.mark.asyncio
async def test_eans_cross_tenant_isolation(async_db):
    """Même valeur EAN sur deux tenants : chacun voit seulement le sien."""
    db = async_db
    produit_a = await _seed_produit(db, tenant_id=_TENANT_A, designation="P-A")
    produit_b = await _seed_produit(db, tenant_id=_TENANT_B, designation="P-B")
    repo = AsyncEpicerieProduitRepository(db)

    await repo.add_secondary_ean(
        produit_id=produit_a.id, ean="8000000000084", tenant_id=_TENANT_A,
    )
    await repo.add_secondary_ean(
        produit_id=produit_b.id, ean="8000000000084", tenant_id=_TENANT_B,
    )

    from_a = await repo.get_by_ean_multi("8000000000084", _TENANT_A)
    from_b = await repo.get_by_ean_multi("8000000000084", _TENANT_B)

    assert from_a is not None and from_a.id == produit_a.id
    assert from_b is not None and from_b.id == produit_b.id

    eans_a = await repo.list_secondary_eans(produit_a.id, _TENANT_A)
    assert len(eans_a) == 1 and eans_a[0].tenant_id == _TENANT_A

    leak = await repo.list_secondary_eans(produit_b.id, _TENANT_A)
    assert leak == []
