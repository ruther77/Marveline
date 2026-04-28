"""Tests intégration — Recherche globale."""
import pytest
from datetime import date as date_
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation


def _seed_data(test_db, tenant_id: int):
    """Crée des données de test pour la recherche."""
    c = Customer(
        tenant_id=tenant_id,
        customer_type="individual",
        first_name="Alice",
        last_name="Dupont",
        email="alice@example.com",
    )
    p = Product(
        tenant_id=tenant_id,
        name="Nappe Bordeaux",
        sku="NAP-BORD-001",
        description="Nappe rectangulaire bordeaux",
        category="vaisselle",
        stock_quantity=10,
        available_quantity=10,
        price_per_day_cents=500,
    )
    test_db.add(c)
    test_db.add(p)
    test_db.flush()
    test_db.commit()
    return c, p


class TestGlobalSearch:
    def test_search_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/search?q=alice")
        assert resp.status_code == 401

    def test_search_empty_results(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/search?q=zzznomatch", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["total"] == 0
        assert data["query"] == "zzznomatch"

    def test_search_finds_customer(
        self, client: TestClient, auth_headers_real: dict, test_db, test_user
    ):
        _seed_data(test_db, test_user.tenant_id)
        resp = client.get("/api/v1/search?q=Alice&types=customer", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["type"] == "customer" and "Alice" in r["title"] for r in data["results"])

    def test_search_finds_product(
        self, client: TestClient, auth_headers_real: dict, test_db, test_user
    ):
        _seed_data(test_db, test_user.tenant_id)
        resp = client.get("/api/v1/search?q=Nappe&types=product", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["type"] == "product" for r in data["results"])

    def test_search_product_url_is_catalogue_canonical(
        self, client: TestClient, auth_headers_real: dict, test_db, test_user
    ):
        """L'URL de navigation produit doit pointer vers /catalogue/products/{id} (Point 5)."""
        _, product = _seed_data(test_db, test_user.tenant_id)
        resp = client.get("/api/v1/search?q=Nappe&types=product", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        product_results = [r for r in data["results"] if r["type"] == "product"]
        assert len(product_results) >= 1
        for r in product_results:
            assert r["url"].startswith("/catalogue/products/"), (
                f"URL produit doit commencer par /catalogue/products/, reçu: {r['url']}"
            )
            assert r["url"] != "/catalogue/products/", "URL produit doit inclure l'id"

    def test_search_tenant_isolation(
        self, client: TestClient, auth_headers_real: dict, test_db
    ):
        """Les résultats d'un autre tenant ne doivent pas être visibles."""
        other_tenant_id = 9999
        c = Customer(
            tenant_id=other_tenant_id,
            customer_type="individual",
            first_name="Bob",
            last_name="Autretenant",
            email="bob@other.com",
        )
        test_db.add(c)
        test_db.commit()

        resp = client.get("/api/v1/search?q=Autretenant&types=customer", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_search_case_insensitive(
        self, client: TestClient, auth_headers_real: dict, test_db, test_user
    ):
        _seed_data(test_db, test_user.tenant_id)
        resp = client.get("/api/v1/search?q=alice&types=customer", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_search_type_filter(
        self, client: TestClient, auth_headers_real: dict, test_db, test_user
    ):
        """Filtrer sur types=customer ne retourne que des clients."""
        _seed_data(test_db, test_user.tenant_id)
        resp = client.get("/api/v1/search?q=a&types=customer", headers=auth_headers_real)
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["type"] == "customer"

    def test_search_reservation_url_canonical(
        self, client: TestClient, auth_headers_real: dict, test_db, test_user
    ):
        """L'URL réservation doit pointer vers /reservations/{id} — jamais /events (legacy)."""
        c = Customer(
            tenant_id=test_user.tenant_id,
            customer_type="individual",
            first_name="Testeur",
            last_name="Recherche",
            email="testeur.recherche.search@example.com",
        )
        test_db.add(c)
        test_db.flush()

        resa = Reservation(
            tenant_id=test_user.tenant_id,
            customer_id=c.id,
            reference="RES-TEST-URLCANON",
            event_date=date_(2026, 6, 15),
            delivery_date=date_(2026, 6, 14),
            return_date=date_(2026, 6, 16),
        )
        test_db.add(resa)
        test_db.commit()

        resp = client.get(
            "/api/v1/search?q=RES-TEST-URLCANON&types=reservation",
            headers=auth_headers_real,
        )
        assert resp.status_code == 200
        data = resp.json()
        resa_results = [r for r in data["results"] if r["type"] == "reservation"]
        assert len(resa_results) >= 1
        for r in resa_results:
            assert r["url"] == f"/reservations/{resa.id}", (
                f"URL réservation doit être /reservations/{{id}}, reçu: {r['url']}"
            )
            assert "/events" not in r["url"], (
                f"URL réservation ne doit pas contenir /events (legacy), reçu: {r['url']}"
            )
