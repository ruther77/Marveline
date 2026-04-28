"""Tests CRUD IngredientSourcingService — gestion des mappings via service.

Couverture :
  1. list_mappings : tri par ordre + enrichissement produit + stock
  2. add_mapping : création nominale
  3. add_mapping : doublon (ingrédient+produit) → AlreadyExists
  4. add_mapping : ingrédient inexistant → NotFound
  5. add_mapping : produit inexistant → NotFound
  6. update_mapping : modifie ordre + facteur_conv
  7. update_mapping : mapping absent → NotFound
  8. remove_mapping : suppression OK
  9. reorder_mappings : batch update + retour trié
 10. cross-tenant : add/list sur ingrédient d'un autre tenant → NotFound
"""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.exceptions import AlreadyExists, NotFound
from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.schemas.restaurant.ingredient_epicerie_mapping import (
    MappingCreate,
    MappingReorderItem,
    MappingReorderRequest,
    MappingUpdate,
)
from app.services.restaurant.ingredient_sourcing import IngredientSourcingService

from tests.conftest import ASYNC_TEST_DATABASE_URL

_TENANT_RESTO = 3
_TENANT_RESTO_OTHER = 99
_TENANT_EPICERIE = 2


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _mk_ingredient(
    db: AsyncSession, nom: str = "Ingr", tenant_id: int = _TENANT_RESTO,
) -> IngredientRestaurant:
    ingr = IngredientRestaurant(
        tenant_id=tenant_id, nom=nom, unite_stock="L",
        stock_actuel=Decimal("0"), stock_alerte=Decimal("0"),
    )
    db.add(ingr)
    await db.flush()
    return ingr


async def _mk_produit(db: AsyncSession, designation: str = "Prod") -> EpicerieProduit:
    prod = EpicerieProduit(
        tenant_id=_TENANT_EPICERIE, designation_clean=designation,
        unite_vente="U", prix_achat_cts=500, prix_unitaire_cts=800,
    )
    db.add(prod)
    await db.flush()
    stock = EpicerieStock(
        tenant_id=_TENANT_EPICERIE, produit_id=prod.id,
        quantite=Decimal("10"), seuil_alerte=Decimal("0"),
    )
    db.add(stock)
    await db.flush()
    return prod


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_mapping_nominal(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)
    service = IngredientSourcingService(async_db)

    mapping = await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=prod.id, ordre=0, facteur_conv=Decimal("6")),
    )
    assert mapping.id is not None
    assert mapping.ingredient_id == ingr.id
    assert mapping.produit_id == prod.id
    assert mapping.ordre == 0


@pytest.mark.asyncio
async def test_add_mapping_doublon_already_exists(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)
    service = IngredientSourcingService(async_db)

    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=prod.id, ordre=0, facteur_conv=Decimal("1")),
    )
    await async_db.commit()

    with pytest.raises(AlreadyExists):
        await service.add_mapping(
            ingr.id, _TENANT_RESTO,
            MappingCreate(produit_id=prod.id, ordre=1, facteur_conv=Decimal("2")),
        )


@pytest.mark.asyncio
async def test_add_mapping_ingredient_inexistant(async_db: AsyncSession):
    prod = await _mk_produit(async_db)
    service = IngredientSourcingService(async_db)

    with pytest.raises(NotFound):
        await service.add_mapping(
            99999, _TENANT_RESTO,
            MappingCreate(produit_id=prod.id, ordre=0, facteur_conv=Decimal("1")),
        )


@pytest.mark.asyncio
async def test_add_mapping_produit_inexistant(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    service = IngredientSourcingService(async_db)

    with pytest.raises(NotFound):
        await service.add_mapping(
            ingr.id, _TENANT_RESTO,
            MappingCreate(produit_id=99999, ordre=0, facteur_conv=Decimal("1")),
        )


@pytest.mark.asyncio
async def test_update_mapping(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)
    service = IngredientSourcingService(async_db)
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=prod.id, ordre=0, facteur_conv=Decimal("1")),
    )

    updated = await service.update_mapping(
        ingr.id, prod.id, _TENANT_RESTO,
        MappingUpdate(ordre=3, facteur_conv=Decimal("12.5000")),
    )
    assert updated.ordre == 3
    assert Decimal(updated.facteur_conv) == Decimal("12.5000")


@pytest.mark.asyncio
async def test_update_mapping_absent(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    service = IngredientSourcingService(async_db)

    with pytest.raises(NotFound):
        await service.update_mapping(
            ingr.id, 99999, _TENANT_RESTO,
            MappingUpdate(ordre=5),
        )


@pytest.mark.asyncio
async def test_remove_mapping(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit(async_db)
    service = IngredientSourcingService(async_db)
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=prod.id, ordre=0, facteur_conv=Decimal("1")),
    )

    await service.remove_mapping(ingr.id, prod.id, _TENANT_RESTO)

    items = await service.list_mappings(ingr.id, _TENANT_RESTO)
    assert items == []


@pytest.mark.asyncio
async def test_list_mappings_enriched(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    p1 = await _mk_produit(async_db, "A")
    p2 = await _mk_produit(async_db, "B")
    service = IngredientSourcingService(async_db)
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=p2.id, ordre=1, facteur_conv=Decimal("2")),
    )
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=p1.id, ordre=0, facteur_conv=Decimal("5")),
    )

    items = await service.list_mappings(ingr.id, _TENANT_RESTO)
    assert len(items) == 2
    # Tri par ordre croissant
    assert items[0].produit_id == p1.id
    assert items[0].ordre == 0
    assert items[0].produit_designation == "A"
    assert items[0].produit_stock_disponible == Decimal("10")
    assert items[1].produit_id == p2.id


@pytest.mark.asyncio
async def test_reorder_mappings(async_db: AsyncSession):
    ingr = await _mk_ingredient(async_db)
    p1 = await _mk_produit(async_db, "A")
    p2 = await _mk_produit(async_db, "B")
    p3 = await _mk_produit(async_db, "C")
    service = IngredientSourcingService(async_db)
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=p1.id, ordre=0, facteur_conv=Decimal("1")),
    )
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=p2.id, ordre=1, facteur_conv=Decimal("1")),
    )
    await service.add_mapping(
        ingr.id, _TENANT_RESTO,
        MappingCreate(produit_id=p3.id, ordre=2, facteur_conv=Decimal("1")),
    )

    # On remap : p3 devient préféré, p1 devient dernier
    reordered = await service.reorder_mappings(
        ingr.id, _TENANT_RESTO,
        MappingReorderRequest(items=[
            MappingReorderItem(produit_id=p3.id, ordre=0),
            MappingReorderItem(produit_id=p2.id, ordre=1),
            MappingReorderItem(produit_id=p1.id, ordre=2),
        ]),
    )
    assert [m.produit_id for m in reordered] == [p3.id, p2.id, p1.id]


@pytest.mark.asyncio
async def test_cross_tenant_ingredient_notfound(async_db: AsyncSession):
    """Service appelé avec tenant B sur ingrédient du tenant A → NotFound."""
    ingr = await _mk_ingredient(async_db, tenant_id=_TENANT_RESTO)
    prod = await _mk_produit(async_db)
    service = IngredientSourcingService(async_db)

    with pytest.raises(NotFound):
        await service.list_mappings(ingr.id, _TENANT_RESTO_OTHER)

    with pytest.raises(NotFound):
        await service.add_mapping(
            ingr.id, _TENANT_RESTO_OTHER,
            MappingCreate(produit_id=prod.id, ordre=0, facteur_conv=Decimal("1")),
        )
