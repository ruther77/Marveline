"""Tests unitaires pour StockItemService et StockItemRepository."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.stock_item import StockItem
from app.services.stock_item import StockItemService, VALID_TRANSITIONS


TENANT_ID = 1
TENANT_OTHER = 2


# ── Helpers ────────────────────────────────────────────────────────────


async def _make_product(db, tenant_id=TENANT_ID, name="Assiette Test", sku="ASS-TEST-001",
                        stock_quantity=10, available_quantity=10):
    """Crée un produit de test en DB."""
    prod = Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        category="assiettes",
        price_per_day_cents=250,
        deposit_amount_cents=0,
        stock_quantity=stock_quantity,
        available_quantity=available_quantity,
        condition="bon",
    )
    db.add(prod)
    await db.flush()
    await db.refresh(prod)
    return prod


async def _make_variant(db, product_id, tenant_id=TENANT_ID, label="Standard",
                        stock_quantity=10, available_quantity=10):
    """Crée une variante de test en DB."""
    variant = ProductVariant(
        tenant_id=tenant_id,
        product_id=product_id,
        label=label,
        sku=f"VAR-{product_id}-{label[:3].upper()}",
        price_per_day_cents=250,
        stock_quantity=stock_quantity,
        available_quantity=available_quantity,
        deposit_amount_cents=0,
    )
    db.add(variant)
    await db.flush()
    await db.refresh(variant)
    return variant


async def _make_stock_item(db, product_id, tenant_id=TENANT_ID, status="available",
                           serial_number=None, reservation_id=None, variant_id=None):
    """Crée un StockItem en DB avec le statut donné."""
    item = StockItem(
        tenant_id=tenant_id,
        product_id=product_id,
        variant_id=variant_id,
        status=status,
        serial_number=serial_number,
        current_reservation_id=reservation_id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
async def service(async_db):
    """StockItemService avec session de test."""
    return StockItemService(async_db)


@pytest.fixture
async def product(async_db):
    """Produit de test avec variante Standard et 5 unités disponibles."""
    prod = await _make_product(async_db, stock_quantity=5, available_quantity=5)
    variant = await _make_variant(async_db, prod.id, stock_quantity=5, available_quantity=5)
    for _ in range(5):
        await _make_stock_item(async_db, prod.id, status="available", variant_id=variant.id)
    return prod


# ══════════════════════════════════════════════════════════════════════
# Tests reserve_n
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reserve_n_happy_path(service, async_db, product):
    """reserve_n passe N items available → reserved."""
    items = await service.reserve_n(product.id, 3, TENANT_ID)

    assert len(items) == 3
    for item in items:
        assert item.status == "reserved"


@pytest.mark.asyncio
async def test_reserve_n_variant_id_filters_items(service, async_db):
    """reserve_n avec variant_id ne réserve que les items de cette variante."""
    prod = await _make_product(async_db, sku="VAR-FILTER-001", stock_quantity=4,
                               available_quantity=4)
    v1 = await _make_variant(async_db, prod.id, label="Rouge", stock_quantity=2,
                              available_quantity=2)
    v2 = await _make_variant(async_db, prod.id, label="Bleu", stock_quantity=2,
                              available_quantity=2)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v1.id)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v1.id)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v2.id)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v2.id)

    reserved = await service.reserve_n(prod.id, 2, TENANT_ID, variant_id=v1.id)

    assert len(reserved) == 2
    assert all(item.variant_id == v1.id for item in reserved)
    # Les items de v2 restent disponibles
    result = await async_db.execute(
        select(StockItem).where(
            StockItem.product_id == prod.id,
            StockItem.variant_id == v2.id,
        )
    )
    v2_items = result.scalars().all()
    assert all(i.status == "available" for i in v2_items)


@pytest.mark.asyncio
async def test_reserve_n_without_reservation_id(service, async_db, product):
    """reserve_n sans reservation_id laisse current_reservation_id à None."""
    items = await service.reserve_n(product.id, 2, TENANT_ID)

    for item in items:
        assert item.current_reservation_id is None


@pytest.mark.asyncio
async def test_reserve_n_insufficient_stock_raises(service, async_db, product):
    """reserve_n lève 400 si stock insuffisant."""
    with pytest.raises(HTTPException) as exc_info:
        await service.reserve_n(product.id, 10, TENANT_ID)  # seulement 5 disponibles

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_reserve_n_cross_tenant_isolation(service, async_db, product):
    """reserve_n ne touche pas les items d'un autre tenant."""
    # Créer un produit identique pour tenant TENANT_OTHER
    prod_other = await _make_product(async_db, tenant_id=TENANT_OTHER, sku="ASS-TEST-002")
    for _ in range(3):
        await _make_stock_item(async_db, prod_other.id, tenant_id=TENANT_OTHER,
                               status="available")

    # Réserver avec le bon tenant
    items = await service.reserve_n(product.id, 3, TENANT_ID)
    assert all(item.tenant_id == TENANT_ID for item in items)

    # Les items de l'autre tenant ne sont pas touchés
    result = await async_db.execute(
        select(StockItem).where(
            StockItem.product_id == prod_other.id,
            StockItem.tenant_id == TENANT_OTHER,
        )
    )
    other_items = result.scalars().all()
    assert all(i.status == "available" for i in other_items)


