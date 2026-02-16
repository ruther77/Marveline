"""Tests d'intégration : workflow Reservation → Invoice (auto-facturation).

Couvre :
- Confirmation d'une réservation auto-crée une Invoice (draft)
- Montants et dates de la facture auto-générée corrects
- Facture accessible via GET /invoices?reservation_id=X
- Idempotence : confirmer 2x ne crée pas de doublon
- Cross-tenant isolation : facture non visible par autre tenant
- Annulation réservation ne supprime pas la facture
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.models.product import Product
from app.constants import CustomerType, ProductCategory, ProductCondition


# ============================================================
# Fixtures spécifiques au workflow reservation → invoice
# ============================================================

@pytest.fixture
def customer_workflow(test_db):
    """Client de test pour workflow reservation → invoice."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Marie",
        last_name="Dupont",
        email="marie.dupont@workflow.com",
        phone="+33699887766",
        city="Lyon",
        postal_code="69001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def product_workflow(test_db):
    """Produit de test pour workflow reservation → invoice."""
    product = Product(
        tenant_id=1,
        name="Nappe blanche 240cm",
        sku="NAPPE-WF-001",
        category=ProductCategory.NAPPES,
        price_per_day=1500,  # 15€/jour
        deposit_amount=3000,  # 30€ caution
        stock_quantity=20,
        available_quantity=20,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


@pytest.fixture
def customer_tenant2(test_db):
    """Client de test pour tenant 2 (cross-tenant)."""
    customer = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Jean",
        last_name="Martin",
        email="jean.martin@tenant2.com",
        phone="+33688776655",
        city="Marseille",
        postal_code="13001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def product_tenant2(test_db):
    """Produit de test pour tenant 2 (cross-tenant)."""
    product = Product(
        tenant_id=2,
        name="Chaise dorée",
        sku="CHAISE-T2-001",
        category=ProductCategory.MOBILIER,
        price_per_day=2500,  # 25€/jour
        deposit_amount=5000,  # 50€ caution
        stock_quantity=15,
        available_quantity=15,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


def _create_reservation(client, customer_id, product_id, headers, quantity=3):
    """Helper : crée une réservation draft via API."""
    reservation_data = {
        "customer_id": customer_id,
        "event_date": str(date.today() + timedelta(days=10)),
        "delivery_date": str(date.today() + timedelta(days=9)),
        "return_date": str(date.today() + timedelta(days=11)),
        "event_location": "Salle des fêtes Lyon",
        "lines": [
            {
                "product_id": product_id,
                "quantity": quantity
            }
        ]
    }
    resp = client.post("/api/v1/reservations", json=reservation_data, headers=headers)
    assert resp.status_code == 201, f"Create reservation failed: {resp.json()}"
    return resp.json()


def _confirm_reservation(client, reservation_id, headers):
    """Helper : confirme une réservation via API."""
    resp = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=headers
    )
    return resp


# ============================================================
# Test : confirmation auto-crée une facture
# ============================================================

class TestConfirmCreatesInvoice:
    """Confirmer une réservation auto-génère une facture draft."""

    def test_confirm_creates_invoice(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow, auth_headers_real
    ):
        """POST /reservations/{id}/confirm → Invoice créée automatiquement."""
        # Créer réservation
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        reservation_id = res_data["id"]

        # Confirmer
        confirm_resp = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == "confirmed"

        # Vérifier facture créée via GET /invoices?reservation_id=X
        invoices_resp = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real
        )
        assert invoices_resp.status_code == 200
        invoices = invoices_resp.json()
        assert invoices["total"] == 1, "Une facture doit être auto-générée"

        invoice = invoices["items"][0]
        assert invoice["status"] == "draft"
        assert invoice["invoice_number"].startswith("INV-")

    def test_invoice_amounts_match_reservation(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow, auth_headers_real
    ):
        """La facture auto-générée a le bon total_amount (copié de la réservation)."""
        # Créer réservation avec 3 nappes × 15€/jour × 3 jours = 13500 centimes
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id,
            auth_headers_real, quantity=3
        )
        reservation_id = res_data["id"]
        reservation_total = res_data["total_amount_cents"]

        # Confirmer
        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Vérifier montant facture
        invoices_resp = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real
        )
        invoice = invoices_resp.json()["items"][0]
        assert invoice["total_amount_cents"] == reservation_total

    def test_invoice_dates(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow, auth_headers_real
    ):
        """issue_date = today, due_date = event_date de la réservation."""
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        reservation_id = res_data["id"]
        event_date = res_data["event_date"]

        # Confirmer
        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Vérifier dates facture
        invoices_resp = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real
        )
        invoice = invoices_resp.json()["items"][0]
        assert invoice["issue_date"] == str(date.today())
        assert invoice["due_date"] == event_date


