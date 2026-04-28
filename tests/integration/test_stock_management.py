"""Tests d'intégration pour les endpoints stock management."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.product import Product


# ---------------------------------------------------------------------------
# Fixture produit test
# ---------------------------------------------------------------------------

@pytest.fixture
def stock_product(test_db, auth_headers_admin, client):
    """Crée un produit de test via l'API (requiert admin pour PRODUCTS_WRITE)."""
    client.post(
        "/api/v1/categories",
        json={"name": "Cat Stock Test", "description": "test"},
        headers=auth_headers_admin,
    )

    p_resp = client.post(
        "/api/v1/products",
        json={
            "name": "Produit Stock Test",
            "sku": "SKU-STOCK-TEST-001",
            "category": "vaisselle",
            "price_per_day_cents": 100,
            "deposit_amount_cents": 0,
            "stock_quantity": 20,
            "available_quantity": 20,
        },
        headers=auth_headers_admin,
    )
    if p_resp.status_code not in (200, 201):
        pytest.skip(f"Impossible de créer produit: {p_resp.text}")
    return p_resp.json()


# ---------------------------------------------------------------------------
# Inventaire physique
# ---------------------------------------------------------------------------

class TestInventaire:
    def test_start_inventaire(self, client: TestClient, auth_headers_real: dict):
        """Démarre une session d'inventaire → 201."""
        r = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "in_progress"
        assert "id" in data

        # Nettoyage — compléter la session pour libérer pour les autres tests
        client.post(f"/api/v1/stock/inventaire/{data['id']}/complete", headers=auth_headers_real)

    def test_start_duplicate_409(self, client: TestClient, auth_headers_real: dict):
        """Deux sessions en parallèle → 409."""
        r1 = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        assert r1.status_code == 201
        r2 = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        assert r2.status_code == 409
        # Nettoyage
        client.post(f"/api/v1/stock/inventaire/{r1.json()['id']}/complete", headers=auth_headers_real)

    def test_get_inventaire(self, client: TestClient, auth_headers_real: dict):
        """Récupère une session."""
        r = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        session_id = r.json()["id"]
        r2 = client.get(f"/api/v1/stock/inventaire/{session_id}", headers=auth_headers_real)
        assert r2.status_code == 200
        assert r2.json()["id"] == session_id
        client.post(f"/api/v1/stock/inventaire/{session_id}/complete", headers=auth_headers_real)

    def test_get_not_found(self, client: TestClient, auth_headers_real: dict):
        r = client.get("/api/v1/stock/inventaire/99999", headers=auth_headers_real)
        assert r.status_code == 404

    def test_update_and_complete(
        self, client: TestClient, auth_headers_real: dict, stock_product: dict
    ):
        """Saisit un comptage et complète la session."""
        r = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        session_id = r.json()["id"]

        # Saisir comptage
        r2 = client.patch(
            f"/api/v1/stock/inventaire/{session_id}",
            json={"entries": [{"product_id": stock_product["id"], "counted_quantity": 18}]},
            headers=auth_headers_real,
        )
        assert r2.status_code == 200
        variances = r2.json()["variances_json"]
        assert str(stock_product["id"]) in variances

        # Compléter
        r3 = client.post(
            f"/api/v1/stock/inventaire/{session_id}/complete",
            headers=auth_headers_real,
        )
        assert r3.status_code == 200
        assert r3.json()["status"] == "completed"

    def test_complete_already_done(self, client: TestClient, auth_headers_real: dict):
        """Compléter deux fois → 400."""
        r = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        session_id = r.json()["id"]
        client.post(f"/api/v1/stock/inventaire/{session_id}/complete", headers=auth_headers_real)
        r2 = client.post(f"/api/v1/stock/inventaire/{session_id}/complete", headers=auth_headers_real)
        assert r2.status_code == 400

    def test_unauthenticated(self, client: TestClient):
        r = client.post("/api/v1/stock/inventaire")
        assert r.status_code == 401

    def test_cross_tenant_blocked(
        self, client: TestClient, auth_headers_real: dict, auth_headers_tenant2: dict
    ):
        """Tenant2 ne peut pas voir/modifier l'inventaire de Tenant1."""
        r = client.post("/api/v1/stock/inventaire", headers=auth_headers_real)
        session_id = r.json()["id"]
        r2 = client.get(f"/api/v1/stock/inventaire/{session_id}", headers=auth_headers_tenant2)
        assert r2.status_code == 404
        client.post(f"/api/v1/stock/inventaire/{session_id}/complete", headers=auth_headers_real)


# ---------------------------------------------------------------------------
# Ajustements manuels
# ---------------------------------------------------------------------------

