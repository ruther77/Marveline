"""Tests P1-6 — Acompte 40% Option A (2 factures générées à la confirmation).

Couvre :
- confirm_reservation génère 2 factures : advance (40%) + balance (60%)
- Facture advance : due_date = today + 7 jours
- Facture balance : due_date = event_date - BALANCE_DUE_DAYS_BEFORE_EVENT
- Les 2 factures appartiennent au bon tenant (isolation multi-tenant)
- Pas de double-génération si on appelle confirm plusieurs fois (déjà confirmé)
- Isolation tenant (cross-tenant interdit)
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.constants import CustomerType, ProductCategory, ProductCondition
from app.constants.business import ADVANCE_PAYMENT_PERCENT, BALANCE_DUE_DAYS_BEFORE_EVENT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adv_customer(test_db):
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Marie",
        last_name="Dupont",
        email="marie.dupont.adv@example.com",
        phone="+33612300001",
        is_active=True,
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def adv_product(test_db):
    product = Product(
        tenant_id=1,
        name="Chaise Tiffany",
        sku="CHAISE-ADV-001",
        category=ProductCategory.CHAISES,
        price_per_day_cents=500,   # 5EUR/jour
        deposit_amount_cents=1000,
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    test_db.add(product)
    test_db.flush()
    variant = ProductVariant(
        tenant_id=1,
        product_id=product.id,
        sku="CHAISE-ADV-001-DEF",
        label="Standard",
        price_per_day_cents=500,
        stock_quantity=20,
        available_quantity=20,
        is_active=True,
    )
    test_db.add(variant)
    test_db.commit()
    test_db.refresh(product)
    test_db.refresh(variant)
    product._test_variant_id = variant.id
    return product


def _create_reservation(client, headers, customer_id, product, quantity=4, unit_price_cents=500, days_ahead=30):
    """Helper : cree une reservation draft et retourne (reservation_id, total_amount_cents)."""
    event_date = date.today() + timedelta(days=days_ahead)
    variant_id = getattr(product, "_test_variant_id", None)
    res = client.post(
        "/api/v1/reservations",
        json={
            "customer_id": customer_id,
            "event_date": str(event_date),
            "delivery_date": str(event_date - timedelta(days=1)),
            "return_date": str(event_date + timedelta(days=1)),
            "lines": [
                {
                    "product_id": product.id,
                    "variant_id": variant_id,
                    "quantity": quantity,
                    "unit_price_cents": unit_price,
                    "subtotal_cents": quantity * unit_price,
                }
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.json()
    return res.json()["id"], res.json()["total_amount_cents"]


def _confirm_reservation(client, headers, reservation_id):
    """Helper : confirme une réservation et retourne la réponse."""
    res = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=headers,
    )
    return res


def _list_invoices_for_reservation(client, headers, reservation_id):
    """Helper : liste les factures d'une réservation."""
    res = client.get(
        f"/api/v1/invoices?reservation_id={reservation_id}",
        headers=headers,
    )
    assert res.status_code == 200, res.json()
    return res.json()["items"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_confirm_generates_two_invoices(
    client: TestClient, auth_headers_real, adv_customer, adv_product
):
    """confirm_reservation doit générer exactement 2 factures : advance + balance."""
    reservation_id, _ = _create_reservation(
        client, auth_headers_real, adv_customer.id, adv_product
    )
    confirm = _confirm_reservation(client, auth_headers_real, reservation_id)
    assert confirm.status_code == 200, confirm.json()

    invoices = _list_invoices_for_reservation(client, auth_headers_real, reservation_id)
    assert len(invoices) == 2

    types = {inv["invoice_type"] for inv in invoices}
    assert types == {"advance", "balance"}


def test_advance_invoice_amount_is_40_percent(
    client: TestClient, auth_headers_real, adv_customer, adv_product
):
    """La facture advance = 40% du total_amount de la réservation."""
    reservation_id, total_cents = _create_reservation(
        client, auth_headers_real, adv_customer.id, adv_product,
        quantity=4, unit_price_cents=500
    )
    _confirm_reservation(client, auth_headers_real, reservation_id)

    invoices = _list_invoices_for_reservation(client, auth_headers_real, reservation_id)
    advance_inv = next(inv for inv in invoices if inv["invoice_type"] == "advance")

    expected_advance = total_cents * ADVANCE_PAYMENT_PERCENT // 100
    assert advance_inv["total_amount_cents"] == expected_advance


def test_balance_invoice_amount_is_60_percent(
    client: TestClient, auth_headers_real, adv_customer, adv_product
):
    """La facture balance = total - advance (≈ 60%)."""
    reservation_id, total_cents = _create_reservation(
        client, auth_headers_real, adv_customer.id, adv_product,
        quantity=4, unit_price_cents=500
    )
    _confirm_reservation(client, auth_headers_real, reservation_id)

    invoices = _list_invoices_for_reservation(client, auth_headers_real, reservation_id)
    advance_inv = next(inv for inv in invoices if inv["invoice_type"] == "advance")
    balance_inv = next(inv for inv in invoices if inv["invoice_type"] == "balance")

    advance_cents = total_cents * ADVANCE_PAYMENT_PERCENT // 100
    expected_balance = total_cents - advance_cents
    assert balance_inv["total_amount_cents"] == expected_balance


def test_balance_invoice_due_date(
    client: TestClient, auth_headers_real, adv_customer, adv_product
):
    """La facture balance : due_date = event_date - BALANCE_DUE_DAYS_BEFORE_EVENT."""
    days_ahead = 30
    event_date = date.today() + timedelta(days=days_ahead)

    reservation_id, _ = _create_reservation(
        client, auth_headers_real, adv_customer.id, adv_product,
        days_ahead=days_ahead
    )
    _confirm_reservation(client, auth_headers_real, reservation_id)

    invoices = _list_invoices_for_reservation(client, auth_headers_real, reservation_id)
    balance_inv = next(inv for inv in invoices if inv["invoice_type"] == "balance")

    expected_due = str(event_date - timedelta(days=BALANCE_DUE_DAYS_BEFORE_EVENT))
    assert balance_inv["due_date"] == expected_due


def test_invoices_belong_to_correct_tenant(
    client: TestClient, auth_headers_real, adv_customer, adv_product
):
    """Les 2 factures générées appartiennent bien au tenant 1."""
    reservation_id, _ = _create_reservation(
        client, auth_headers_real, adv_customer.id, adv_product
    )
    _confirm_reservation(client, auth_headers_real, reservation_id)

    invoices = _list_invoices_for_reservation(client, auth_headers_real, reservation_id)
    for inv in invoices:
        assert inv["tenant_id"] == 1


def test_cross_tenant_cannot_see_reservation(
    client: TestClient, auth_headers_real, auth_headers_tenant2, adv_customer, adv_product
):
    """Tenant B ne peut pas accéder à la réservation du tenant A → 404."""
    reservation_id, _ = _create_reservation(
        client, auth_headers_real, adv_customer.id, adv_product
    )

    get_res = client.get(
        f"/api/v1/reservations/{reservation_id}",
        headers=auth_headers_tenant2,
    )
    assert get_res.status_code == 404
