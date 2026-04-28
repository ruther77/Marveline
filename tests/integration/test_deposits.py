"""Tests intégration — Cautions de réservations (POST/PATCH /reservations/{id}/deposit)."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.models.deposit import Deposit
from app.models.invoice import Invoice
from app.models.invoice_charge import InvoiceCharge
from app.models.product import Product
from app.models.reservation import Reservation, ReservationLine
from app.constants import (
    CustomerType, ProductCategory, ProductCondition,
    ReservationStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_dep(test_db):
    c = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Claire",
        last_name="Caution",
        email="claire.dep@example.com",
        phone="+33600000020",
        city="Bordeaux",
        postal_code="33000",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def product_dep(test_db):
    p = Product(
        tenant_id=1,
        name="Nappe Caution",
        sku="NAPPE-DEP-001",
        category=ProductCategory.DECORATIONS,
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
def reservation_dep(test_db, customer_dep, product_dep):
    """Réservation tenant_id=1, status=confirmed, pour tests caution."""
    r = Reservation(
        tenant_id=1,
        customer_id=customer_dep.id,
        reference="RES-DEP-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Salle Caution",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=8000,
        deposit_amount_cents=0,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)

    line = ReservationLine(
        tenant_id=1,
        reservation_id=r.id,
        product_id=product_dep.id,
        quantity=20,
        unit_price_cents=200,
        subtotal_cents=4000,
    )
    test_db.add(line)
    test_db.commit()
    return r


@pytest.fixture
def customer_dep_t2(test_db):
    c = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Denis",
        last_name="Tenant2",
        email="denis.dep.t2@example.com",
        phone="+33600000021",
        city="Nantes",
        postal_code="44000",
        is_active=True,
    )
    test_db.add(c)
    test_db.commit()
    test_db.refresh(c)
    return c


@pytest.fixture
def reservation_dep_t2(test_db, customer_dep_t2):
    """Réservation appartenant au tenant_id=2."""
    r = Reservation(
        tenant_id=2,
        customer_id=customer_dep_t2.id,
        reference="RES-DEP-T2-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=5000,
        deposit_amount_cents=0,
        deposit_paid=False,
    )
    test_db.add(r)
    test_db.commit()
    test_db.refresh(r)
    return r


# ---------------------------------------------------------------------------
# Tests CRUD
# ---------------------------------------------------------------------------

class TestDepositsCRUD:
    """Tests CRUD sur /reservations/{id}/deposit."""

    def test_create_deposit_returns_201(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Création caution → 201, statut initial 'held'."""
        r = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 15000},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["status"] == "held"
        assert data["amount_cents"] == 15000
        assert data["reservation_id"] == reservation_dep.id
        assert "id" in data

    def test_create_deposit_with_collection_date(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Création caution avec collection_date → champ préservé."""
        collect_date = str(date.today())
        r = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 10000, "collection_date": collect_date},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201, r.text
        assert r.json()["collection_date"] == collect_date

    def test_create_deposit_marks_deposit_paid(
        self, client: TestClient, auth_headers_admin: dict, auth_headers_real: dict, reservation_dep
    ):
        """Création caution → deposit_paid=True, deposit_amount (ref CGV) préservé."""
        client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 20000},
            headers=auth_headers_admin,
        )
        r = client.get(
            f"/api/v1/reservations/{reservation_dep.id}",
            headers=auth_headers_real,
        )
        assert r.status_code == 200
        data = r.json()
        # deposit_amount_cents = montant CGV attendu (calculé à confirmation, non écrasé)
        assert data["deposit_amount_cents"] == 0  # fixture insérée directement avec deposit_amount_cents=0
        assert data["deposit_paid"] is True

    def test_create_deposit_on_nonexistent_reservation_returns_404(
        self, client: TestClient, auth_headers_admin: dict
    ):
        """Réservation inexistante → 404."""
        r = client.post(
            "/api/v1/reservations/999999/deposit",
            json={"amount_cents": 5000},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_update_deposit_status_released(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Update statut → 'released' avec release_date."""
        # Créer d'abord la caution
        created = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 10000},
            headers=auth_headers_admin,
        ).json()
        deposit_id = created["id"]

        release_date = str(date.today() + timedelta(days=5))
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposit/{deposit_id}",
            json={"status": "released", "release_date": release_date},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "released"
        assert data["release_date"] == release_date

    def test_update_deposit_status_retained(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Update statut → 'retained' avec retained_amount_cents."""
        created = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 10000},
            headers=auth_headers_admin,
        ).json()
        deposit_id = created["id"]

        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposit/{deposit_id}",
            json={"status": "retained", "retained_amount_cents": 5000},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "retained"
        assert data["retained_amount_cents"] == 5000

    def test_update_released_requires_release_date(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Status 'released' sans release_date → 422 (validation Pydantic)."""
        created = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 10000},
            headers=auth_headers_admin,
        ).json()
        deposit_id = created["id"]

        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposit/{deposit_id}",
            json={"status": "released"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 422

    def test_update_retained_requires_retained_amount(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Status 'retained' sans retained_amount_cents → 422."""
        created = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 10000},
            headers=auth_headers_admin,
        ).json()
        deposit_id = created["id"]

        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposit/{deposit_id}",
            json={"status": "retained"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 422

    def test_update_nonexistent_deposit_returns_404(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Caution inexistante → 404."""
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposit/999999",
            json={"status": "released", "release_date": str(date.today())},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_create_deposit_with_notes(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep
    ):
        """Création caution avec notes → notes conservées."""
        r = client.post(
            f"/api/v1/reservations/{reservation_dep.id}/deposit",
            json={"amount_cents": 5000, "notes": "Chèque caution reçu"},
            headers=auth_headers_admin,
        )
        assert r.status_code == 201, r.text
        assert r.json()["notes"] == "Chèque caution reçu"


# ---------------------------------------------------------------------------
# Tests isolation tenant
# ---------------------------------------------------------------------------

class TestDepositsTenantIsolation:
    """Tests anti-cross-tenant pour les cautions."""

    def test_cannot_create_deposit_for_other_tenant_reservation(
        self, client: TestClient, auth_headers_admin: dict, reservation_dep_t2
    ):
        """Tenant 1 ne peut pas créer une caution pour réservation du tenant 2 → 404."""
        r = client.post(
            f"/api/v1/reservations/{reservation_dep_t2.id}/deposit",
            json={"amount_cents": 5000},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404

    def test_cannot_update_deposit_of_other_tenant(
        self,
        client: TestClient,
        auth_headers_admin: dict,
        auth_headers_admin_tenant2: dict,
        reservation_dep_t2,
    ):
        """Tenant 1 ne peut pas modifier une caution du tenant 2 → 404."""
        # Tenant 2 crée une caution
        created = client.post(
            f"/api/v1/reservations/{reservation_dep_t2.id}/deposit",
            json={"amount_cents": 5000},
            headers=auth_headers_admin_tenant2,
        )
        assert created.status_code == 201
        deposit_id = created.json()["id"]

        # Tenant 1 tente de la modifier
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep_t2.id}/deposit/{deposit_id}",
            json={"status": "released", "release_date": str(date.today())},
            headers=auth_headers_admin,
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests B3 — Auto-retention caution basee sur dommages
# ---------------------------------------------------------------------------


@pytest.fixture
def deposit_held(test_db, reservation_dep):
    """Deposit held pour la reservation."""
    d = Deposit(
        tenant_id=1,
        reservation_id=reservation_dep.id,
        amount_cents=20000,
        status="held",
    )
    test_db.add(d)
    test_db.commit()
    test_db.refresh(d)
    return d


@pytest.fixture
def invoice_for_dep(test_db, reservation_dep):
    """Facture liee a la reservation."""
    inv = Invoice(
        tenant_id=1,
        reservation_id=reservation_dep.id,
        invoice_number="INV-DEP-001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=7),
        total_amount_cents=8000,
        total_ttc_cents=9600,
        paid_amount_cents=0,
        status="draft",
        invoice_type="balance",
    )
    test_db.add(inv)
    test_db.commit()
    test_db.refresh(inv)
    return inv


@pytest.fixture
def damage_charge(test_db, invoice_for_dep):
    """Charge DAMAGE sur la facture."""
    charge = InvoiceCharge(
        tenant_id=1,
        invoice_id=invoice_for_dep.id,
        charge_type="DAMAGE",
        description="Rayure table",
        amount_cents=5000,
    )
    test_db.add(charge)
    test_db.commit()
    test_db.refresh(charge)
    return charge


class TestDepositDamageReconciliation:
    """B3 — Auto-retention caution quand dommages factures."""

    def test_release_blocked_when_damages_exist(
        self, client, auth_headers_admin, reservation_dep, deposit_held, damage_charge
    ):
        """PATCH status=released doit etre bloque si des charges DAMAGE existent."""
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposits/{deposit_held.id}",
            json={"status": "released", "release_date": str(date.today())},
            headers=auth_headers_admin,
        )
        assert r.status_code == 400
        assert "dommages" in r.json()["detail"].lower()

    def test_retained_amount_cannot_exceed_deposit(
        self, client, auth_headers_admin, reservation_dep, deposit_held
    ):
        """retained_amount_cents > deposit.amount_cents doit etre refuse."""
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposits/{deposit_held.id}",
            json={
                "status": "retained",
                "retained_amount_cents": 99999,
                "release_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 400
        assert "depasse" in r.json()["detail"].lower()

    def test_retained_with_valid_amount_succeeds(
        self, client, auth_headers_admin, reservation_dep, deposit_held, damage_charge
    ):
        """PATCH status=retained avec montant valide doit reussir."""
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposits/{deposit_held.id}",
            json={
                "status": "retained",
                "retained_amount_cents": 5000,
                "release_date": str(date.today()),
            },
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "retained"
        assert r.json()["retained_amount_cents"] == 5000

    def test_release_ok_when_no_damages(
        self, client, auth_headers_admin, reservation_dep, deposit_held
    ):
        """PATCH status=released sans dommages doit reussir."""
        r = client.patch(
            f"/api/v1/reservations/{reservation_dep.id}/deposits/{deposit_held.id}",
            json={"status": "released", "release_date": str(date.today())},
            headers=auth_headers_admin,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "released"