class TestAdjustments:
    def test_create_adjustment(
        self, client: TestClient, auth_headers_real: dict, stock_product: dict
    ):
        """Crée un ajustement positif."""
        r = client.post(
            "/api/v1/stock/adjustments",
            json={"product_id": stock_product["id"], "delta": 5, "reason": "Réception fournisseur"},
            headers=auth_headers_real,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["delta"] == 5
        assert data["reason"] == "Réception fournisseur"
        assert data["product_id"] == stock_product["id"]

    def test_create_negative_adjustment(
        self, client: TestClient, auth_headers_real: dict, stock_product: dict
    ):
        """Ajustement négatif (perte/casse)."""
        r = client.post(
            "/api/v1/stock/adjustments",
            json={"product_id": stock_product["id"], "delta": -2, "reason": "Casse accidentelle"},
            headers=auth_headers_real,
        )
        assert r.status_code == 201
        assert r.json()["delta"] == -2

    def test_list_adjustments(
        self, client: TestClient, auth_headers_real: dict, stock_product: dict
    ):
        """Liste des ajustements du tenant — contrat PaginatedResponse."""
        client.post(
            "/api/v1/stock/adjustments",
            json={"product_id": stock_product["id"], "delta": 1, "reason": "Test list"},
            headers=auth_headers_real,
        )
        r = client.get("/api/v1/stock/adjustments", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "total" in data
        assert data["total"] >= 1

    def test_list_adjustments_filter_product(
        self, client: TestClient, auth_headers_real: dict, stock_product: dict
    ):
        """Filtre par product_id."""
        r = client.get(
            f"/api/v1/stock/adjustments?product_id={stock_product['id']}",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        for adj in r.json()["items"]:
            assert adj["product_id"] == stock_product["id"]

    def test_product_not_found(self, client: TestClient, auth_headers_real: dict):
        """Produit inexistant → 404."""
        r = client.post(
            "/api/v1/stock/adjustments",
            json={"product_id": 99999, "delta": 1, "reason": "Test"},
            headers=auth_headers_real,
        )
        assert r.status_code == 404

    def test_cross_tenant_product_blocked(
        self, client: TestClient, auth_headers_real: dict,
        auth_headers_tenant2: dict, stock_product: dict
    ):
        """Tenant2 ne peut pas ajuster le stock d'un produit Tenant1."""
        r = client.post(
            "/api/v1/stock/adjustments",
            json={"product_id": stock_product["id"], "delta": 1, "reason": "XTenant"},
            headers=auth_headers_tenant2,
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Niveaux de stock
# ---------------------------------------------------------------------------

class TestStockLevels:
    def test_get_levels(self, client: TestClient, auth_headers_real: dict):
        """Retourne les niveaux de stock — contrat PaginatedResponse."""
        r = client.get("/api/v1/stock/levels", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "total" in data
        for item in data["items"]:
            assert item["level"] in ("critical", "low", "ok", "overstock")

    def test_get_reorder_list(self, client: TestClient, auth_headers_real: dict):
        """Liste des produits sous seuil réassort — contrat PaginatedResponse."""
        r = client.get("/api/v1/stock/reorder", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "total" in data

    def test_create_reorder(self, client: TestClient, auth_headers_real: dict, stock_product: dict):
        """Crée une commande de réassort."""
        r = client.post(
            "/api/v1/stock/reorder",
            json={"items": [{"product_id": stock_product["id"], "quantity": 10}]},
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        assert r.json()["created"] == 1

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/stock/levels")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Couverture stock
# ---------------------------------------------------------------------------

class TestStockCoverage:
    def test_get_coverage_returns_200(self, client: TestClient, auth_headers_real: dict):
        """GET /stock/coverage → 200 avec structure attendue."""
        r = client.get("/api/v1/stock/coverage", headers=auth_headers_real)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "computed_at" in data
        assert isinstance(data["items"], list)

    def test_coverage_item_structure(
        self, client: TestClient, auth_headers_real: dict, stock_product: dict
    ):
        """Chaque item de couverture a les champs métriques attendus."""
        r = client.get("/api/v1/stock/coverage", headers=auth_headers_real)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) > 0
        item = next(i for i in items if i["product_id"] == stock_product["id"])
        assert item["available_qty"] >= 0
        assert item["total_qty"] >= 0
        assert item["movements_30d"] >= 0
        assert item["avg_daily_movements"] >= 0
        assert item["status"] in ("critical", "low", "ok", "good")
        # Produit sans mouvement → days_of_coverage = None
        assert item["days_of_coverage"] is None

    def test_coverage_cross_tenant_isolation(
        self, client: TestClient, auth_headers_real: dict, auth_headers_admin: dict
    ):
        """Un tenant ne voit pas les produits d'un autre tenant."""
        r1 = client.get("/api/v1/stock/coverage", headers=auth_headers_real)
        r2 = client.get("/api/v1/stock/coverage", headers=auth_headers_admin)
        assert r1.status_code == 200
        assert r2.status_code == 200
        ids1 = {i["product_id"] for i in r1.json()["items"]}
        ids2 = {i["product_id"] for i in r2.json()["items"]}
        # Les deux tenants n'ont pas les mêmes produits (isolation)
        assert ids1.isdisjoint(ids2)

    def test_coverage_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/stock/coverage")
        assert r.status_code == 401
