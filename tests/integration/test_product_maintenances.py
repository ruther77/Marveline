"""Tests intégration — ProductMaintenance CRUD + isolation tenant."""
import pytest
from fastapi.testclient import TestClient

from app.constants import ProductCategory, ProductCondition
from app.models.product import Product


@pytest.fixture
def test_product(test_db):
    """Produit de test tenant_id=1."""
    product = Product(
        tenant_id=1,
        name="Table maintenance test",
        sku="MAINT-TEST-001",
        category=ProductCategory.TABLES,
        price_per_day_cents=1500,
        deposit_amount_cents=3000,
        stock_quantity=5,
        available_quantity=5,
        condition=ProductCondition.BON,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


class TestMaintenanceCRUD:
    """Tests CRUD complets sur /products/{id}/maintenances."""

    def test_list_maintenances_empty(
        self, client: TestClient, test_product, auth_headers_real: dict
    ):
        """Liste vide initialement."""
        r = client.get(
            f"/api/v1/products/{test_product.id}/maintenances",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_create_maintenance(
        self, client: TestClient, test_product, auth_headers_admin: dict
    ):
        """Création → 201 avec champs corrects."""
        r = client.post(
            f"/api/v1/products/{test_product.id}/maintenances",
            json={
                "title": "Révision annuelle",
                "description": "Contrôle général",
                "scheduled_date": "2026-03-01",
                "cost_cents": 5000,
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Révision annuelle"
        assert data["status"] == "scheduled"
        assert data["product_id"] == test_product.id
        assert data["tenant_id"] == 1
        assert data["cost_cents"] == 5000
        assert data["is_active"] is True

    def test_list_maintenances_after_create(
        self, client: TestClient, test_product, auth_headers_admin: dict, auth_headers_real: dict
    ):
        """Après création, la liste contient l'entrée."""
        client.post(
            f"/api/v1/products/{test_product.id}/maintenances",
            json={"title": "Entretien courant"},
            headers=auth_headers_admin,
        )
        r = client.get(
            f"/api/v1/products/{test_product.id}/maintenances",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert items[0]["title"] == "Entretien courant"

    def test_update_maintenance_status(
        self, client: TestClient, test_product, auth_headers_admin: dict
    ):
        """PATCH status → in_progress."""
        created = client.post(
            f"/api/v1/products/{test_product.id}/maintenances",
            json={"title": "Réparation"},
            headers=auth_headers_admin,
        ).json()
        r = client.patch(
            f"/api/v1/products/{test_product.id}/maintenances/{created['id']}",
            json={"status": "in_progress"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    def test_delete_maintenance(
        self, client: TestClient, test_product, auth_headers_admin: dict, auth_headers_real: dict
    ):
        """DELETE → 204 puis plus visible dans la liste."""
        created = client.post(
            f"/api/v1/products/{test_product.id}/maintenances",
            json={"title": "Nettoyage"},
            headers=auth_headers_admin,
        ).json()
        r = client.delete(
            f"/api/v1/products/{test_product.id}/maintenances/{created['id']}",
            headers=auth_headers_admin,
        )
        assert r.status_code == 204
        # Vérifier que la liste ne contient plus l'entrée
        r2 = client.get(
            f"/api/v1/products/{test_product.id}/maintenances",
            headers=auth_headers_real,
        )
        ids = [m["id"] for m in r2.json()]
        assert created["id"] not in ids

    def test_update_unknown_maintenance_returns_404(
        self, client: TestClient, test_product, auth_headers_admin: dict
    ):
        """PATCH maintenance inconnue → 404."""
        r = client.patch(
            f"/api/v1/products/{test_product.id}/maintenances/999999",
            json={"status": "completed"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_list_maintenances_product_not_found_returns_404(
        self, client: TestClient, auth_headers_real: dict
    ):
        """Liste pour produit inexistant → 404."""
        r = client.get(
            "/api/v1/products/999999/maintenances",
            headers=auth_headers_real,
        )
        assert r.status_code == 404


class TestMaintenanceTenantIsolation:
    """Isolation tenant — un tenant ne voit pas les maintenances d'un autre."""

    def test_cross_tenant_not_visible(
        self,
        client: TestClient,
        test_product,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
    ):
        """Les maintenances du tenant 1 sont invisibles pour le tenant 2."""
        client.post(
            f"/api/v1/products/{test_product.id}/maintenances",
            json={"title": "Maintenance tenant 1"},
            headers=auth_headers_admin,
        )
        # tenant 2 tente de lister les maintenances du produit du tenant 1
        r = client.get(
            f"/api/v1/products/{test_product.id}/maintenances",
            headers=auth_headers_tenant2,
        )
        # Doit renvoyer 404 (produit inconnu pour tenant 2)
        assert r.status_code == 404
