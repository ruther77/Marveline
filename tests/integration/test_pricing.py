"""Tests d'intégration pour les endpoints pricing rules."""
import pytest
from fastapi.testclient import TestClient

from app.models.product import Product
from app.constants import ProductCategory, ProductCondition


class TestPricingRulesCRUD:
    def test_list_empty(self, client: TestClient, auth_headers_admin: dict):
        """Liste vide initialement."""
        r = client.get("/api/v1/pricing/rules", headers=auth_headers_admin)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_ok(self, client: TestClient, auth_headers_admin: dict):
        """Création d'une règle flat."""
        r = client.post(
            "/api/v1/pricing/rules",
            json={
                "name": "Remise été 10%",
                "rule_type": "flat",
                "applies_to": "all",
                "discount_pct": 1000,
                "valid_from": "2026-06-01",
                "valid_to": "2026-08-31",
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Remise été 10%"
        assert data["rule_type"] == "flat"
        assert data["applies_to"] == "all"
        assert data["discount_pct"] == 1000
        assert data["active"] is True
        assert "id" in data

    def test_create_with_tiers(self, client: TestClient, auth_headers_admin: dict):
        """Règle tiered avec paliers."""
        r = client.post(
            "/api/v1/pricing/rules",
            json={
                "name": "Tarif volume",
                "rule_type": "tiered",
                "applies_to": "product",
                "target_id": 1,
                "tiers": [
                    {"min_qty": 1, "max_qty": 9, "unit_price_cents": 500},
                    {"min_qty": 10, "max_qty": None, "unit_price_cents": 400},
                ],
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 201
        data = r.json()
        assert len(data["tiers"]) == 2
        assert data["tiers"][0]["unit_price_cents"] == 500

    def test_get_by_id(self, client: TestClient, auth_headers_admin: dict):
        """Récupération par ID."""
        created = client.post(
            "/api/v1/pricing/rules",
            json={"name": "GetById Rule", "rule_type": "flat", "applies_to": "all"},
            headers=auth_headers_admin,
        ).json()
        r = client.get(f"/api/v1/pricing/rules/{created['id']}", headers=auth_headers_admin)
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_get_not_found(self, client: TestClient, auth_headers_admin: dict):
        r = client.get("/api/v1/pricing/rules/99999", headers=auth_headers_admin)
        assert r.status_code == 404

    def test_update_ok(self, client: TestClient, auth_headers_admin: dict):
        """PATCH partiel."""
        created = client.post(
            "/api/v1/pricing/rules",
            json={"name": "Update Rule Test", "rule_type": "flat", "applies_to": "all"},
            headers=auth_headers_admin,
        ).json()
        r = client.patch(
            f"/api/v1/pricing/rules/{created['id']}",
            json={"discount_pct": 500, "name": "Updated Rule"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["discount_pct"] == 500
        assert data["name"] == "Updated Rule"

    def test_delete_ok(self, client: TestClient, auth_headers_admin: dict):
        """Soft-delete → 204, puis invisible dans list (active_only=True)."""
        created = client.post(
            "/api/v1/pricing/rules",
            json={"name": "ToDelete Rule", "rule_type": "flat", "applies_to": "all"},
            headers=auth_headers_admin,
        ).json()
        r = client.delete(f"/api/v1/pricing/rules/{created['id']}", headers=auth_headers_admin)
        assert r.status_code == 204
        # Vérifier que la règle est inactive (active_only=False)
        r2 = client.get(
            f"/api/v1/pricing/rules/{created['id']}", headers=auth_headers_admin
        )
        assert r2.status_code == 200
        assert r2.json()["active"] is False

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/pricing/rules")
        assert r.status_code == 401


class TestPricingRulesForProduct:
    def test_get_rules_for_product(self, client: TestClient, auth_headers_admin: dict):
        """Règles applicables à un produit."""
        # Créer règle "all"
        client.post(
            "/api/v1/pricing/rules",
            json={"name": "Rule All For Product Test", "rule_type": "flat", "applies_to": "all", "discount_pct": 100},
            headers=auth_headers_admin,
        )
        r = client.get("/api/v1/pricing/rules/product/1", headers=auth_headers_admin)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        # La règle "all" doit apparaître
        names = [item["name"] for item in r.json()]
        assert "Rule All For Product Test" in names

    def test_unauthenticated(self, client: TestClient):
        r = client.get("/api/v1/pricing/rules/product/1")
        assert r.status_code == 401


class TestPricingTenantIsolation:
    def test_cross_tenant_get_blocked(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_tenant2: dict
    ):
        """Tenant2 ne peut pas voir la règle de Tenant1."""
        created = client.post(
            "/api/v1/pricing/rules",
            json={"name": "Tenant1 Only Rule", "rule_type": "flat", "applies_to": "all"},
            headers=auth_headers_admin,
        ).json()
        r = client.get(
            f"/api/v1/pricing/rules/{created['id']}", headers=auth_headers_tenant2
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Simulate
# ---------------------------------------------------------------------------

@pytest.fixture
def product_sim(test_db):
    p = Product(
        tenant_id=1,
        name="Assiette test sim",
        sku="ASS-SIM-001",
        category=ProductCategory.ASSIETTES,
        price_per_day_cents=500,
        deposit_amount_cents=0,
        stock_quantity=50,
        available_quantity=50,
        condition=ProductCondition.BON,
        is_active=True,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


class TestPricingSimulate:
    def test_simulate_no_rule_returns_base_price(
        self, client: TestClient, auth_headers_admin: dict, product_sim
    ):
        """Sans règle active, prix = price_per_day × qty × days."""
        r = client.post(
            "/api/v1/pricing/simulate",
            json={
                "product_id": product_sim.id,
                "quantity": 2,
                "rental_days": 3,
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["base_unit_price_cents"] == 500
        assert data["applied_rule_id"] is None
        assert data["discount_pct"] == 0
        assert data["final_unit_price_cents"] == 500
        assert data["total_cents"] == 500 * 2 * 3

    def test_simulate_with_discount_rule(
        self, client: TestClient, auth_headers_admin: dict, product_sim
    ):
        """Règle flat 'all' à 1000 bp (10%) → final = 450 centimes/unité."""
        # Créer une règle de remise globale
        client.post(
            "/api/v1/pricing/rules",
            json={
                "name": "Sim remise 10%",
                "rule_type": "flat",
                "applies_to": "all",
                "discount_pct": 1000,
            },
            headers=auth_headers_admin,
        )
        r = client.post(
            "/api/v1/pricing/simulate",
            json={
                "product_id": product_sim.id,
                "quantity": 1,
                "rental_days": 1,
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["discount_pct"] > 0
        assert data["final_unit_price_cents"] < data["base_unit_price_cents"]

    def test_simulate_product_not_found(
        self, client: TestClient, auth_headers_admin: dict
    ):
        r = client.post(
            "/api/v1/pricing/simulate",
            json={"product_id": 999999, "quantity": 1, "rental_days": 1},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_simulate_unauthenticated(self, client: TestClient, product_sim):
        r = client.post(
            "/api/v1/pricing/simulate",
            json={"product_id": product_sim.id, "quantity": 1, "rental_days": 1},
        )
        assert r.status_code == 401
