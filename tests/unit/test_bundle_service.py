"""Tests unitaires pour BundleService."""
import pytest
from fastapi import HTTPException
from app.models.bundle import ProductBundle, BundleItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.services.bundle import BundleService
from app.constants import ErrorMessages


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

async def _make_bundle(db, tenant_id=1, name="Pack Test", slug=None, bundle_price_cents=50000,
                       cleaning_fee_cents=0, featured=False, display_order=0):
    """Cree un bundle de test."""
    from app.utils.slug import slugify
    bundle = ProductBundle(
        tenant_id=tenant_id,
        name=name,
        slug=slug or slugify(name),
        bundle_price_cents=bundle_price_cents,
        cleaning_fee_cents=cleaning_fee_cents,
        featured=featured,
        display_order=display_order,
    )
    db.add(bundle)
    await db.flush()
    await db.refresh(bundle)
    return bundle


async def _make_product(db, tenant_id=1, name="Produit Test", sku="PRD-001",
                        category="assiettes", price_per_day_cents=250):
    """Cree un produit de test."""
    prod = Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        category=category,
        price_per_day_cents=price_per_day_cents,
        deposit_amount_cents=0,
        stock_quantity=10,
        available_quantity=10,
        condition="bon",
    )
    db.add(prod)
    await db.flush()
    await db.refresh(prod)
    return prod


async def _make_variant(db, product_id, tenant_id=1, label="Standard",
                        stock_quantity=10, available_quantity=10):
    """Cree une variante de test."""
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


