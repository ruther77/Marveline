"""Tests d'intégration — Endpoint /orders (liste unifiée commandes).

Couvre :
  - GET /orders           : liste paginée, filtres status / order_type
  - GET /orders/{type}/{id}: détail complet
  - Isolation cross-tenant
"""
import pytest
from datetime import date, timedelta

from app.models.customer import Customer
from app.models.devis import Devis
from app.models.reservation import Reservation
from app.models.vente import Vente
from app.constants import CustomerType


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def customer_t1(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Orders",
        email="alice.orders@test.com",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def customer_t2(test_db):
    c = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bob",
        last_name="T2",
        email="bob.t2@test.com",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def devis_t1(test_db, customer_t1):
    d = Devis(
        tenant_id=1,
        reference="DEV-2026-0001",
        customer_id=customer_t1.id,
        status="draft",
        valid_until=date.today() + timedelta(days=30),
        tva_rate=2000,
        subtotal_cents=50000,
        total_cents=60000,
    )
    test_db.add(d)
    test_db.commit()
    test_db.refresh(d)
    return d


@pytest.fixture
def reservation_t1(test_db, customer_t1):
    r = Reservation(
        tenant_id=1,
        reference="RES-2026-0001",
        customer_id=customer_t1.id,
        status="confirmed",
        delivery_date=date.today() + timedelta(days=7),
        event_date=date.today() + timedelta(days=8),
        return_date=date.today() + timedelta(days=9),
        total_amount_cents=80000,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


@pytest.fixture
def vente_t1(test_db, customer_t1):
    v = Vente(
        tenant_id=1,
        reference="VTE-2026-0001",
        customer_id=customer_t1.id,
        status="pending",
        subtotal_cents=30000,
        total_cents=36000,
    )
    test_db.add(v)
    test_db.commit()
    test_db.refresh(v)
    return v


@pytest.fixture
def devis_t2(test_db, customer_t2):
    d = Devis(
        tenant_id=2,
        reference="DEV-2026-T2-0001",
        customer_id=customer_t2.id,
        status="sent",
        valid_until=date.today() + timedelta(days=30),
        tva_rate=2000,
        subtotal_cents=99000,
        total_cents=118800,
    )
    test_db.add(d)
    test_db.commit()
    test_db.refresh(d)
    return d


# ─── Tests GET /orders ────────────────────────────────────────────────────────

class TestListOrders:
    def test_liste_paginee_vide(self, client, auth_headers_admin):
        resp = client.get("/api/v1/orders", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0
        assert data["items"] == []

    def test_liste_retourne_toutes_commandes(
        self, client, auth_headers_admin, devis_t1, reservation_t1, vente_t1
    ):
        resp = client.get("/api/v1/orders", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        types = {item["type"] for item in data["items"]}
        assert types == {"devis", "reservation", "vente"}

    def test_filtre_order_type_devis(
        self, client, auth_headers_admin, devis_t1, reservation_t1, vente_t1
    ):
        resp = client.get("/api/v1/orders?order_type=devis", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "devis"
        assert data["items"][0]["reference"] == "DEV-2026-0001"

    def test_filtre_order_type_reservation(
        self, client, auth_headers_admin, devis_t1, reservation_t1, vente_t1
    ):
        resp = client.get("/api/v1/orders?order_type=reservation", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "reservation"

    def test_filtre_order_type_vente(
        self, client, auth_headers_admin, devis_t1, reservation_t1, vente_t1
    ):
        resp = client.get("/api/v1/orders?order_type=vente", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "vente"

    def test_filtre_status_confirmed(
        self, client, auth_headers_admin, devis_t1, reservation_t1, vente_t1
    ):
        resp = client.get("/api/v1/orders?status=confirmed", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        # reservation=confirmed (map → confirmed), devis=draft (→draft), vente=pending (→confirmed)
        confirmed = [i for i in data["items"] if i["status"] == "confirmed"]
        assert len(confirmed) >= 1

    def test_pagination_skip_limit(
        self, client, auth_headers_admin, devis_t1, reservation_t1, vente_t1
    ):
        resp = client.get("/api/v1/orders?skip=0&limit=2", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["skip"] == 0
        assert data["limit"] == 2

    def test_order_type_invalide_ignoré(
        self, client, auth_headers_admin, devis_t1
    ):
        # order_type hors ("devis","reservation","vente") → 0 résultats (aucune branche active)
        resp = client.get("/api/v1/orders?order_type=unknown", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_non_authentifie(self, client):
        resp = client.get("/api/v1/orders")
        assert resp.status_code == 401


# ─── Tests GET /orders/{order_type}/{order_id} ────────────────────────────────

class TestGetOrderDetail:
    # Tests sans fixtures data — exécutés en premier pour éviter lock contention async
    def test_detail_order_type_invalide(self, client, auth_headers_admin):
        resp = client.get("/api/v1/orders/facture/1", headers=auth_headers_admin)
        assert resp.status_code == 422

    def test_detail_404_inconnu(self, client, auth_headers_admin):
        resp = client.get("/api/v1/orders/devis/99999", headers=auth_headers_admin)
        assert resp.status_code == 404

    # Tests avec fixtures data — exécutés après
    def test_detail_devis(self, client, auth_headers_admin, devis_t1):
        resp = client.get(f"/api/v1/orders/devis/{devis_t1.id}", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == devis_t1.id
        assert data["type"] == "devis"
        assert data["reference"] == "DEV-2026-0001"
        assert data["native_status"] == "draft"
        assert "actions" in data
        assert "lines" in data

    def test_detail_reservation(self, client, auth_headers_admin, reservation_t1):
        resp = client.get(
            f"/api/v1/orders/reservation/{reservation_t1.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == reservation_t1.id
        assert data["type"] == "reservation"
        assert data["native_status"] == "confirmed"
        assert "confirm" in data["actions"] or "departure" in data["actions"]

    def test_detail_vente(self, client, auth_headers_admin, vente_t1):
        resp = client.get(f"/api/v1/orders/vente/{vente_t1.id}", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == vente_t1.id
        assert data["type"] == "vente"
        assert data["native_status"] == "pending"


# ─── Tests isolation cross-tenant ─────────────────────────────────────────────

class TestOrdersCrossTenantIsolation:
    def test_tenant1_ne_voit_pas_devis_tenant2(
        self, client, auth_headers_admin, devis_t2
    ):
        """Un admin tenant_id=1 ne doit pas voir les commandes tenant_id=2."""
        resp = client.get("/api/v1/orders", headers=auth_headers_admin)
        assert resp.status_code == 200
        data = resp.json()
        refs = [item["reference"] for item in data["items"]]
        assert "DEV-2026-T2-0001" not in refs

    def test_detail_cross_tenant_retourne_404(
        self, client, auth_headers_admin, devis_t2
    ):
        """Accès au détail d'une commande d'un autre tenant → 404."""
        resp = client.get(
            f"/api/v1/orders/devis/{devis_t2.id}",
            headers=auth_headers_admin,
        )
        assert resp.status_code == 404
