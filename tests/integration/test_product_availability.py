"""Tests d'intégration — GET /products/{id}/availability."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.product import Product
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationLine
from app.constants import ProductCategory, ProductCondition, CustomerType


# ── Fixtures ──────────────────────────────────────────────────────────────────

def avail_product_fixture(test_db):
    product = Product(
        tenant_id=1,
        name="Chaise thonet",
        sku="CHAISE-THONET-AV",
        category=ProductCategory.NAPPES,
        price_per_day_cents=500,
        deposit_amount_cents=2000,
        stock_quantity=5,
        available_quantity=5,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


import pytest

@pytest.fixture
def avail_product(test_db):
    return avail_product_fixture(test_db)


@pytest.fixture
def avail_customer(test_db):
    customer = Customer(
        tenant_id=1,
        first_name="Alice",
        last_name="Martin",
        email="alice.avail@test.com",
        customer_type=CustomerType.INDIVIDUAL,
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


def _make_reservation(db, product, customer, delivery: date, return_d: date, status: str, qty: int = 2):
    res = Reservation(
        tenant_id=1,
        reference=f"RES-AV-{delivery.isoformat()}-{status}",
        customer_id=customer.id,
        event_date=delivery + timedelta(days=1),
        delivery_date=delivery,
        return_date=return_d,
        status=status,
        total_amount_cents=qty * 500,
    )
    db.add(res)
    db.flush()
    line = ReservationLine(
        tenant_id=1,
        reservation_id=res.id,
        product_id=product.id,
        quantity=qty,
        unit_price_cents=500,
        subtotal_cents=qty * 500,
    )
    db.add(line)
    db.commit()
    return res


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_availability_empty_range(client: TestClient, avail_product, auth_headers_real):
    """Aucune réservation → busy_slots vide."""
    url = f"/api/v1/products/{avail_product.id}/availability?date_from=2030-01-01&date_to=2030-01-31"
    resp = client.get(url, headers=auth_headers_real)
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == avail_product.id
    assert data["total_quantity"] == avail_product.stock_quantity
    assert data["busy_slots"] == []


def test_availability_confirmed_reservation_appears(
    client: TestClient, avail_product, avail_customer, test_db, auth_headers_real
):
    """Réservation confirmée → apparaît dans busy_slots."""
    _make_reservation(
        test_db, avail_product, avail_customer,
        delivery=date(2030, 3, 5),
        return_d=date(2030, 3, 10),
        status="confirmed",
        qty=3,
    )
    url = f"/api/v1/products/{avail_product.id}/availability?date_from=2030-03-01&date_to=2030-03-31"
    resp = client.get(url, headers=auth_headers_real)
    assert resp.status_code == 200
    slots = resp.json()["busy_slots"]
    assert len(slots) == 1
    assert slots[0]["reserved_quantity"] == 3
    assert slots[0]["date_from"] == "2030-03-05"
    assert slots[0]["date_to"] == "2030-03-10"


def test_availability_active_statuses_included(
    client: TestClient, avail_product, avail_customer, test_db, auth_headers_real
):
    """Statuts actifs (pre_check, confirmed_risk, delivered, extended) → inclus."""
    for status in ("pre_check", "confirmed_risk", "delivered", "extended"):
        _make_reservation(
            test_db, avail_product, avail_customer,
            delivery=date(2031, 4, 1),
            return_d=date(2031, 4, 5),
            status=status,
            qty=1,
        )
    url = f"/api/v1/products/{avail_product.id}/availability?date_from=2031-04-01&date_to=2031-04-30"
    resp = client.get(url, headers=auth_headers_real)
    assert resp.status_code == 200
    assert len(resp.json()["busy_slots"]) == 4


def test_availability_inactive_statuses_excluded(
    client: TestClient, avail_product, avail_customer, test_db, auth_headers_real
):
    """Statuts inactifs (draft, cancelled, returned) → exclus."""
    for status in ("draft", "cancelled", "returned", "returned_dispute"):
        _make_reservation(
            test_db, avail_product, avail_customer,
            delivery=date(2032, 5, 1),
            return_d=date(2032, 5, 5),
            status=status,
            qty=1,
        )
    url = f"/api/v1/products/{avail_product.id}/availability?date_from=2032-05-01&date_to=2032-05-31"
    resp = client.get(url, headers=auth_headers_real)
    assert resp.status_code == 200
    assert resp.json()["busy_slots"] == []


def test_availability_date_validation(client: TestClient, avail_product, auth_headers_real):
    """date_to < date_from → 400."""
    url = f"/api/v1/products/{avail_product.id}/availability?date_from=2030-06-30&date_to=2030-06-01"
    resp = client.get(url, headers=auth_headers_real)
    assert resp.status_code == 400


def test_availability_cross_tenant_blocked(
    client: TestClient, avail_product, auth_headers_tenant2
):
    """Tenant 2 ne peut pas voir la disponibilité d'un produit tenant 1."""
    url = f"/api/v1/products/{avail_product.id}/availability?date_from=2030-01-01&date_to=2030-01-31"
    resp = client.get(url, headers=auth_headers_tenant2)
    assert resp.status_code == 404


def test_availability_product_not_found(client: TestClient, auth_headers_real):
    """Produit inexistant → 404."""
    resp = client.get(
        "/api/v1/products/999999/availability?date_from=2030-01-01&date_to=2030-01-31",
        headers=auth_headers_real,
    )
    assert resp.status_code == 404