async def _make_bundle_item(db, bundle_id, product_id, tenant_id=1, quantity=1,
                            display_order=0):
    """Cree un item de bundle."""
    item = BundleItem(
        tenant_id=tenant_id,
        bundle_id=bundle_id,
        product_id=product_id,
        quantity=quantity,
        display_order=display_order,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


# ─────────────────────────────────────────────────────────────────────
# Create bundle
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreateBundle:
    """Tests pour BundleService.create_bundle."""

    async def test_create_with_auto_slug(self, async_db):
        service = BundleService(async_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack Mariage", bundle_price_cents=50000)
        bundle = await service.create_bundle(data, tenant_id=1)
        await async_db.commit()
        assert bundle.name == "Pack Mariage"
        assert bundle.slug == "pack_mariage"
        assert bundle.bundle_price_cents == 50000
        assert bundle.tenant_id == 1

    async def test_create_with_explicit_slug(self, async_db):
        service = BundleService(async_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack Noel", slug="noel_2026", bundle_price_cents=75000)
        bundle = await service.create_bundle(data, tenant_id=1)
        await async_db.commit()
        assert bundle.slug == "noel_2026"

    async def test_create_slug_duplicate_raises(self, async_db):
        await _make_bundle(async_db, name="Pack A", slug="pack_a")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack A Bis", slug="pack_a", bundle_price_cents=30000)
        with pytest.raises(HTTPException) as exc_info:
            await service.create_bundle(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_SLUG_EXISTS in exc_info.value.detail

    async def test_create_name_duplicate_raises(self, async_db):
        await _make_bundle(async_db, name="Pack Unique", slug="different_slug")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack Unique", slug="another_slug",
                            bundle_price_cents=30000)
        with pytest.raises(HTTPException) as exc_info:
            await service.create_bundle(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_NAME_EXISTS in exc_info.value.detail

    async def test_create_with_all_fields(self, async_db):
        service = BundleService(async_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(
            name="Pack Premium",
            description="Le pack complet",
            short_description="Tout inclus",
            bundle_price_cents=100000,
            cleaning_fee_cents=5000,
            featured=True,
            display_order=1,
            image_url="https://cdn.example.com/pack.jpg",
        )
        bundle = await service.create_bundle(data, tenant_id=1)
        await async_db.commit()
        assert bundle.description == "Le pack complet"
        assert bundle.short_description == "Tout inclus"
        assert bundle.cleaning_fee_cents == 5000
        assert bundle.featured is True
        assert bundle.display_order == 1
        assert bundle.image_url == "https://cdn.example.com/pack.jpg"


# ─────────────────────────────────────────────────────────────────────
# Update bundle
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpdateBundle:
    """Tests pour BundleService.update_bundle."""

    async def test_update_name(self, async_db):
        bundle = await _make_bundle(async_db, name="Old Pack")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(name="New Pack")
        updated = await service.update_bundle(bundle.id, data, tenant_id=1)
        await async_db.commit()
        assert updated.name == "New Pack"

    async def test_update_price(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Prix", bundle_price_cents=50000)
        service = BundleService(async_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(bundle_price_cents=75000)
        updated = await service.update_bundle(bundle.id, data, tenant_id=1)
        await async_db.commit()
        assert updated.bundle_price_cents == 75000

    async def test_update_slug_unique_violation_raises(self, async_db):
        await _make_bundle(async_db, name="Pack A", slug="pack_a")
        bundle_b = await _make_bundle(async_db, name="Pack B", slug="pack_b")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(slug="pack_a")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_bundle(bundle_b.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_SLUG_EXISTS in exc_info.value.detail

    async def test_update_not_found_raises(self, async_db):
        service = BundleService(async_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(name="Ghost")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_bundle(99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Delete bundle
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeleteBundle:
    """Tests pour BundleService.delete_bundle."""

    async def test_delete_soft_delete(self, async_db):
        bundle = await _make_bundle(async_db, name="To Delete")
        service = BundleService(async_db)
        result = await service.delete_bundle(bundle.id, tenant_id=1)
        await async_db.commit()
        assert result is True

    async def test_delete_not_found_raises(self, async_db):
        service = BundleService(async_db)
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_bundle(99999, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Add item
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestAddItem:
    """Tests pour BundleService.add_item."""

    async def test_add_item_ok(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Items")
        product = await _make_product(async_db, name="Assiette", sku="ASS-001")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=10)
        item = await service.add_item(bundle.id, data, tenant_id=1)
        await async_db.commit()
        assert item.bundle_id == bundle.id
        assert item.product_id == product.id
        assert item.quantity == 10

    async def test_add_item_product_not_found_raises(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack NoProduct")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=99999, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_PRODUCT_NOT_FOUND in exc_info.value.detail

    async def test_add_item_duplicate_raises(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Dup")
        product = await _make_product(async_db, name="Verre Dup", sku="V-DUP")
        await _make_bundle_item(async_db, bundle.id, product.id)
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_DUPLICATE in exc_info.value.detail

    async def test_add_item_cross_tenant_product_raises(self, async_db):
        bundle = await _make_bundle(async_db, tenant_id=1, name="Pack T1")
        product = await _make_product(async_db, tenant_id=2, name="Prod T2", sku="T2-001")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_PRODUCT_NOT_FOUND in exc_info.value.detail

    async def test_add_item_bundle_not_found_raises(self, async_db):
        product = await _make_product(async_db, name="Orphan Prod", sku="ORP-001")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404

    async def test_add_item_variant_required_when_product_has_variants(self, async_db):
        """add_item → 422 si produit a des variantes actives et variant_id=None."""
        bundle = await _make_bundle(async_db, name="Pack VariantRequired")
        product = await _make_product(async_db, name="Prod Varianté", sku="VAR-REQ-001")
        await _make_variant(async_db, product.id, label="Standard")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 422
        assert ErrorMessages.BUNDLE_ITEM_VARIANT_REQUIRED in exc_info.value.detail

    async def test_add_item_with_valid_variant_id_ok(self, async_db):
        """add_item avec variant_id valide (appartenant au produit) → 201."""
        bundle = await _make_bundle(async_db, name="Pack WithVariant")
        product = await _make_product(async_db, name="Prod Var OK", sku="VAR-OK-001")
        variant = await _make_variant(async_db, product.id, label="Standard")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, variant_id=variant.id, quantity=2)
        item = await service.add_item(bundle.id, data, tenant_id=1)
        await async_db.commit()
        assert item.product_id == product.id
        assert item.variant_id == variant.id

    async def test_add_item_variant_mismatch_raises(self, async_db):
        """add_item → 400 si variant_id n'appartient pas au product_id."""
        bundle = await _make_bundle(async_db, name="Pack Mismatch")
        product_a = await _make_product(async_db, name="Prod A", sku="MISM-A-001")
        product_b = await _make_product(async_db, name="Prod B", sku="MISM-B-001")
        variant_b = await _make_variant(async_db, product_b.id, label="Standard")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemCreate
        # variant_b appartient à product_b, pas product_a
        data = BundleItemCreate(product_id=product_a.id, variant_id=variant_b.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_VARIANT_MISMATCH in exc_info.value.detail


# ─────────────────────────────────────────────────────────────────────
# Update item
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpdateItem:
    """Tests pour BundleService.update_item."""

    async def test_update_quantity(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Qty")
        product = await _make_product(async_db, name="Prod Qty", sku="QTY-001")
        item = await _make_bundle_item(async_db, bundle.id, product.id, quantity=5)
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemUpdate
        data = BundleItemUpdate(quantity=20)
        updated = await service.update_item(bundle.id, item.id, data, tenant_id=1)
        await async_db.commit()
        assert updated.quantity == 20

    async def test_update_item_not_found_raises(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Ghost Item")
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemUpdate
        data = BundleItemUpdate(quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            await service.update_item(bundle.id, 99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404

    async def test_update_item_variant_mismatch_raises(self, async_db):
        """update_item → 400 si le nouveau variant_id n'appartient pas au produit de l'item."""
        bundle = await _make_bundle(async_db, name="Pack UpdMismatch")
        product_a = await _make_product(async_db, name="Prod Upd A", sku="UPD-A-001")
        product_b = await _make_product(async_db, name="Prod Upd B", sku="UPD-B-001")
        variant_b = await _make_variant(async_db, product_b.id, label="Upd Standard")
        item = await _make_bundle_item(async_db, bundle.id, product_a.id)
        service = BundleService(async_db)
        from app.schemas.bundle import BundleItemUpdate
        data = BundleItemUpdate(variant_id=variant_b.id)
        with pytest.raises(HTTPException) as exc_info:
            await service.update_item(bundle.id, item.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_VARIANT_MISMATCH in exc_info.value.detail


# ─────────────────────────────────────────────────────────────────────
# Remove item
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRemoveItem:
    """Tests pour BundleService.remove_item."""

    async def test_remove_item_ok(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Remove")
        product = await _make_product(async_db, name="Prod Remove", sku="REM-001")
        item = await _make_bundle_item(async_db, bundle.id, product.id)
        service = BundleService(async_db)
        result = await service.remove_item(bundle.id, item.id, tenant_id=1)
        await async_db.commit()
        assert result is True

    async def test_remove_item_not_found_raises(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack NoRemove")
        service = BundleService(async_db)
        with pytest.raises(HTTPException) as exc_info:
            await service.remove_item(bundle.id, 99999, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Calculate price
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCalculatePrice:
    """Tests pour BundleService.calculate_price."""

    async def test_calculate_correct(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Calc", bundle_price_cents=40000)
        prod1 = await _make_product(async_db, name="Prod 1", sku="P1",
                                    price_per_day_cents=250)
        prod2 = await _make_product(async_db, name="Prod 2", sku="P2",
                                    price_per_day_cents=300)
        await _make_bundle_item(async_db, bundle.id, prod1.id, quantity=10)
        await _make_bundle_item(async_db, bundle.id, prod2.id, quantity=5)

        service = BundleService(async_db)
        result = await service.calculate_price(bundle.id, tenant_id=1)
        # individual = 250*10 + 300*5 = 2500 + 1500 = 4000
        assert result["individual_price_cents"] == 4000
        assert result["bundle_price_cents"] == 40000
        assert result["savings_cents"] == 4000 - 40000  # -36000 (bundle plus cher)
        assert len(result["items"]) == 2

    async def test_calculate_empty_bundle(self, async_db):
        bundle = await _make_bundle(async_db, name="Pack Empty", bundle_price_cents=10000)
        service = BundleService(async_db)
        result = await service.calculate_price(bundle.id, tenant_id=1)
        assert result["individual_price_cents"] == 0
        assert result["savings_cents"] == -10000
        assert result["savings_percent"] == 0.0

    async def test_calculate_not_found_raises(self, async_db):
        service = BundleService(async_db)
        with pytest.raises(HTTPException) as exc_info:
            await service.calculate_price(99999, tenant_id=1)
        assert exc_info.value.status_code == 404