# ══════════════════════════════════════════════════════════════════════
# Tests release_n
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_release_n_happy_path(service, async_db, product):
    """release_n passe N items reserved → available."""
    # D'abord réserver 3
    await service.reserve_n(product.id, 3, TENANT_ID)
    # Puis libérer 2
    items = await service.release_n(product.id, 2, TENANT_ID)

    assert len(items) == 2
    for item in items:
        assert item.status == "available"


@pytest.mark.asyncio
async def test_release_n_insufficient_reserved_raises(service, async_db, product):
    """release_n lève 400 si pas assez d'items réservés."""
    with pytest.raises(HTTPException) as exc_info:
        await service.release_n(product.id, 5, TENANT_ID)  # 0 réservés

    assert exc_info.value.status_code == 400


# ══════════════════════════════════════════════════════════════════════
# Tests transition_n
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_transition_n_reserved_to_on_location(service, async_db, product):
    """transition_n passe reserved → on_location."""
    await service.reserve_n(product.id, 3, TENANT_ID)
    items = await service.transition_n(product.id, 3, "reserved", "on_location", TENANT_ID)

    assert len(items) == 3
    for item in items:
        assert item.status == "on_location"


@pytest.mark.asyncio
async def test_transition_n_on_location_to_available(service, async_db, product):
    """transition_n passe on_location → available (retour OK)."""
    await service.reserve_n(product.id, 2, TENANT_ID)
    await service.transition_n(product.id, 2, "reserved", "on_location", TENANT_ID)
    items = await service.transition_n(product.id, 2, "on_location", "available", TENANT_ID)

    assert len(items) == 2
    for item in items:
        assert item.status == "available"


@pytest.mark.asyncio
async def test_transition_n_on_location_to_damaged(service, async_db, product):
    """transition_n passe on_location → damaged (retour cassé)."""
    await service.reserve_n(product.id, 1, TENANT_ID)
    await service.transition_n(product.id, 1, "reserved", "on_location", TENANT_ID)
    items = await service.transition_n(product.id, 1, "on_location", "damaged", TENANT_ID)

    assert items[0].status == "damaged"


@pytest.mark.asyncio
async def test_transition_n_invalid_raises(service, async_db, product):
    """transition_n lève 400 pour une transition invalide."""
    with pytest.raises(HTTPException) as exc_info:
        await service.transition_n(product.id, 1, "available", "on_location", TENANT_ID)

    assert exc_info.value.status_code == 400
    # Le service lève HTTP 400 pour toute transition invalide (VALID_TRANSITIONS)


@pytest.mark.asyncio
async def test_transition_n_insufficient_raises(service, async_db, product):
    """transition_n lève 400 si pas assez d'items dans from_status."""
    with pytest.raises(HTTPException) as exc_info:
        await service.transition_n(product.id, 10, "reserved", "on_location", TENANT_ID)

    assert exc_info.value.status_code == 400


# ══════════════════════════════════════════════════════════════════════
# Tests transition_status (item individuel)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_transition_status_individual_item(service, async_db, product):
    """transition_status passe un item individuel vers un nouveau statut."""
    item = await _make_stock_item(async_db, product.id, status="available")
    result = await service.transition_status(item.id, "retired", TENANT_ID)

    assert result.status == "retired"


@pytest.mark.asyncio
async def test_transition_status_wrong_tenant_raises(service, async_db, product):
    """transition_status lève 400 si item appartient à un autre tenant."""
    item = await _make_stock_item(async_db, product.id, tenant_id=TENANT_OTHER,
                                  status="available")

    with pytest.raises(HTTPException) as exc_info:
        await service.transition_status(item.id, "retired", TENANT_ID)

    assert exc_info.value.status_code == 400


