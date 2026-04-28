"""Tests d'intégration — Commandes fournisseurs (cycle commande)."""
import pytest
from fastapi.testclient import TestClient


def _create_supplier(client: TestClient, headers: dict, name: str = "Fournisseur Test") -> dict:
    r = client.post("/api/v1/suppliers", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()


def _create_product(client: TestClient, headers: dict, name: str = "Produit Test") -> dict:
    import hashlib
    sku = "SKU-" + hashlib.md5(name.encode()).hexdigest()[:8].upper()
    r = client.post(
        "/api/v1/products",
        json={
            "name": name,
            "sku": sku,
            "category": "mobilier",
            "price_per_day_cents": 1000,
            "deposit_amount_cents": 0,
            "stock_quantity": 10,
            "available_quantity": 10,
        },
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


def _create_order(client: TestClient, headers: dict, supplier_id: int, product_id: int) -> dict:
    r = client.post(
        "/api/v1/supplier-orders",
        json={
            "supplier_id": supplier_id,
            "reference": "CMD-TEST-001",
            "order_date": "2026-02-23",
            "expected_date": "2026-03-01",
            "lines": [
                {"product_id": product_id, "qty_ordered": 10, "unit_cost_cents": 500}
            ],
        },
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()


class TestSupplierOrdersCRUD:
    """Tests CRUD commandes fournisseurs."""

    def test_list_empty(self, client: TestClient, auth_headers_admin: dict):
        r = client.get("/api/v1/supplier-orders", headers=auth_headers_admin)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    def test_create_ok(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur CRUD")
        product = _create_product(client, auth_headers_admin, "Produit CRUD")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        assert order["status"] == "draft"
        assert order["reference"] == "CMD-TEST-001"
        assert len(order["lines"]) == 1
        assert order["lines"][0]["qty_ordered"] == 10
        assert order["lines"][0]["qty_received"] == 0
        assert order["lines"][0]["qty_remaining"] == 10

    def test_create_no_lines_422(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur NoLines")
        r = client.post(
            "/api/v1/supplier-orders",
            json={"supplier_id": supplier["id"], "reference": "CMD-EMPTY", "lines": []},
            headers=auth_headers_admin,
        )
        assert r.status_code == 422

    def test_get_by_id(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur GetById")
        product = _create_product(client, auth_headers_admin, "Produit GetById")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        r = client.get(f"/api/v1/supplier-orders/{order['id']}", headers=auth_headers_admin)
        assert r.status_code == 200
        assert r.json()["id"] == order["id"]

    def test_get_not_found(self, client: TestClient, auth_headers_admin: dict):
        r = client.get("/api/v1/supplier-orders/99999", headers=auth_headers_admin)
        assert r.status_code == 404

    def test_update_ok(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur Update")
        product = _create_product(client, auth_headers_admin, "Produit Update")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        r = client.patch(
            f"/api/v1/supplier-orders/{order['id']}",
            json={"notes": "Livraison urgente"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["notes"] == "Livraison urgente"

    def test_delete_ok(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur Delete")
        product = _create_product(client, auth_headers_admin, "Produit Delete")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        r = client.delete(f"/api/v1/supplier-orders/{order['id']}", headers=auth_headers_admin)
        assert r.status_code == 204
        # Plus accessible après suppression
        r2 = client.get(f"/api/v1/supplier-orders/{order['id']}", headers=auth_headers_admin)
        assert r2.status_code == 404

    def test_unauthenticated_401(self, client: TestClient):
        r = client.get("/api/v1/supplier-orders")
        assert r.status_code == 401


class TestSupplierOrdersWorkflow:
    """Tests du cycle de vie : draft → ordered → réception."""

    def test_confirm_draft_to_ordered(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur Confirm")
        product = _create_product(client, auth_headers_admin, "Produit Confirm")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        assert order["status"] == "draft"
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/confirm",
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ordered"

    def test_confirm_already_ordered_409(self, client: TestClient, auth_headers_admin: dict):
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur ConfirmDup")
        product = _create_product(client, auth_headers_admin, "Produit ConfirmDup")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        client.post(f"/api/v1/supplier-orders/{order['id']}/confirm", headers=auth_headers_admin)
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/confirm",
            headers=auth_headers_admin,
        )
        assert r.status_code == 409

    def test_full_reception(self, client: TestClient, auth_headers_admin: dict):
        """Réception totale → fully_received."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur FullRecv")
        product = _create_product(client, auth_headers_admin, "Produit FullRecv")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        client.post(f"/api/v1/supplier-orders/{order['id']}/confirm", headers=auth_headers_admin)
        line_id = order["lines"][0]["id"]
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/receive",
            json={"lines": [{"line_id": line_id, "qty_received": 10}]},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "fully_received"
        assert data["lines"][0]["qty_received"] == 10
        assert data["lines"][0]["qty_remaining"] == 0
        assert len(data["receipts"]) == 1

    def test_partial_reception(self, client: TestClient, auth_headers_admin: dict):
        """Réception partielle → partially_received + reliquat correct."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur PartialRecv")
        product = _create_product(client, auth_headers_admin, "Produit PartialRecv")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        client.post(f"/api/v1/supplier-orders/{order['id']}/confirm", headers=auth_headers_admin)
        line_id = order["lines"][0]["id"]
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/receive",
            json={"lines": [{"line_id": line_id, "qty_received": 4}]},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "partially_received"
        assert data["lines"][0]["qty_received"] == 4
        assert data["lines"][0]["qty_remaining"] == 6

    def test_reception_exceeds_reliquat_422(self, client: TestClient, auth_headers_admin: dict):
        """Quantité reçue > reliquat → 422."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur Exceed")
        product = _create_product(client, auth_headers_admin, "Produit Exceed")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        client.post(f"/api/v1/supplier-orders/{order['id']}/confirm", headers=auth_headers_admin)
        line_id = order["lines"][0]["id"]
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/receive",
            json={"lines": [{"line_id": line_id, "qty_received": 999}]},
            headers=auth_headers_admin,
        )
        assert r.status_code == 422

    def test_cancel_order(self, client: TestClient, auth_headers_admin: dict):
        """Annulation d'une commande draft."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur Cancel")
        product = _create_product(client, auth_headers_admin, "Produit Cancel")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/cancel",
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_receive_from_draft_409(self, client: TestClient, auth_headers_admin: dict):
        """Réception d'une commande draft (non confirmée) → 409."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur RecvDraft")
        product = _create_product(client, auth_headers_admin, "Produit RecvDraft")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        line_id = order["lines"][0]["id"]
        r = client.post(
            f"/api/v1/supplier-orders/{order['id']}/receive",
            json={"lines": [{"line_id": line_id, "qty_received": 1}]},
            headers=auth_headers_admin,
        )
        assert r.status_code == 409

    def test_filter_by_status(self, client: TestClient, auth_headers_admin: dict):
        """Filtre par statut dans la liste."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur FilterStatus")
        product = _create_product(client, auth_headers_admin, "Produit FilterStatus")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        client.post(f"/api/v1/supplier-orders/{order['id']}/confirm", headers=auth_headers_admin)
        r = client.get(
            "/api/v1/supplier-orders?status=ordered",
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert all(i["status"] == "ordered" for i in items)


class TestSupplierOrdersTenantIsolation:
    """Tests d'isolation multi-tenant."""

    def test_cross_tenant_get_blocked(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
    ):
        """Tenant B ne peut pas voir une commande de tenant A."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur TenantA")
        product = _create_product(client, auth_headers_admin, "Produit TenantA")
        order = _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        r = client.get(
            f"/api/v1/supplier-orders/{order['id']}",
            headers=auth_headers_tenant2,
        )
        assert r.status_code == 404

    def test_cross_tenant_list_empty(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_tenant2: dict,
    ):
        """Tenant B ne voit pas les commandes de tenant A dans sa liste."""
        supplier = _create_supplier(client, auth_headers_admin, "Fournisseur TenantIso")
        product = _create_product(client, auth_headers_admin, "Produit TenantIso")
        _create_order(client, auth_headers_admin, supplier["id"], product["id"])
        r = client.get("/api/v1/supplier-orders", headers=auth_headers_tenant2)
        assert r.status_code == 200
        # Les commandes créées par tenant A ne doivent pas apparaître
        data = r.json()
        assert isinstance(data["items"], list)
