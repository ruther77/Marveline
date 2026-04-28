"""Tests modèle IngredientEpicerieMapping — table pivot ingrédient ↔ produits épicerie.

Couverture :
  1. Création nominale : tenant_id, ordre, facteur_conv persistés
  2. Contrainte UNIQUE (ingredient_id, produit_id) : pas de doublon pour même paire
  3. CheckConstraint ordre >= 0
  4. CheckConstraint facteur_conv > 0
  5. Cascade DELETE sur ingredient → mappings supprimés
  6. Cascade DELETE sur produit → mappings supprimés
  7. Plusieurs produits par ingrédient avec ordres différents (fallbacks)
  8. Un produit peut mapper plusieurs ingrédients (cardinalité N:N)
"""
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.epicerie.produit import EpicerieProduit
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant

from tests.conftest import ASYNC_TEST_DATABASE_URL

_TENANT_RESTO = 3
_TENANT_EPICERIE = 2


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _mk_ingredient(db: AsyncSession, nom: str = "Huile d'olive") -> IngredientRestaurant:
    ingr = IngredientRestaurant(
        tenant_id=_TENANT_RESTO,
        nom=nom,
        unite_stock="L",
        stock_actuel=Decimal("0.000"),
        stock_alerte=Decimal("5.000"),
    )
    db.add(ingr)
    await db.flush()
    return ingr


async def _mk_produit(db: AsyncSession, designation: str = "Huile olive 1L") -> EpicerieProduit:
    prod = EpicerieProduit(
        tenant_id=_TENANT_EPICERIE,
        designation_clean=designation,
        unite_vente="U",
        prix_achat_cts=500,
        prix_unitaire_cts=800,
    )
    db.add(prod)
    await db.flush()
    return prod


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_nominal(async_db: AsyncSession):
    """Création basique : tenant_id, ordre, facteur_conv bien persistés."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)

    mapping = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO,
        ingredient_id=ingr.id,
        produit_id=prod.id,
        ordre=0,
        facteur_conv=Decimal("6.0000"),
    )
    async_db.add(mapping)
    await async_db.flush()

    assert mapping.id is not None
    assert mapping.tenant_id == _TENANT_RESTO
    assert mapping.ordre == 0
    assert Decimal(mapping.facteur_conv) == Decimal("6.0000")


@pytest.mark.asyncio
async def test_unique_constraint_ingr_produit(async_db: AsyncSession):
    """Deux mappings pour la même paire (ingredient, produit) → IntegrityError."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)

    m1 = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=prod.id,
        ordre=0, facteur_conv=Decimal("1.0"),
    )
    async_db.add(m1)
    await async_db.flush()

    m2 = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=prod.id,
        ordre=1, facteur_conv=Decimal("2.0"),
    )
    async_db.add(m2)
    with pytest.raises(IntegrityError):
        await async_db.flush()
    await async_db.rollback()


@pytest.mark.asyncio
async def test_ordre_negatif_rejete(async_db: AsyncSession):
    """CheckConstraint ordre >= 0 : ordre = -1 → IntegrityError."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)

    m = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=prod.id,
        ordre=-1, facteur_conv=Decimal("1.0"),
    )
    async_db.add(m)
    with pytest.raises(IntegrityError):
        await async_db.flush()
    await async_db.rollback()


@pytest.mark.asyncio
async def test_facteur_conv_zero_rejete(async_db: AsyncSession):
    """CheckConstraint facteur_conv > 0 : 0 → IntegrityError."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)

    m = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=prod.id,
        ordre=0, facteur_conv=Decimal("0"),
    )
    async_db.add(m)
    with pytest.raises(IntegrityError):
        await async_db.flush()
    await async_db.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_ingredient(async_db: AsyncSession):
    """DELETE sur IngredientRestaurant → mappings associés supprimés (CASCADE)."""
    from sqlalchemy import select

    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)
    m = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=prod.id,
        ordre=0, facteur_conv=Decimal("1.0"),
    )
    async_db.add(m)
    await async_db.flush()
    mapping_id = m.id

    await async_db.delete(ingr)
    await async_db.flush()

    remaining = await async_db.execute(
        select(IngredientEpicerieMapping).where(IngredientEpicerieMapping.id == mapping_id)
    )
    assert remaining.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cascade_delete_produit(async_db: AsyncSession):
    """DELETE sur EpicerieProduit → mappings associés supprimés (CASCADE)."""
    from sqlalchemy import select

    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)
    m = IngredientEpicerieMapping(
        tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=prod.id,
        ordre=0, facteur_conv=Decimal("1.0"),
    )
    async_db.add(m)
    await async_db.flush()
    mapping_id = m.id

    await async_db.delete(prod)
    await async_db.flush()

    remaining = await async_db.execute(
        select(IngredientEpicerieMapping).where(IngredientEpicerieMapping.id == mapping_id)
    )
    assert remaining.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_plusieurs_produits_ordre_different(async_db: AsyncSession):
    """Un ingrédient peut avoir N produits avec ordres distincts (fallbacks)."""
    from sqlalchemy import select

    ingr = await _mk_ingredient(async_db)
    p1 = await _mk_produit(async_db, "Bidon 5L")
    p2 = await _mk_produit(async_db, "Bouteille 1L")

    async_db.add_all([
        IngredientEpicerieMapping(
            tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=p1.id,
            ordre=0, facteur_conv=Decimal("5.0"),
        ),
        IngredientEpicerieMapping(
            tenant_id=_TENANT_RESTO, ingredient_id=ingr.id, produit_id=p2.id,
            ordre=1, facteur_conv=Decimal("1.0"),
        ),
    ])
    await async_db.flush()

    rows = await async_db.execute(
        select(IngredientEpicerieMapping)
        .where(IngredientEpicerieMapping.ingredient_id == ingr.id)
        .order_by(IngredientEpicerieMapping.ordre)
    )
    items = rows.scalars().all()
    assert len(items) == 2
    assert items[0].produit_id == p1.id
    assert items[1].produit_id == p2.id


@pytest.mark.asyncio
async def test_produit_partage_entre_ingredients(async_db: AsyncSession):
    """Un même produit peut mapper plusieurs ingrédients (cardinalité N:N)."""
    from sqlalchemy import select

    huile_cuisson = await _mk_ingredient(async_db, "Huile cuisson")
    huile_assaison = await _mk_ingredient(async_db, "Huile assaisonnement")
    prod = await _mk_produit(async_db, "Bouteille huile 1L × 6")

    async_db.add_all([
        IngredientEpicerieMapping(
            tenant_id=_TENANT_RESTO, ingredient_id=huile_cuisson.id, produit_id=prod.id,
            ordre=0, facteur_conv=Decimal("6.0"),
        ),
        IngredientEpicerieMapping(
            tenant_id=_TENANT_RESTO, ingredient_id=huile_assaison.id, produit_id=prod.id,
            ordre=0, facteur_conv=Decimal("6.0"),
        ),
    ])
    await async_db.flush()

    rows = await async_db.execute(
        select(IngredientEpicerieMapping)
        .where(IngredientEpicerieMapping.produit_id == prod.id)
    )
    assert len(rows.scalars().all()) == 2
