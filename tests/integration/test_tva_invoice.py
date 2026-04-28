"""Tests P2-19 — TVA Option A (taux capturé sur Invoice).

Couvre :
- generate_from_reservation calcule tva_amount_cents (total_ht * tva_rate)
- generate_from_reservation calcule total_ttc_cents (total_ht + tva_amount_cents)
- tva_rate capturé depuis TenantSettings (défaut 0.20 si absent)
- InvoiceResponse expose tva_rate, tva_amount_cents, total_ttc_cents, tva_amount_euros, total_ttc_euros
- Isolation tenant (cross-tenant interdit)
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.models.tenant_settings import TenantSettings
from app.constants import (
    CustomerType, ProductCategory, ProductCondition,
    ReservationStatus, InvoiceStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tva_customer(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Claire",
        last_name="Durand",
        email="claire.durand.tva@example.com",
        phone="+33600000099",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def tva_product(test_db):
    p = Product(
        tenant_id=1,
        name="Nappe Damassée TVA",
        sku="NAPPE-TVA-001",
        category=ProductCategory.HOUSSES,
        price_per_day_cents=200,
        deposit_amount_cents=500,
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
def confirmed_reservation_tva(test_db, tva_customer, tva_product):
    """Réservation CONFIRMED avec total_amount = 10000 centimes (HT)."""
    event_date = date.today() + timedelta(days=20)
    r = Reservation(
        tenant_id=1,
        customer_id=tva_customer.id,
        reference="RES-TVA-001",
        event_date=event_date,
        delivery_date=event_date - timedelta(days=1),
        return_date=event_date + timedelta(days=1),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,   # 100.00 € HT
        deposit_amount_cents=3000,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)

    line = ReservationLine(
        tenant_id=1,
        reservation_id=r.id,
        product_id=tva_product.id,
        quantity=5,
        unit_price_cents=200,
        subtotal_cents=1000,
    )
    test_db.add(line)
    test_db.commit()
    return r


def _create_invoice(client, headers, reservation_id):
    """Helper : crée une facture depuis une réservation, retourne la réponse."""
    event_date = date.today() + timedelta(days=20)
    return client.post(
        "/api/v1/invoices",
        json={
            "reservation_id": reservation_id,
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=14)),
        },
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_invoice_has_tva_fields(
    client: TestClient, auth_headers_real, confirmed_reservation_tva
):
    """InvoiceResponse expose tva_rate, tva_amount_cents, total_ttc_cents."""
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    assert "tva_rate" in data
    assert "tva_amount_cents" in data
    assert "total_ttc_cents" in data
    assert "tva_amount_euros" in data
    assert "total_ttc_euros" in data


def test_invoice_tva_calculation_default_rate(
    client: TestClient, auth_headers_real, confirmed_reservation_tva
):
    """TVA calculée correctement avec le taux par défaut (20%)."""
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    total_ht = data["total_amount_cents"]
    tva_rate = data["tva_rate"]
    assert tva_rate is not None

    expected_tva = int(total_ht * tva_rate)
    assert data["tva_amount_cents"] == expected_tva
    assert data["total_ttc_cents"] == total_ht + expected_tva


def test_invoice_ttc_coherence(
    client: TestClient, auth_headers_real, confirmed_reservation_tva
):
    """total_ttc_cents = total_amount_cents + tva_amount_cents."""
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    assert data["total_ttc_cents"] == data["total_amount_cents"] + data["tva_amount_cents"]


def test_invoice_tva_euros_conversion(
    client: TestClient, auth_headers_real, confirmed_reservation_tva
):
    """tva_amount_euros = tva_amount_cents / 100."""
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    assert data["tva_amount_euros"] == pytest.approx(data["tva_amount_cents"] / 100, abs=0.01)
    assert data["total_ttc_euros"] == pytest.approx(data["total_ttc_cents"] / 100, abs=0.01)


def test_invoice_tva_custom_rate(
    client: TestClient, auth_headers_real, confirmed_reservation_tva, test_db
):
    """Taux TVA personnalisé via TenantSettings (5.5%) est bien capturé."""
    # Configurer TenantSettings avec un taux 5.5%
    from sqlalchemy import select
    settings = test_db.execute(
        select(TenantSettings).filter(TenantSettings.tenant_id == 1)
    ).scalar_one_or_none()

    if settings is None:
        settings = TenantSettings(tenant_id=1, vat_rate=0.055)
        test_db.add(settings)
    else:
        settings.vat_rate = 0.055
    test_db.commit()

    # Nouvelle réservation pour cet test (la précédente est déjà facturée)
    from app.models.product import Product
    event_date = date.today() + timedelta(days=25)
    r = Reservation(
        tenant_id=1,
        customer_id=confirmed_reservation_tva.customer_id,
        reference="RES-TVA-055",
        event_date=event_date,
        delivery_date=event_date - timedelta(days=1),
        return_date=event_date + timedelta(days=1),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=3000,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)

    res = _create_invoice(client, auth_headers_real, r.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    assert data["tva_rate"] == pytest.approx(0.055, abs=0.001)
    expected_tva = int(10000 * 0.055)
    assert data["tva_amount_cents"] == expected_tva
    assert data["total_ttc_cents"] == 10000 + expected_tva

    # Remettre le taux par défaut
    settings.vat_rate = 0.20
    test_db.commit()


def test_cross_tenant_cannot_see_invoice(
    client: TestClient, auth_headers_real, auth_headers_tenant2, confirmed_reservation_tva
):
    """Tenant B ne peut pas accéder à la facture de Tenant A → 404."""
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201, res.json()
    invoice_id = res.json()["id"]

    get_res = client.get(
        f"/api/v1/invoices/{invoice_id}",
        headers=auth_headers_tenant2,
    )
    assert get_res.status_code == 404


# ---------------------------------------------------------------------------
# Tests multi-taux TVA (breakdown)
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_rate_reservation(test_db, tva_customer):
    """Réservation avec 2 lignes à taux TVA différents (20% et 5.5%)."""
    p1 = Product(
        tenant_id=1,
        name="Assiette Multi-TVA 20%",
        sku="MULTI-TVA-20",
        category=ProductCategory.HOUSSES,
        price_per_day_cents=300,
        deposit_amount_cents=0,
        stock_quantity=50,
        available_quantity=50,
        condition=ProductCondition.NEUF,
        is_active=True,
        tva_rate=0.20,
    )
    p2 = Product(
        tenant_id=1,
        name="Produit Multi-TVA 5.5%",
        sku="MULTI-TVA-055",
        category=ProductCategory.HOUSSES,
        price_per_day_cents=200,
        deposit_amount_cents=0,
        stock_quantity=50,
        available_quantity=50,
        condition=ProductCondition.NEUF,
        is_active=True,
        tva_rate=0.055,
    )
    test_db.add_all([p1, p2])
    test_db.flush()

    event_date = date.today() + timedelta(days=30)
    r = Reservation(
        tenant_id=1,
        customer_id=tva_customer.id,
        reference="RES-MULTI-TVA",
        event_date=event_date,
        delivery_date=event_date - timedelta(days=1),
        return_date=event_date + timedelta(days=1),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=5000,  # 50.00 € HT
        deposit_amount_cents=0,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.flush()

    line1 = ReservationLine(
        tenant_id=1,
        reservation_id=r.id,
        product_id=p1.id,
        quantity=10,
        unit_price_cents=300,
        subtotal_cents=3000,
        tva_rate=0.20,
    )
    line2 = ReservationLine(
        tenant_id=1,
        reservation_id=r.id,
        product_id=p2.id,
        quantity=10,
        unit_price_cents=200,
        subtotal_cents=2000,
        tva_rate=0.055,
    )
    test_db.add_all([line1, line2])
    test_db.commit()
    return r


def test_invoice_tva_breakdown_multi_rate(
    client: TestClient, auth_headers_real, multi_rate_reservation
):
    """Facture avec lignes multi-taux → tva_breakdown non nul avec 2 entrées."""
    res = _create_invoice(client, auth_headers_real, multi_rate_reservation.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    assert data["tva_breakdown"] is not None, "tva_breakdown doit être non nul pour multi-taux"
    assert len(data["tva_breakdown"]) == 2, f"Attendu 2 taux, obtenu {len(data['tva_breakdown'])}"

    rates = {item["rate"] for item in data["tva_breakdown"]}
    assert 0.20 in rates
    assert 0.055 in rates


def test_invoice_tva_breakdown_structure(
    client: TestClient, auth_headers_real, multi_rate_reservation
):
    """Chaque entrée du breakdown a les champs requis."""
    res = _create_invoice(client, auth_headers_real, multi_rate_reservation.id)
    assert res.status_code == 201, res.json()
    breakdown = res.json()["tva_breakdown"]

    for item in breakdown:
        assert "rate" in item
        assert "base_ht_cents" in item
        assert "tva_cents" in item
        assert "ttc_cents" in item
        assert item["ttc_cents"] == item["base_ht_cents"] + item["tva_cents"]


def test_invoice_tva_single_rate_no_breakdown(
    client: TestClient, auth_headers_real, confirmed_reservation_tva
):
    """Facture taux unique → tva_breakdown est None (rétro-compat)."""
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201, res.json()
    data = res.json()

    # taux unique : breakdown None
    assert data["tva_breakdown"] is None


# ---------------------------------------------------------------------------
# Tests endpoint GET /invoices/tva-report
# ---------------------------------------------------------------------------

def test_tva_report_invalid_month(client: TestClient, auth_headers_real):
    """Format de mois invalide → 400."""
    res = client.get("/api/v1/invoices/tva-report?month=invalid", headers=auth_headers_real)
    assert res.status_code == 400


def test_tva_report_valid_empty(client: TestClient, auth_headers_real):
    """Mois sans factures → rapport vide mais valide."""
    res = client.get("/api/v1/invoices/tva-report?month=2000-01", headers=auth_headers_real)
    assert res.status_code == 200, res.json()
    data = res.json()

    assert data["month"] == "2000-01"
    assert data["invoice_count"] == 0
    assert data["total_base_ht_cents"] == 0
    assert data["total_tva_cents"] == 0
    assert data["total_ttc_cents"] == 0
    assert data["breakdown_by_rate"] == []


def test_tva_report_structure(client: TestClient, auth_headers_real):
    """La réponse expose les champs euros calculés."""
    res = client.get("/api/v1/invoices/tva-report?month=2000-01", headers=auth_headers_real)
    assert res.status_code == 200
    data = res.json()

    assert "total_base_ht_euros" in data
    assert "total_tva_euros" in data
    assert "total_ttc_euros" in data


# ---------------------------------------------------------------------------
# Tests endpoint GET /invoices/payments (global tenant)
# ---------------------------------------------------------------------------

def test_list_all_payments_empty(client: TestClient, auth_headers_real):
    """Sans paiement → liste vide."""
    res = client.get("/api/v1/invoices/payments", headers=auth_headers_real)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_list_all_payments_cross_tenant(
    client: TestClient, auth_headers_tenant2, confirmed_reservation_tva, auth_headers_real, test_db
):
    """Tenant B ne voit pas les paiements de Tenant A."""
    # Créer une facture + paiement pour tenant 1
    res = _create_invoice(client, auth_headers_real, confirmed_reservation_tva.id)
    assert res.status_code == 201
    invoice_id = res.json()["id"]

    pay_res = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={
            "amount_cents": 1000,
            "payment_method": "cash",
            "payment_date": str(date.today()),
        },
        headers=auth_headers_real,
    )
    assert pay_res.status_code == 201

    # Tenant 2 ne doit pas voir ce paiement
    res2 = client.get("/api/v1/invoices/payments", headers=auth_headers_tenant2)
    assert res2.status_code == 200
    # Les paiements de tenant 2 ne contiennent pas ceux de tenant 1
    payment_ids = [p["id"] for p in res2.json()]
    assert pay_res.json()["id"] not in payment_ids
