"""Tests unitaires pour BundleService."""
import pytest
from fastapi import HTTPException
from app.models.bundle import ProductBundle, BundleItem
from app.models.product import Product
from app.services.bundle import BundleService
from app.constants import ErrorMessages


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_bundle(db, tenant_id=1, name="Pack Test", slug=None, bundle_price=50000,
                 cleaning_fee=0, featured=False, display_order=0):
    """Cree un bundle de test."""
    from app.utils.slug import slugify
    bundle = ProductBundle(
        tenant_id=tenant_id,
        name=name,
        slug=slug or slugify(name),
        bundle_price=bundle_price,
        cleaning_fee=cleaning_fee,
        featured=featured,
        display_order=display_order,
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle


def _make_product(db, tenant_id=1, name="Produit Test", sku="PRD-001",
                  category="assiettes", price_per_day=250):
    """Cree un produit de test."""
    prod = Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        category=category,
        price_per_day=price_per_day,
        deposit_amount=0,
        stock_quantity=10,
        available_quantity=10,
        condition="bon",
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


def _make_bundle_item(db, bundle_id, product_id, tenant_id=1, quantity=1, display_order=0):
    """Cree un item de bundle."""
    item = BundleItem(
        tenant_id=tenant_id,
        bundle_id=bundle_id,
        product_id=product_id,
        quantity=quantity,
        display_order=display_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ─────────────────────────────────────────────────────────────────────
# Create bundle
# ─────────────────────────────────────────────────────────────────────

class TestCreateBundle:
    """Tests pour BundleService.create_bundle."""

    def test_create_with_auto_slug(self, test_db):
        service = BundleService(test_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack Mariage", bundle_price_cents=50000)
        bundle = service.create_bundle(data, tenant_id=1)
        test_db.commit()
        assert bundle.name == "Pack Mariage"
        assert bundle.slug == "pack_mariage"
        assert bundle.bundle_price == 50000
        assert bundle.tenant_id == 1

    def test_create_with_explicit_slug(self, test_db):
        service = BundleService(test_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack Noel", slug="noel_2026", bundle_price_cents=75000)
        bundle = service.create_bundle(data, tenant_id=1)
        test_db.commit()
        assert bundle.slug == "noel_2026"

    def test_create_slug_duplicate_raises(self, test_db):
        _make_bundle(test_db, name="Pack A", slug="pack_a")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack A Bis", slug="pack_a", bundle_price_cents=30000)
        with pytest.raises(HTTPException) as exc_info:
            service.create_bundle(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_SLUG_EXISTS in exc_info.value.detail

    def test_create_name_duplicate_raises(self, test_db):
        _make_bundle(test_db, name="Pack Unique", slug="different_slug")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleCreate
        data = BundleCreate(name="Pack Unique", slug="another_slug", bundle_price_cents=30000)
        with pytest.raises(HTTPException) as exc_info:
            service.create_bundle(data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_NAME_EXISTS in exc_info.value.detail

    def test_create_with_all_fields(self, test_db):
        service = BundleService(test_db)
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
        bundle = service.create_bundle(data, tenant_id=1)
        test_db.commit()
        assert bundle.description == "Le pack complet"
        assert bundle.short_description == "Tout inclus"
        assert bundle.cleaning_fee == 5000
        assert bundle.featured is True
        assert bundle.display_order == 1
        assert bundle.image_url == "https://cdn.example.com/pack.jpg"


# ─────────────────────────────────────────────────────────────────────
# Update bundle
# ─────────────────────────────────────────────────────────────────────

class TestUpdateBundle:
    """Tests pour BundleService.update_bundle."""

    def test_update_name(self, test_db):
        bundle = _make_bundle(test_db, name="Old Pack")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(name="New Pack")
        updated = service.update_bundle(bundle.id, data, tenant_id=1)
        test_db.commit()
        assert updated.name == "New Pack"

    def test_update_price(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Prix", bundle_price=50000)
        service = BundleService(test_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(bundle_price_cents=75000)
        updated = service.update_bundle(bundle.id, data, tenant_id=1)
        test_db.commit()
        assert updated.bundle_price == 75000

    def test_update_slug_unique_violation_raises(self, test_db):
        _make_bundle(test_db, name="Pack A", slug="pack_a")
        bundle_b = _make_bundle(test_db, name="Pack B", slug="pack_b")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(slug="pack_a")
        with pytest.raises(HTTPException) as exc_info:
            service.update_bundle(bundle_b.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_SLUG_EXISTS in exc_info.value.detail

    def test_update_not_found_raises(self, test_db):
        service = BundleService(test_db)
        from app.schemas.bundle import BundleUpdate
        data = BundleUpdate(name="Ghost")
        with pytest.raises(HTTPException) as exc_info:
            service.update_bundle(99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Delete bundle
# ─────────────────────────────────────────────────────────────────────

class TestDeleteBundle:
    """Tests pour BundleService.delete_bundle."""

    def test_delete_soft_delete(self, test_db):
        bundle = _make_bundle(test_db, name="To Delete")
        service = BundleService(test_db)
        result = service.delete_bundle(bundle.id, tenant_id=1)
        test_db.commit()
        assert result is True

    def test_delete_not_found_raises(self, test_db):
        service = BundleService(test_db)
        with pytest.raises(HTTPException) as exc_info:
            service.delete_bundle(99999, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Add item
# ─────────────────────────────────────────────────────────────────────

class TestAddItem:
    """Tests pour BundleService.add_item."""

    def test_add_item_ok(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Items")
        product = _make_product(test_db, name="Assiette", sku="ASS-001")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=10)
        item = service.add_item(bundle.id, data, tenant_id=1)
        test_db.commit()
        assert item.bundle_id == bundle.id
        assert item.product_id == product.id
        assert item.quantity == 10

    def test_add_item_product_not_found_raises(self, test_db):
        bundle = _make_bundle(test_db, name="Pack NoProduct")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=99999, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_PRODUCT_NOT_FOUND in exc_info.value.detail

    def test_add_item_duplicate_raises(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Dup")
        product = _make_product(test_db, name="Verre Dup", sku="V-DUP")
        _make_bundle_item(test_db, bundle.id, product.id)
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_DUPLICATE in exc_info.value.detail

    def test_add_item_cross_tenant_product_raises(self, test_db):
        bundle = _make_bundle(test_db, tenant_id=1, name="Pack T1")
        product = _make_product(test_db, tenant_id=2, name="Prod T2", sku="T2-001")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            service.add_item(bundle.id, data, tenant_id=1)
        assert exc_info.value.status_code == 400
        assert ErrorMessages.BUNDLE_ITEM_PRODUCT_NOT_FOUND in exc_info.value.detail

    def test_add_item_bundle_not_found_raises(self, test_db):
        product = _make_product(test_db, name="Orphan Prod", sku="ORP-001")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemCreate
        data = BundleItemCreate(product_id=product.id, quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            service.add_item(99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Update item
# ─────────────────────────────────────────────────────────────────────

class TestUpdateItem:
    """Tests pour BundleService.update_item."""

    def test_update_quantity(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Qty")
        product = _make_product(test_db, name="Prod Qty", sku="QTY-001")
        item = _make_bundle_item(test_db, bundle.id, product.id, quantity=5)
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemUpdate
        data = BundleItemUpdate(quantity=20)
        updated = service.update_item(bundle.id, item.id, data, tenant_id=1)
        test_db.commit()
        assert updated.quantity == 20

    def test_update_item_not_found_raises(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Ghost Item")
        service = BundleService(test_db)
        from app.schemas.bundle import BundleItemUpdate
        data = BundleItemUpdate(quantity=1)
        with pytest.raises(HTTPException) as exc_info:
            service.update_item(bundle.id, 99999, data, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Remove item
# ─────────────────────────────────────────────────────────────────────

class TestRemoveItem:
    """Tests pour BundleService.remove_item."""

    def test_remove_item_ok(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Remove")
        product = _make_product(test_db, name="Prod Remove", sku="REM-001")
        item = _make_bundle_item(test_db, bundle.id, product.id)
        service = BundleService(test_db)
        result = service.remove_item(bundle.id, item.id, tenant_id=1)
        test_db.commit()
        assert result is True

    def test_remove_item_not_found_raises(self, test_db):
        bundle = _make_bundle(test_db, name="Pack NoRemove")
        service = BundleService(test_db)
        with pytest.raises(HTTPException) as exc_info:
            service.remove_item(bundle.id, 99999, tenant_id=1)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# Calculate price
# ─────────────────────────────────────────────────────────────────────

class TestCalculatePrice:
    """Tests pour BundleService.calculate_price."""

    def test_calculate_correct(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Calc", bundle_price=40000)
        prod1 = _make_product(test_db, name="Prod 1", sku="P1", price_per_day=250)
        prod2 = _make_product(test_db, name="Prod 2", sku="P2", price_per_day=300)
        _make_bundle_item(test_db, bundle.id, prod1.id, quantity=10)
        _make_bundle_item(test_db, bundle.id, prod2.id, quantity=5)

        service = BundleService(test_db)
        result = service.calculate_price(bundle.id, tenant_id=1)
        # individual = 250*10 + 300*5 = 2500 + 1500 = 4000
        assert result["individual_price_cents"] == 4000
        assert result["bundle_price_cents"] == 40000
        assert result["savings_cents"] == 4000 - 40000  # -36000 (bundle plus cher)
        assert len(result["items"]) == 2

    def test_calculate_empty_bundle(self, test_db):
        bundle = _make_bundle(test_db, name="Pack Empty", bundle_price=10000)
        service = BundleService(test_db)
        result = service.calculate_price(bundle.id, tenant_id=1)
        assert result["individual_price_cents"] == 0
        assert result["savings_cents"] == -10000
        assert result["savings_percent"] == 0.0

    def test_calculate_not_found_raises(self, test_db):
        service = BundleService(test_db)
        with pytest.raises(HTTPException) as exc_info:
            service.calculate_price(99999, tenant_id=1)
        assert exc_info.value.status_code == 404
