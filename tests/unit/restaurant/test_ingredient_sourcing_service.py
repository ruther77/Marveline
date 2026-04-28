"""Tests IngredientSourcingService — résolveur cascade mixte.

Couverture :
  1. Un produit suffit (stock > besoin)
  2. Cascade mixte : n°1 partiel + n°2 complète
  3. Rupture totale : deficit signalé
  4. Ingrédient sans mapping → 0 items, deficit = besoin
  5. Produit sans ligne stock → skip (considéré 0)
  6. Cross-tenant → ValueError
  7. Ordre respecté (préféré en tête, fallbacks après)
  8. Conversion : facteur_conv appliqué correctement
"""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.epicerie.produit import EpicerieProduit
from app.models.epicerie.stock import EpicerieStock
from app.models.restaurant.ingredient_epicerie_mapping import IngredientEpicerieMapping
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.services.restaurant.ingredient_sourcing import IngredientSourcingService

from tests.conftest import ASYNC_TEST_DATABASE_URL

_TENANT_RESTO = 3
_TENANT_RESTO_OTHER = 99
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


async def _mk_ingredient(
    db: AsyncSession, nom: str = "Huile d'olive", tenant_id: int = _TENANT_RESTO,
    unite: str = "L",
) -> IngredientRestaurant:
    ingr = IngredientRestaurant(
        tenant_id=tenant_id, nom=nom, unite_stock=unite,
        stock_actuel=Decimal("0.000"), stock_alerte=Decimal("5.000"),
    )
    db.add(ingr)
    await db.flush()
    return ingr


async def _mk_produit_avec_stock(
    db: AsyncSession, designation: str, unite_vente: str, stock_qte: Decimal,
) -> EpicerieProduit:
    prod = EpicerieProduit(
        tenant_id=_TENANT_EPICERIE,
        designation_clean=designation,
        unite_vente=unite_vente,
        prix_achat_cts=500,
        prix_unitaire_cts=800,
    )
    db.add(prod)
    await db.flush()
    stock = EpicerieStock(
        tenant_id=_TENANT_EPICERIE,
        produit_id=prod.id,
        quantite=stock_qte,
        seuil_alerte=Decimal("0"),
    )
    db.add(stock)
    await db.flush()
    return prod


async def _mk_mapping(
    db: AsyncSession, ingredient_id: int, produit_id: int,
    ordre: int, facteur_conv: Decimal, tenant_id: int = _TENANT_RESTO,
) -> IngredientEpicerieMapping:
    m = IngredientEpicerieMapping(
        tenant_id=tenant_id,
        ingredient_id=ingredient_id,
        produit_id=produit_id,
        ordre=ordre,
        facteur_conv=facteur_conv,
    )
    db.add(m)
    await db.flush()
    return m


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_produit_suffit(async_db: AsyncSession):
    """Produit préféré a assez de stock : tout prélevé sur lui, déficit = 0."""
    ingr = await _mk_ingredient(async_db)
    prod = await _mk_produit_avec_stock(async_db, "Bidon 5L", "U", Decimal("10"))
    await _mk_mapping(async_db, ingr.id, prod.id, ordre=0, facteur_conv=Decimal("5"))

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("20"), _TENANT_RESTO)

    assert res.couverture_complete is True
    assert res.deficit == Decimal("0")
    assert len(res.items) == 1
    assert res.items[0].produit_id == prod.id
    assert res.items[0].qte_couverte_besoin == Decimal("20")
    # 20 L / facteur 5 = 4 bidons
    assert res.items[0].qte_prelevee_unites_vente == Decimal("4")


@pytest.mark.asyncio
async def test_cascade_mixte_partiel_puis_complet(async_db: AsyncSession):
    """n°1 couvre partiellement, n°2 complète le reste."""
    ingr = await _mk_ingredient(async_db)
    # n°1 : Bidon 5L, stock 2 → peut fournir 10L
    p1 = await _mk_produit_avec_stock(async_db, "Bidon 5L", "U", Decimal("2"))
    # n°2 : Bouteille 1L, stock 10 → peut fournir 10L
    p2 = await _mk_produit_avec_stock(async_db, "Bouteille 1L", "U", Decimal("10"))
    await _mk_mapping(async_db, ingr.id, p1.id, ordre=0, facteur_conv=Decimal("5"))
    await _mk_mapping(async_db, ingr.id, p2.id, ordre=1, facteur_conv=Decimal("1"))

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("15"), _TENANT_RESTO)

    assert res.couverture_complete is True
    assert res.deficit == Decimal("0")
    assert len(res.items) == 2
    assert res.items[0].produit_id == p1.id
    assert res.items[0].qte_couverte_besoin == Decimal("10")  # tout le stock
    assert res.items[0].qte_prelevee_unites_vente == Decimal("2")
    assert res.items[1].produit_id == p2.id
    assert res.items[1].qte_couverte_besoin == Decimal("5")
    assert res.items[1].qte_prelevee_unites_vente == Decimal("5")


