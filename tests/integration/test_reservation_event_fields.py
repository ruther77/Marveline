"""Tests pour les champs event_type, event_name, guest_count sur Reservation."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.constants import CustomerType, ProductCategory, ProductCondition

TODAY = date.today()
EVENT = str(TODAY + timedelta(days=15))
DELIVERY = str(TODAY + timedelta(days=14))
RETURN = str(TODAY + timedelta(days=16))


@pytest.fixture
def customer_h(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Event",
        email="alice.event@example.com",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def product_h(test_db):
    p = Product(
        tenant_id=1,
        name="Chaise event H",
        sku="CHAIR-H-001",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=500,
        deposit_amount_cents=1000,
        stock_quantity=50,
        available_quantity=50,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(p)
    test_db.commit()
    test_db.refresh(p)
    return p


@pytest.fixture
def variant_h(test_db, product_h):
    v = ProductVariant(
        tenant_id=1,
        product_id=product_h.id,
        label="Standard",
        sku=f"STD-{product_h.id}",
        price_per_day_cents=product_h.price_per_day_cents,
        deposit_amount_cents=product_h.deposit_amount_cents,
        stock_quantity=product_h.stock_quantity,
        available_quantity=product_h.available_quantity,
        is_active=True,
    )
    test_db.add(v)
    test_db.commit()
    test_db.refresh(v)
    return v


def _payload(customer_id, product_id, variant_id, **kwargs):
    base = {
        "customer_id": customer_id,
        "event_date": EVENT,
        "delivery_date": DELIVERY,
        "return_date": RETURN,
        "lines": [{"product_id": product_id, "variant_id": variant_id, "quantity": 5}],
    }
    base.update(kwargs)
    return base


def test_create_reservation_with_event_type(
    client: TestClient, auth_headers_real, customer_h, product_h, variant_h
):
    """Création avec event_type/event_name/guest_count → stockés et retournés."""
    payload = _payload(
        customer_h.id, product_h.id, variant_h.id,
        event_type="mariage",
        event_name="Mariage Dupont",
        guest_count=120,
    )
    resp = client.post("/api/v1/reservations", json=payload, headers=auth_headers_real)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["event_type"] == "mariage"
    assert data["event_name"] == "Mariage Dupont"
    assert data["guest_count"] == 120


def test_create_reservation_without_event_type(
    client: TestClient, auth_headers_real, customer_h, product_h, variant_h
):
    """Création sans event_type → null, pas d'erreur."""
    payload = _payload(customer_h.id, product_h.id, variant_h.id)
    resp = client.post("/api/v1/reservations", json=payload, headers=auth_headers_real)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["event_type"] is None
    assert data["event_name"] is None
    assert data["guest_count"] is None


def test_create_reservation_negative_guest_count(
    client: TestClient, auth_headers_real, customer_h, product_h, variant_h
):
    """guest_count négatif → 422."""
    payload = _payload(customer_h.id, product_h.id, variant_h.id, guest_count=-5)
    resp = client.post("/api/v1/reservations", json=payload, headers=auth_headers_real)
    assert resp.status_code == 422


def test_create_reservation_zero_guest_count(
    client: TestClient, auth_headers_real, customer_h, product_h, variant_h
):
    """guest_count = 0 → 422 (doit être > 0)."""
    payload = _payload(customer_h.id, product_h.id, variant_h.id, guest_count=0)
    resp = client.post("/api/v1/reservations", json=payload, headers=auth_headers_real)
    assert resp.status_code == 422


def test_update_reservation_event_fields(
    client: TestClient, auth_headers_real, customer_h, product_h, variant_h
):
    """PATCH met à jour event_type/event_name/guest_count."""
    payload = _payload(customer_h.id, product_h.id, variant_h.id)
    create_resp = client.post("/api/v1/reservations", json=payload, headers=auth_headers_real)
    assert create_resp.status_code == 201
    res_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/reservations/{res_id}",
        json={"event_type": "anniversaire", "event_name": "30 ans Marie", "guest_count": 50},
        headers=auth_headers_real,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    data = patch_resp.json()
    assert data["event_type"] == "anniversaire"
    assert data["event_name"] == "30 ans Marie"
    assert data["guest_count"] == 50


def test_event_fields_tenant_isolation(
    client: TestClient, auth_headers_real, auth_headers_tenant2, customer_h, product_h, variant_h
):
    """Tenant2 ne peut pas lire la réservation de tenant1."""
    payload = _payload(customer_h.id, product_h.id, variant_h.id, event_type="entreprise")
    create_resp = client.post("/api/v1/reservations", json=payload, headers=auth_headers_real)
    assert create_resp.status_code == 201
    res_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v1/reservations/{res_id}", headers=auth_headers_tenant2)
    assert get_resp.status_code == 404
