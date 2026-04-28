"""Tests d'integration pour les endpoints categories."""
import pytest
from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.product import Product
from app.utils.slug import slugify


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _create_category(db, tenant_id=1, name="Test Cat", slug=None, parent_id=None, display_order=0):
    """Cree une categorie dans la DB de test."""
    cat = Category(
        tenant_id=tenant_id,
        name=name,
        slug=slug or slugify(name),
        parent_id=parent_id,
        display_order=display_order,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _create_product(db, tenant_id=1, name="Produit Test", sku="PRD-001", category="test_cat"):
    """Cree un produit de test."""
    prod = Product(
        tenant_id=tenant_id,
        name=name,
        sku=sku,
        category=category,
        price_per_day_cents=25000,
        deposit_amount_cents=0,
        stock_quantity=10,
        available_quantity=10,
        condition="bon",
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


# ─────────────────────────────────────────────────────────────────────
# GET /categories — Liste
# ─────────────────────────────────────────────────────────────────────

class TestListCategories:
    """Tests pour GET /api/v1/categories."""

    def test_list_empty(self, client: TestClient, auth_headers_real):
        """Liste vide quand aucune categorie."""
        resp = client.get("/api/v1/categories", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_returns_categories(self, client: TestClient, auth_headers_real, test_db):
        """Liste retourne les categories du tenant."""
        _create_category(test_db, name="Assiettes", slug="assiettes", display_order=1)
        _create_category(test_db, name="Verres", slug="verres", display_order=2)

        resp = client.get("/api/v1/categories", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        names = [c["name"] for c in data["items"]]
        assert "Assiettes" in names
        assert "Verres" in names

    def test_list_active_only_filter(self, client: TestClient, auth_headers_real, test_db):
        """active_only=true exclut les categories inactives."""
        cat = _create_category(test_db, name="Inactive Cat")
        cat.is_active = False
        test_db.commit()
        _create_category(test_db, name="Active Cat")

        # Par defaut active_only=true
        resp = client.get("/api/v1/categories", headers=auth_headers_real)
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Active Cat"

        # active_only=false inclut tout
        resp = client.get("/api/v1/categories?active_only=false", headers=auth_headers_real)
        data = resp.json()
        assert data["total"] == 2

    def test_list_requires_auth(self, client: TestClient):
        """Liste sans token → 401."""
        resp = client.get("/api/v1/categories")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# GET /categories/tree
# ─────────────────────────────────────────────────────────────────────

class TestGetTree:
    """Tests pour GET /api/v1/categories/tree."""

    def test_tree_returns_hierarchy(self, client: TestClient, auth_headers_real, test_db):
        """L'arbre construit correctement la hierarchie."""
        root = _create_category(test_db, name="Mobilier", slug="mobilier")
        _create_category(test_db, name="Tables", slug="tables", parent_id=root.id)

        resp = client.get("/api/v1/categories/tree", headers=auth_headers_real)
        assert resp.status_code == 200
        tree = resp.json()
        assert len(tree) == 1
        assert tree[0]["name"] == "Mobilier"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["name"] == "Tables"

    def test_tree_includes_product_count(self, client: TestClient, auth_headers_real, test_db):
        """L'arbre inclut le nombre de produits par categorie."""
        _create_category(test_db, name="Verres", slug="verres")
        _create_product(test_db, name="Verre 1", sku="V-001", category="verres")
        _create_product(test_db, name="Verre 2", sku="V-002", category="verres")

        resp = client.get("/api/v1/categories/tree", headers=auth_headers_real)
        tree = resp.json()
        verres = next(n for n in tree if n["slug"] == "verres")
        assert verres["product_count"] == 2

    def test_tree_empty_tenant(self, client: TestClient, auth_headers_tenant2):
        """Arbre vide pour un tenant sans categories."""
        resp = client.get("/api/v1/categories/tree", headers=auth_headers_tenant2)
        assert resp.status_code == 200
        assert resp.json() == []


# ─────────────────────────────────────────────────────────────────────
# GET /categories/{id}
# ─────────────────────────────────────────────────────────────────────

class TestGetCategory:
    """Tests pour GET /api/v1/categories/{id}."""

    def test_get_found(self, client: TestClient, auth_headers_real, test_db):
        """Retourne les details d'une categorie existante."""
        cat = _create_category(test_db, name="Nappes", slug="nappes", display_order=5)

        resp = client.get(f"/api/v1/categories/{cat.id}", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Nappes"
        assert data["slug"] == "nappes"
        assert data["display_order"] == 5

    def test_get_not_found(self, client: TestClient, auth_headers_real):
        """Categorie inexistante → 404."""
        resp = client.get("/api/v1/categories/99999", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_get_cross_tenant(self, client: TestClient, auth_headers_tenant2, test_db):
        """Categorie d'un autre tenant → 404 (isolation multi-tenant)."""
        cat = _create_category(test_db, tenant_id=1, name="Tenant1 Only")

        resp = client.get(f"/api/v1/categories/{cat.id}", headers=auth_headers_tenant2)
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# POST /categories
# ─────────────────────────────────────────────────────────────────────

class TestCreateCategory:
    """Tests pour POST /api/v1/categories."""

    def test_create_with_auto_slug(self, client: TestClient, auth_headers_admin):
        """Creation avec slug auto-genere depuis le nom."""
        resp = client.post(
            "/api/v1/categories",
            json={"name": "Vaisselle Service"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Vaisselle Service"
        assert data["slug"] == "vaisselle_service"

    def test_create_with_explicit_slug(self, client: TestClient, auth_headers_admin):
        """Creation avec slug explicite."""
        resp = client.post(
            "/api/v1/categories",
            json={"name": "Verres a vin", "slug": "verres_vin"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "verres_vin"

    def test_create_slug_duplicate_returns_400(self, client: TestClient, auth_headers_admin, test_db):
        """Slug duplique → 400."""
        _create_category(test_db, name="Chaises", slug="chaises")

        resp = client.post(
            "/api/v1/categories",
            json={"name": "Chaises Luxe", "slug": "chaises"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 400

    def test_create_non_admin_returns_403(self, client: TestClient, auth_headers_real):
        """Creation par non-admin → 403."""
        resp = client.post(
            "/api/v1/categories",
            json={"name": "Forbidden"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# PATCH /categories/{id}
# ─────────────────────────────────────────────────────────────────────

class TestUpdateCategory:
    """Tests pour PATCH /api/v1/categories/{id}."""

    def test_update_name(self, client: TestClient, auth_headers_admin, test_db):
        """Mise a jour du nom."""
        cat = _create_category(test_db, name="Old Name")

        resp = client.patch(
            f"/api/v1/categories/{cat.id}",
            json={"name": "New Name"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_update_not_found(self, client: TestClient, auth_headers_admin):
        """Update categorie inexistante → 404."""
        resp = client.patch(
            "/api/v1/categories/99999",
            json={"name": "Ghost"},
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404

    def test_update_non_admin_returns_403(self, client: TestClient, auth_headers_real, test_db):
        """Update par non-admin → 403."""
        cat = _create_category(test_db, name="No Touch")

        resp = client.patch(
            f"/api/v1/categories/{cat.id}",
            json={"name": "Hacked"},
            headers=auth_headers_real,
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# DELETE /categories/{id}
# ─────────────────────────────────────────────────────────────────────

class TestDeleteCategory:
    """Tests pour DELETE /api/v1/categories/{id}."""

    def test_delete_soft_delete(self, client: TestClient, auth_headers_admin, test_db):
        """Soft delete reussi → 204."""
        cat = _create_category(test_db, name="To Delete")

        resp = client.delete(f"/api/v1/categories/{cat.id}", headers=auth_headers_admin)
        assert resp.status_code == 204

    def test_delete_with_children_returns_400(self, client: TestClient, auth_headers_admin, test_db):
        """Delete categorie avec enfants actifs → 400."""
        parent = _create_category(test_db, name="Parent Cat")
        _create_category(test_db, name="Child Cat", parent_id=parent.id)

        resp = client.delete(f"/api/v1/categories/{parent.id}", headers=auth_headers_admin)
        assert resp.status_code == 400

    def test_delete_not_found(self, client: TestClient, auth_headers_admin):
        """Delete categorie inexistante → 404."""
        resp = client.delete("/api/v1/categories/99999", headers=auth_headers_admin)
        assert resp.status_code == 404

    def test_delete_cross_tenant(self, client: TestClient, auth_headers_admin_tenant2, test_db):
        """Delete categorie d'un autre tenant → 404."""
        cat = _create_category(test_db, tenant_id=1, name="Tenant1 Cat")

        resp = client.delete(f"/api/v1/categories/{cat.id}", headers=auth_headers_admin_tenant2)
        assert resp.status_code == 404

    def test_delete_non_admin_returns_403(self, client: TestClient, auth_headers_real, test_db):
        """Delete par non-admin → 403."""
        cat = _create_category(test_db, name="Protected")

        resp = client.delete(f"/api/v1/categories/{cat.id}", headers=auth_headers_real)
        assert resp.status_code == 403