@pytest.mark.asyncio
async def test_rupture_totale_deficit_signale(async_db: AsyncSession):
    """Besoin > stock cumulé total → deficit > 0, couverture_complete = False."""
    ingr = await _mk_ingredient(async_db)
    p1 = await _mk_produit_avec_stock(async_db, "Bidon 5L", "U", Decimal("1"))  # 5L
    p2 = await _mk_produit_avec_stock(async_db, "Bouteille 1L", "U", Decimal("2"))  # 2L
    await _mk_mapping(async_db, ingr.id, p1.id, ordre=0, facteur_conv=Decimal("5"))
    await _mk_mapping(async_db, ingr.id, p2.id, ordre=1, facteur_conv=Decimal("1"))

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("20"), _TENANT_RESTO)

    assert res.couverture_complete is False
    assert res.qte_couverte_totale == Decimal("7")  # 5 + 2
    assert res.deficit == Decimal("13")  # 20 - 7
    assert len(res.items) == 2


@pytest.mark.asyncio
async def test_ingredient_sans_mapping(async_db: AsyncSession):
    """Ingrédient sans aucun produit mappé → items vide, deficit = besoin."""
    ingr = await _mk_ingredient(async_db)

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("5"), _TENANT_RESTO)

    assert res.couverture_complete is False
    assert res.qte_couverte_totale == Decimal("0")
    assert res.deficit == Decimal("5")
    assert res.items == []


@pytest.mark.asyncio
async def test_produit_sans_ligne_stock_est_skip(async_db: AsyncSession):
    """Produit sans EpicerieStock (stock inexistant) → traité comme rupture, skip."""
    ingr = await _mk_ingredient(async_db)
    # Produit sans entrée EpicerieStock
    prod_sans_stock = EpicerieProduit(
        tenant_id=_TENANT_EPICERIE, designation_clean="Produit sans stock",
        unite_vente="U", prix_achat_cts=500, prix_unitaire_cts=800,
    )
    async_db.add(prod_sans_stock)
    await async_db.flush()
    # Produit avec stock
    prod_ok = await _mk_produit_avec_stock(async_db, "OK", "U", Decimal("3"))
    await _mk_mapping(async_db, ingr.id, prod_sans_stock.id, ordre=0, facteur_conv=Decimal("1"))
    await _mk_mapping(async_db, ingr.id, prod_ok.id, ordre=1, facteur_conv=Decimal("1"))

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("3"), _TENANT_RESTO)

    assert res.couverture_complete is True
    assert len(res.items) == 1
    assert res.items[0].produit_id == prod_ok.id


@pytest.mark.asyncio
async def test_cross_tenant_raise(async_db: AsyncSession):
    """Résolveur appelé avec un tenant_id différent → ValueError."""
    ingr = await _mk_ingredient(async_db, tenant_id=_TENANT_RESTO)
    service = IngredientSourcingService(async_db)

    with pytest.raises(ValueError, match="introuvable"):
        await service.resolve(ingr.id, Decimal("5"), _TENANT_RESTO_OTHER)


@pytest.mark.asyncio
async def test_ordre_respecte(async_db: AsyncSession):
    """Le produit d'ordre 0 est consommé avant ordre 1, même si ordre 1 a plus de stock."""
    ingr = await _mk_ingredient(async_db)
    # n°1 : petit stock mais préféré
    p1 = await _mk_produit_avec_stock(async_db, "Préféré", "U", Decimal("1"))
    # n°2 : gros stock mais fallback
    p2 = await _mk_produit_avec_stock(async_db, "Fallback", "U", Decimal("100"))
    await _mk_mapping(async_db, ingr.id, p1.id, ordre=0, facteur_conv=Decimal("1"))
    await _mk_mapping(async_db, ingr.id, p2.id, ordre=1, facteur_conv=Decimal("1"))

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("3"), _TENANT_RESTO)

    assert res.couverture_complete is True
    # Préféré d'abord (totalité 1), puis fallback (2)
    assert res.items[0].produit_id == p1.id
    assert res.items[0].qte_couverte_besoin == Decimal("1")
    assert res.items[1].produit_id == p2.id
    assert res.items[1].qte_couverte_besoin == Decimal("2")


@pytest.mark.asyncio
async def test_besoin_exact_stock_pas_de_fallback(async_db: AsyncSession):
    """Besoin = stock du premier produit → 2e mapping non consulté."""
    ingr = await _mk_ingredient(async_db)
    p1 = await _mk_produit_avec_stock(async_db, "A", "U", Decimal("5"))
    p2 = await _mk_produit_avec_stock(async_db, "B", "U", Decimal("5"))
    await _mk_mapping(async_db, ingr.id, p1.id, ordre=0, facteur_conv=Decimal("1"))
    await _mk_mapping(async_db, ingr.id, p2.id, ordre=1, facteur_conv=Decimal("1"))

    service = IngredientSourcingService(async_db)
    res = await service.resolve(ingr.id, Decimal("5"), _TENANT_RESTO)

    assert res.couverture_complete is True
    assert len(res.items) == 1  # seul le premier produit consommé
    assert res.items[0].produit_id == p1.id
