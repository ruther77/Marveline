"""Tests d'integration pour les endpoints bundles."""
import pytest
from fastapi.testclient import TestClient

from app.models.bundle import ProductBundle, BundleItem
from app.models.product import Product
from app.utils.slug import slugify


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _create_bundle(db, tenant_id=1, name="Pack Test", slug=None,
                   bundle_price=50000, cleaning_fee=0, featured=False, display_order=0):
    """Cree un bundle dans la DB de test."""
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


def _create_product(db, tenant_id=1, name="Produit", sku="PRD-001",
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


def _create_bundle_item(db, bundle_id, product_id, tenant_id=1, quantity=1, display_order=0):
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
# GET /bundles — Liste
# ─────────────────────────────────────────────────────────────────────

class TestListBundles:
    """Tests pour GET /api/v1/bundles."""

    def test_list_empty(self, client: TestClient, auth_headers_real):
        """Liste vide quand aucun bundle."""
        resp = client.get("/api/v1/bundles", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_returns_bundles(self, client: TestClient, auth_headers_real, test_db):
        """Liste retourne les bundles du tenant."""
        _create_bundle(test_db, name="Pack A", bundle_price=30000)
        _create_bundle(test_db, name="Pack B", bundle_price=50000)

        resp = client.get("/api/v1/bundles", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_list_featured_filter(self, client: TestClient, auth_headers_real, test_db):
        """Filtre featured=true."""
        _create_bundle(test_db, name="Normal Pack", featured=False)
        _create_bundle(test_db, name="Featured Pack", featured=True)

        resp = client.get("/api/v1/bundles?featured=true", headers=auth_headers_real)
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Featured Pack"

    def test_list_requires_auth(self, client: TestClient):
        """Liste sans token → 401."""
        resp = client.get("/api/v1/bundles")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# GET /bundles/{id}
# ─────────────────────────────────────────────────────────────────────

class TestGetBundle:
    """Tests pour GET /api/v1/bundles/{id}."""

    def test_get_with_items(self, client: TestClient, auth_headers_real, test_db):
        """Retourne bundle avec ses items et produits."""
        bundle = _create_bundle(test_db, name="Pack Detail", bundle_price=40000)
        product = _create_product(test_db, name="Assiette", sku="ASS-001", price_per_day=250)
        _create_bundle_item(test_db, bundle.id, product.id, quantity=10)

        resp = client.get(f"/api/v1/bundles/{bundle.id}", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Pack Detail"
        assert data["bundle_price_cents"] == 40000
        assert len(data["items"]) == 1
        assert data["items"][0]["quantity"] == 10
        assert data["items"][0]["product"]["name"] == "Assiette"

    def test_get_not_found(self, client: TestClient, auth_headers_real):
        """Bundle inexistant → 404."""
        resp = client.get("/api/v1/bundles/99999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_get_cross_tenant(self, client: TestClient, auth_headers_tenant2, test_db):
        """Bundle d'un autre tenant → 404 (isolation multi-tenant)."""
        bundle = _create_bundle(test_db, tenant_id=1, name="T1 Only")

        resp = client.get(f"/api/v1/bundles/{bundle.id}", headers=auth_headers_tenant2)
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# POST /bundles
# ─────────────────────────────────────────────────────────────────────

class TestCreateBundle:
    """Tests pour POST /api/v1/bundles."""

    def test_create_with_auto_slug(self, client: TestClient, auth_headers_admin):
        """Creation avec slug auto-genere."""
        resp = client.post(
            "/api/v1/bundles",
            json={"name": "Pack Mariage", "bundle_price_cents": 50000},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Pack Mariage"
        assert data["slug"] == "pack_mariage"
        assert data["bundle_price_cents"] == 50000

    def test_create_slug_duplicate_returns_400(self, client: TestClient, auth_headers_admin, test_db):
        """Slug duplique → 400."""
        _create_bundle(test_db, name="Pack Existant", slug="pack_existant")

        resp = client.post(
            "/api/v1/bundles",
            json={"name": "Pack Autre", "slug": "pack_existant", "bundle_price_cents": 30000},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_create_non_admin_returns_403(self, client: TestClient, auth_headers_real):
        """Creation par non-admin → 403."""
        resp = client.post(
            "/api/v1/bundles",
            json={"name": "Forbidden", "bundle_price_cents": 10000},
            headers=auth_headers_real,
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# PATCH /bundles/{id}
# ─────────────────────────────────────────────────────────────────────

class TestUpdateBundle:
    """Tests pour PATCH /api/v1/bundles/{id}."""

    def test_update_name(self, client: TestClient, auth_headers_admin, test_db):
        """Mise a jour du nom."""
        bundle = _create_bundle(test_db, name="Old Pack")

        resp = client.patch(
            f"/api/v1/bundles/{bundle.id}",
            json={"name": "New Pack"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Pack"

    def test_update_not_found(self, client: TestClient, auth_headers_admin):
        """Update bundle inexistant → 404."""
        resp = client.patch(
            "/api/v1/bundles/99999",
            json={"name": "Ghost"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# DELETE /bundles/{id}
# ─────────────────────────────────────────────────────────────────────

class TestDeleteBundle:
    """Tests pour DELETE /api/v1/bundles/{id}."""

    def test_delete_soft_delete(self, client: TestClient, auth_headers_admin, test_db):
        """Soft delete reussi → 204."""
        bundle = _create_bundle(test_db, name="To Delete")

        resp = client.delete(f"/api/v1/bundles/{bundle.id}", headers=auth_headers_admin)
        assert resp.status_code == 204

    def test_delete_not_found(self, client: TestClient, auth_headers_admin):
        """Delete bundle inexistant → 404."""
        resp = client.delete("/api/v1/bundles/99999", headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_delete_cross_tenant(self, client: TestClient, auth_headers_admin_tenant2, test_db):
        """Delete bundle d'un autre tenant → 404."""
        bundle = _create_bundle(test_db, tenant_id=1, name="T1 Bundle")

        resp = client.delete(f"/api/v1/bundles/{bundle.id}", headers=auth_headers_admin_tenant2)
        assert resp.status_code == 404

    def test_delete_non_admin_returns_403(self, client: TestClient, auth_headers_real, test_db):
        """Delete par non-admin → 403."""
        bundle = _create_bundle(test_db, name="Protected")

        resp = client.delete(f"/api/v1/bundles/{bundle.id}", headers=auth_headers_real)
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# POST /bundles/{id}/items
# ─────────────────────────────────────────────────────────────────────

class TestAddBundleItem:
    """Tests pour POST /api/v1/bundles/{id}/items."""

    def test_add_item_ok(self, client: TestClient, auth_headers_admin, test_db):
        """Ajout d'un item au bundle."""
        bundle = _create_bundle(test_db, name="Pack Add Item")
        product = _create_product(test_db, name="Assiette Add", sku="ADD-001")

        resp = client.post(
            f"/api/v1/bundles/{bundle.id}/items",
            json={"product_id": product.id, "quantity": 10},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_id"] == product.id
        assert data["quantity"] == 10

    def test_add_item_duplicate_returns_400(self, client: TestClient, auth_headers_admin, test_db):
        """Doublon produit dans bundle → 400."""
        bundle = _create_bundle(test_db, name="Pack Dup")
        product = _create_product(test_db, name="Prod Dup", sku="DUP-001")
        _create_bundle_item(test_db, bundle.id, product.id)

        resp = client.post(
            f"/api/v1/bundles/{bundle.id}/items",
            json={"product_id": product.id, "quantity": 1},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_add_item_product_not_found_returns_400(self, client: TestClient, auth_headers_admin, test_db):
        """Produit inexistant → 400."""
        bundle = _create_bundle(test_db, name="Pack NoProd")

        resp = client.post(
            f"/api/v1/bundles/{bundle.id}/items",
            json={"product_id": 99999, "quantity": 1},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────
# DELETE /bundles/{id}/items/{item_id}
# ─────────────────────────────────────────────────────────────────────

class TestRemoveBundleItem:
    """Tests pour DELETE /api/v1/bundles/{id}/items/{item_id}."""

    def test_remove_item_ok(self, client: TestClient, auth_headers_admin, test_db):
        """Suppression d'un item du bundle → 204."""
        bundle = _create_bundle(test_db, name="Pack Remove")
        product = _create_product(test_db, name="Prod Remove", sku="REM-001")
        item = _create_bundle_item(test_db, bundle.id, product.id)

        resp = client.delete(
            f"/api/v1/bundles/{bundle.id}/items/{item.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 204

    def test_remove_item_not_found(self, client: TestClient, auth_headers_admin, test_db):
        """Item inexistant → 404."""
        bundle = _create_bundle(test_db, name="Pack NoItem")

        resp = client.delete(
            f"/api/v1/bundles/{bundle.id}/items/99999",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# GET /bundles/{id}/calculate-price
# ─────────────────────────────────────────────────────────────────────

class TestCalculatePrice:
    """Tests pour GET /api/v1/bundles/{id}/calculate-price."""

    def test_calculate_ok(self, client: TestClient, auth_headers_real, test_db):
        """Calcul de prix correct."""
        bundle = _create_bundle(test_db, name="Pack Calc", bundle_price=3000)
        prod = _create_product(test_db, name="Prod Calc", sku="CALC-001", price_per_day=250)
        _create_bundle_item(test_db, bundle.id, prod.id, quantity=20)

        resp = client.get(
            f"/api/v1/bundles/{bundle.id}/calculate-price",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        # individual = 250 * 20 = 5000
        assert data["individual_price_cents"] == 5000
        assert data["bundle_price_cents"] == 3000
        assert data["savings_cents"] == 2000
        assert data["savings_percent"] == 40.0

    def test_calculate_not_found(self, client: TestClient, auth_headers_real):
        """Bundle inexistant → 404."""
        resp = client.get(
            "/api/v1/bundles/99999/calculate-price",
            headers=auth_headers_real,
        )
        assert resp.status_code == 404