# ============================================================
# Test : idempotence (confirmer 2x ne duplique pas)
# ============================================================

class TestIdempotence:
    """Confirmer une réservation déjà confirmée ne crée pas de doublon."""

    def test_confirm_already_confirmed_returns_400(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow, auth_headers_real
    ):
        """Confirmer une réservation déjà confirmée → 400."""
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        reservation_id = res_data["id"]

        # Première confirmation → OK
        resp1 = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert resp1.status_code == 200

        # Deuxième confirmation → 400 (status != draft)
        resp2 = _confirm_reservation(client, reservation_id, auth_headers_real)
        assert resp2.status_code == 400

    def test_single_invoice_per_reservation(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow, auth_headers_real
    ):
        """Une seule facture existe après confirmation (pas de doublon)."""
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        reservation_id = res_data["id"]

        # Confirmer
        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Vérifier qu'il n'y a qu'une seule facture
        invoices_resp = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real
        )
        assert invoices_resp.json()["total"] == 1


# ============================================================
# Test : cross-tenant isolation
# ============================================================

class TestCrossTenantIsolation:
    """Les factures auto-générées respectent l'isolation tenant."""

    def test_tenant2_cannot_see_tenant1_invoice(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow,
        customer_tenant2, product_tenant2,
        auth_headers_real, auth_headers_tenant2
    ):
        """Tenant2 ne voit pas la facture auto-générée pour tenant1."""
        # Tenant1 : créer et confirmer réservation
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        reservation_id = res_data["id"]
        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Tenant1 voit sa facture
        invoices_t1 = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real
        )
        assert invoices_t1.json()["total"] == 1

        # Tenant2 ne voit PAS la facture de tenant1
        invoices_t2 = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_tenant2
        )
        assert invoices_t2.json()["total"] == 0

    def test_both_tenants_get_own_invoices(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow,
        customer_tenant2, product_tenant2,
        auth_headers_real, auth_headers_tenant2
    ):
        """Chaque tenant voit uniquement ses propres factures."""
        # Tenant1 : créer et confirmer
        res1 = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        _confirm_reservation(client, res1["id"], auth_headers_real)

        # Tenant2 : créer et confirmer
        res2 = _create_reservation(
            client, customer_tenant2.id, product_tenant2.id, auth_headers_tenant2
        )
        _confirm_reservation(client, res2["id"], auth_headers_tenant2)

        # Chaque tenant voit 1 facture (la sienne)
        invoices_t1 = client.get(
            "/api/v1/invoices",
            headers=auth_headers_real
        )
        invoices_t2 = client.get(
            "/api/v1/invoices",
            headers=auth_headers_tenant2
        )

        ids_t1 = {inv["id"] for inv in invoices_t1.json()["items"]}
        ids_t2 = {inv["id"] for inv in invoices_t2.json()["items"]}
        assert ids_t1.isdisjoint(ids_t2), "Invoice IDs must not overlap between tenants"


# ============================================================
# Test : annulation ne supprime pas la facture
# ============================================================

class TestCancelPreservesInvoice:
    """Annuler une réservation confirmée ne supprime pas la facture."""

    def test_cancel_after_confirm_keeps_invoice(
        self, client: TestClient, test_db,
        customer_workflow, product_workflow, auth_headers_real
    ):
        """Annuler réservation confirmée → facture existe toujours."""
        # Créer et confirmer
        res_data = _create_reservation(
            client, customer_workflow.id, product_workflow.id, auth_headers_real
        )
        reservation_id = res_data["id"]
        _confirm_reservation(client, reservation_id, auth_headers_real)

        # Annuler
        cancel_resp = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            headers=auth_headers_real
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # La facture existe toujours
        invoices_resp = client.get(
            f"/api/v1/invoices?reservation_id={reservation_id}",
            headers=auth_headers_real
        )
        assert invoices_resp.json()["total"] == 1
        assert invoices_resp.json()["items"][0]["status"] == "draft"