# ══════════════════════════════════════════════════════════════════════
# Tests get_counts
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_get_counts_returns_all_statuses(service, async_db):
    """get_counts retourne tous les statuts avec valeur 0 par défaut."""
    prod = await _make_product(async_db, sku="CNT-001", stock_quantity=0,
                               available_quantity=0)
    counts = await service.get_counts(prod.id, TENANT_ID)

    expected_keys = {"available", "reserved", "on_location", "damaged", "in_repair",
                     "retired"}
    assert set(counts.keys()) == expected_keys
    assert all(v == 0 for v in counts.values())


@pytest.mark.asyncio
async def test_get_counts_accurate(service, async_db):
    """get_counts compte correctement par statut."""
    prod = await _make_product(async_db, sku="CNT-002", stock_quantity=6,
                               available_quantity=3)
    await _make_stock_item(async_db, prod.id, status="available")
    await _make_stock_item(async_db, prod.id, status="available")
    await _make_stock_item(async_db, prod.id, status="available")
    await _make_stock_item(async_db, prod.id, status="reserved")
    await _make_stock_item(async_db, prod.id, status="on_location")
    await _make_stock_item(async_db, prod.id, status="damaged")

    counts = await service.get_counts(prod.id, TENANT_ID)

    assert counts["available"] == 3
    assert counts["reserved"] == 1
    assert counts["on_location"] == 1
    assert counts["damaged"] == 1



# ══════════════════════════════════════════════════════════════════════
# Tests VALID_TRANSITIONS (constante)
# ══════════════════════════════════════════════════════════════════════


def test_valid_transitions_exhaustive():
    """Vérifie que toutes les transitions définies sont cohérentes."""
    all_statuses = {"available", "reserved", "on_location", "damaged", "in_repair",
                    "retired"}

    for from_status, to_statuses in VALID_TRANSITIONS.items():
        assert from_status in all_statuses, f"Statut source inconnu : {from_status}"
        for to_status in to_statuses:
            assert to_status in all_statuses, f"Statut destination inconnu : {to_status}"

    # retired ne peut aller nulle part
    assert VALID_TRANSITIONS["retired"] == []


def test_valid_transitions_retired_is_terminal():
    """retired est un statut terminal (aucune transition sortante)."""
    assert not VALID_TRANSITIONS.get("retired")


# ══════════════════════════════════════════════════════════════════════
# Tests variant_id filtering
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_release_n_variant_id_filters_items(service, async_db):
    """release_n avec variant_id ne libère que les items de cette variante."""
    prod = await _make_product(async_db, sku="REL-FILTER-001", stock_quantity=4,
                               available_quantity=2)
    v1 = await _make_variant(async_db, prod.id, label="Rouge", stock_quantity=2,
                              available_quantity=0)
    v2 = await _make_variant(async_db, prod.id, label="Bleu", stock_quantity=2,
                              available_quantity=0)
    item_v1a = await _make_stock_item(async_db, prod.id, status="reserved", variant_id=v1.id)
    item_v1b = await _make_stock_item(async_db, prod.id, status="reserved", variant_id=v1.id)
    await _make_stock_item(async_db, prod.id, status="reserved", variant_id=v2.id)
    await _make_stock_item(async_db, prod.id, status="reserved", variant_id=v2.id)

    released = await service.release_n(prod.id, 2, TENANT_ID, variant_id=v1.id)

    assert len(released) == 2
    assert all(item.variant_id == v1.id for item in released)
    released_ids = {item.id for item in released}
    assert item_v1a.id in released_ids
    assert item_v1b.id in released_ids

    # Les items de v2 restent reserved
    result = await async_db.execute(
        select(StockItem).where(
            StockItem.product_id == prod.id,
            StockItem.variant_id == v2.id,
        )
    )
    v2_items = result.scalars().all()
    assert all(i.status == "reserved" for i in v2_items)


@pytest.mark.asyncio
async def test_reserve_n_no_variant_id_takes_any(service, async_db):
    """reserve_n sans variant_id prend les N premiers items disponibles toutes variantes."""
    prod = await _make_product(async_db, sku="NO-VAR-001", stock_quantity=4,
                               available_quantity=4)
    v1 = await _make_variant(async_db, prod.id, label="A", stock_quantity=2,
                              available_quantity=2)
    v2 = await _make_variant(async_db, prod.id, label="B", stock_quantity=2,
                              available_quantity=2)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v1.id)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v1.id)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v2.id)
    await _make_stock_item(async_db, prod.id, status="available", variant_id=v2.id)

    reserved = await service.reserve_n(prod.id, 3, TENANT_ID)

    assert len(reserved) == 3
    assert all(item.status == "reserved" for item in reserved)
