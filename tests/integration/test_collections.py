"""Tests d'intégration pour les endpoints collections de produits."""
import pytest
from fastapi.testclient import TestClient


class TestCollectionsCRUD:
    def test_list_collections_empty(self, client: TestClient, auth_headers_real: dict):
        """Liste accessible en lecture (PRODUCTS_READ = staff+)."""
        r = client.get("/api/v1/collections", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_create_collection(self, client: TestClient, auth_headers_admin: dict):
        """Créer une collection (PRODUCTS_WRITE = admin)."""
        r = client.post(
            "/api/v1/collections",
            json={"name": "Mariage Champêtre", "description": "Pack mariage", "is_active": True},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Mariage Champêtre"
        assert data["description"] == "Pack mariage"
        assert data["is_active"] is True
        assert "id" in data

    def test_get_collection(self, client: TestClient, auth_headers_admin: dict, auth_headers_real: dict):
        """Récupérer une collection par ID."""
        r = client.post(
            "/api/v1/collections",
            json={"name": "Pack DJ"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        col_id = r.json()["id"]

        # Lecture par staff
        r2 = client.get(f"/api/v1/collections/{col_id}", headers=auth_headers_real)
        assert r2.status_code == 200
        data = r2.json()
        assert data["id"] == col_id
        assert data["name"] == "Pack DJ"
        assert "products" in data

    def test_get_collection_not_found(self, client: TestClient, auth_headers_real: dict):
        r = client.get("/api/v1/collections/999999", headers=auth_headers_real)
        assert r.status_code == 404

    def test_update_collection(self, client: TestClient, auth_headers_admin: dict):
        """Mettre à jour une collection."""
        r = client.post(
            "/api/v1/collections",
            json={"name": "Old Name"},
            headers=auth_headers_admin,
        )
        col_id = r.json()["id"]

        r2 = client.patch(
            f"/api/v1/collections/{col_id}",
            json={"name": "New Name", "is_active": False},
            headers=auth_headers_admin,
        )
        assert r2.status_code == 200
        data = r2.json()
        assert data["name"] == "New Name"
        assert data["is_active"] is False

    def test_delete_collection(self, client: TestClient, auth_headers_admin: dict, auth_headers_real: dict):
        """Supprimer une collection."""
        r = client.post(
            "/api/v1/collections",
            json={"name": "To Delete"},
            headers=auth_headers_admin,
        )
        col_id = r.json()["id"]

        r2 = client.delete(f"/api/v1/collections/{col_id}", headers=auth_headers_admin)
        assert r2.status_code == 204

        r3 = client.get(f"/api/v1/collections/{col_id}", headers=auth_headers_real)
        assert r3.status_code == 404

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/collections")
        assert r.status_code == 401


class TestCollectionsProducts:
    def test_add_products_to_collection(
        self, client: TestClient, auth_headers_admin: dict, test_db
    ):
        """Ajouter des produits à une collection."""
        from app.models.product import Product
        from app.constants import ProductCategory

        product = Product(
            tenant_id=1,
            name="Table Ronde Coll",
            sku="TABLE-COLL-001",
            category=ProductCategory.TABLES,
            price_per_day_cents=5000,
            stock_quantity=10,
            is_active=True,
        )
        test_db.add(product)
        test_db.flush()

        r = client.post(
            "/api/v1/collections",
            json={"name": "Mobilier Mariage"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        col_id = r.json()["id"]

        r2 = client.post(
            f"/api/v1/collections/{col_id}/products",
            json={"product_ids": [product.id]},
            headers=auth_headers_admin,
        )
        assert r2.status_code == 200
        data = r2.json()
        assert len(data["products"]) == 1
        assert data["products"][0]["id"] == product.id

    def test_remove_product_from_collection(
        self, client: TestClient, auth_headers_admin: dict, test_db
    ):
        """Retirer un produit d'une collection."""
        from app.models.product import Product
        from app.constants import ProductCategory

        product = Product(
            tenant_id=1,
            name="Chaise Chiavari Coll",
            sku="CHAISE-COLL-001",
            category=ProductCategory.CHAISES,
            price_per_day_cents=1500,
            stock_quantity=50,
            is_active=True,
        )
        test_db.add(product)
        test_db.flush()

        r = client.post(
            "/api/v1/collections",
            json={"name": "Chaises Coll"},
            headers=auth_headers_admin,
        )
        col_id = r.json()["id"]

        client.post(
            f"/api/v1/collections/{col_id}/products",
            json={"product_ids": [product.id]},
            headers=auth_headers_admin,
        )

        r2 = client.delete(
            f"/api/v1/collections/{col_id}/products/{product.id}",
            headers=auth_headers_admin,
        )
        assert r2.status_code == 200
        assert len(r2.json()["products"]) == 0

    def test_tenant_isolation(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
    ):
        """Tenant 2 ne voit pas les collections de tenant 1."""
        r1 = client.post(
            "/api/v1/collections",
            json={"name": "Collection Tenant 1"},
            headers=auth_headers_admin,
        )
        col_id = r1.json()["id"]

        r2 = client.get(
            f"/api/v1/collections/{col_id}",
            headers=auth_headers_tenant2,
        )
        assert r2.status_code == 404
