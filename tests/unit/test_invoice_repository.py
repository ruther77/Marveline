"""Tests unitaires pour InvoiceRepository."""
import pytest
from datetime import date, timedelta
from app.repositories.invoice import InvoiceRepository
from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.constants import CustomerType, ReservationStatus, InvoiceStatus


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_customer_invoice(test_db):
    """Fixture client pour tests factures."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Invoice",
        last_name="Test",
        email="invoice_test@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def test_reservation_for_invoice(test_db, test_customer_invoice):
    """Fixture réservation pour tests factures."""
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer_invoice.id,
        reference="RES-INV-TEST",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test Location",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=True,
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)
    return reservation


@pytest.fixture
def test_invoice_unpaid(test_db, test_reservation_for_invoice):
    """Fixture facture impayée."""
    invoice = Invoice(
        tenant_id=1,
        reservation_id=test_reservation_for_invoice.id,
        invoice_number="INV-TEST-UNPAID",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=InvoiceStatus.SENT,
    )
    test_db.add(invoice)
    test_db.commit()
    test_db.refresh(invoice)
    return invoice


@pytest.fixture
def test_invoice_partial(test_db, test_reservation_for_invoice):
    """Fixture facture partiellement payée."""
    # Créer une nouvelle réservation (une facture = une réservation)
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_reservation_for_invoice.customer_id,
        reference="RES-INV-PARTIAL",
        event_date=date.today() + timedelta(days=15),
        delivery_date=date.today() + timedelta(days=14),
        return_date=date.today() + timedelta(days=16),
        event_location="Partial Payment Event",
        status=ReservationStatus.CONFIRMED,
        total_amount=20000,
        deposit_amount=10000,
        deposit_paid=True,
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-PARTIAL",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=20000,
        paid_amount=10000,  # 50% payé
        status=InvoiceStatus.SENT,
    )
    test_db.add(invoice)
    test_db.commit()
    test_db.refresh(invoice)
    return invoice


@pytest.fixture
def test_invoice_paid(test_db, test_reservation_for_invoice):
    """Fixture facture complètement payée."""
    # Créer une nouvelle réservation
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_reservation_for_invoice.customer_id,
        reference="RES-INV-PAID",
        event_date=date.today() + timedelta(days=20),
        delivery_date=date.today() + timedelta(days=19),
        return_date=date.today() + timedelta(days=21),
        event_location="Paid Event",
        status=ReservationStatus.CONFIRMED,
        total_amount=15000,
        deposit_amount=7500,
        deposit_paid=True,
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-PAID",
        issue_date=date.today() - timedelta(days=10),
        due_date=date.today() - timedelta(days=1),
        total_amount=15000,
        paid_amount=15000,  # 100% payé
        status=InvoiceStatus.PAID,
        payment_method="card",
        payment_date=date.today() - timedelta(days=5),
    )
    test_db.add(invoice)
    test_db.commit()
    test_db.refresh(invoice)
    return invoice


# ═══════════════════════════════════════════════════════════════════════════
# Tests get_by_id_with_relations()
# ═══════════════════════════════════════════════════════════════════════════

def test_get_by_id_with_relations_found(test_db, test_invoice_unpaid):
    """Récupère une facture avec relations chargées (reservation + customer)."""
    repo = InvoiceRepository(test_db)

    invoice = repo.get_by_id_with_relations(test_invoice_unpaid.id, tenant_id=1)

    assert invoice is not None
    assert invoice.id == test_invoice_unpaid.id
    # Vérifier que relations sont chargées (pas de N+1)
    assert invoice.reservation is not None
    assert invoice.reservation.customer is not None
    assert invoice.reservation.customer.first_name == "Invoice"


def test_get_by_id_with_relations_not_found(test_db):
    """Recherche d'un ID inexistant retourne None."""
    repo = InvoiceRepository(test_db)

    invoice = repo.get_by_id_with_relations(99999, tenant_id=1)

    assert invoice is None


def test_get_by_id_with_relations_cross_tenant(test_db, test_invoice_unpaid):
    """Facture d'un autre tenant n'est pas accessible."""
    repo = InvoiceRepository(test_db)

    # Tenter d'accéder avec tenant_id=2
    invoice = repo.get_by_id_with_relations(test_invoice_unpaid.id, tenant_id=2)

    assert invoice is None


# ═══════════════════════════════════════════════════════════════════════════
# Tests get_by_invoice_number()
# ═══════════════════════════════════════════════════════════════════════════

def test_get_by_invoice_number_found(test_db, test_invoice_unpaid):
    """Récupère une facture par son numéro."""
    repo = InvoiceRepository(test_db)

    invoice = repo.get_by_invoice_number(test_invoice_unpaid.invoice_number, tenant_id=1)

    assert invoice is not None
    assert invoice.id == test_invoice_unpaid.id
    assert invoice.invoice_number == test_invoice_unpaid.invoice_number


def test_get_by_invoice_number_not_found(test_db):
    """Recherche d'un numéro inexistant retourne None."""
    repo = InvoiceRepository(test_db)

    invoice = repo.get_by_invoice_number("INV-9999-9999", tenant_id=1)

    assert invoice is None


def test_get_by_invoice_number_case_insensitive(test_db, test_invoice_unpaid):
    """Recherche insensible à la casse."""
    repo = InvoiceRepository(test_db)

    # Lowercase
    invoice_lower = repo.get_by_invoice_number(
        test_invoice_unpaid.invoice_number.lower(), tenant_id=1
    )
    assert invoice_lower is not None

    # Uppercase
    invoice_upper = repo.get_by_invoice_number(
        test_invoice_unpaid.invoice_number.upper(), tenant_id=1
    )
    assert invoice_upper is not None


def test_get_by_invoice_number_with_whitespace(test_db, test_invoice_unpaid):
    """Recherche ignore les espaces."""
    repo = InvoiceRepository(test_db)

    invoice = repo.get_by_invoice_number(
        f"  {test_invoice_unpaid.invoice_number}  ", tenant_id=1
    )

    assert invoice is not None


def test_get_by_invoice_number_cross_tenant(test_db, test_invoice_unpaid):
    """Facture d'un autre tenant non accessible."""
    repo = InvoiceRepository(test_db)

    invoice = repo.get_by_invoice_number(test_invoice_unpaid.invoice_number, tenant_id=2)

    assert invoice is None


# ═══════════════════════════════════════════════════════════════════════════
# Tests invoice_number_exists()
# ═══════════════════════════════════════════════════════════════════════════

def test_invoice_number_exists_true(test_db, test_invoice_unpaid):
    """Vérifie qu'un numéro existant est détecté."""
    repo = InvoiceRepository(test_db)

    assert repo.invoice_number_exists(test_invoice_unpaid.invoice_number, tenant_id=1) is True


def test_invoice_number_exists_false(test_db):
    """Vérifie qu'un numéro inexistant retourne False."""
    repo = InvoiceRepository(test_db)

    assert repo.invoice_number_exists("INV-9999-9999", tenant_id=1) is False


def test_invoice_number_exists_case_insensitive(test_db, test_invoice_unpaid):
    """Vérification insensible à la casse."""
    repo = InvoiceRepository(test_db)

    assert repo.invoice_number_exists(
        test_invoice_unpaid.invoice_number.lower(), tenant_id=1
    ) is True


def test_invoice_number_exists_with_exclude(test_db, test_invoice_unpaid):
    """Vérification avec exclusion d'un ID (pour UPDATE)."""
    repo = InvoiceRepository(test_db)

    # Exclure l'ID de la facture elle-même → False
    assert repo.invoice_number_exists(
        test_invoice_unpaid.invoice_number,
        tenant_id=1,
        exclude_id=test_invoice_unpaid.id
    ) is False

    # Sans exclure → True
    assert repo.invoice_number_exists(
        test_invoice_unpaid.invoice_number,
        tenant_id=1
    ) is True


def test_invoice_number_exists_cross_tenant(test_db, test_invoice_unpaid):
    """Numéro d'un autre tenant retourne False."""
    repo = InvoiceRepository(test_db)

    # Même numéro mais tenant différent
    assert repo.invoice_number_exists(test_invoice_unpaid.invoice_number, tenant_id=2) is False


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_unpaid()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_unpaid(test_db, test_invoice_unpaid, test_invoice_partial, test_invoice_paid):
    """Liste les factures impayées (paid_amount < total_amount)."""
    repo = InvoiceRepository(test_db)

    results = repo.list_unpaid(tenant_id=1)

    # Unpaid et partial doivent être présents, paid non
    unpaid_ids = [i.id for i in results]
    assert test_invoice_unpaid.id in unpaid_ids
    assert test_invoice_partial.id in unpaid_ids
    assert test_invoice_paid.id not in unpaid_ids

    # Vérifier que toutes sont impayées
    assert all(i.paid_amount < i.total_amount for i in results)


def test_list_unpaid_excludes_cancelled(test_db, test_invoice_unpaid, test_customer_invoice):
    """Liste unpaid exclut les factures annulées."""
    # Créer nouvelle réservation pour facture annulée
    reservation_cancelled = Reservation(
        tenant_id=1,
        customer_id=test_customer_invoice.id,
        reference="RES-CANCELLED",
        event_date=date.today() + timedelta(days=20),
        delivery_date=date.today() + timedelta(days=19),
        return_date=date.today() + timedelta(days=21),
        event_location="Cancelled Event",
        status=ReservationStatus.CANCELLED,
        total_amount=5000,
        deposit_amount=2500,
        deposit_paid=False
    )
    test_db.add(reservation_cancelled)
    test_db.flush()

    # Créer facture annulée impayée
    invoice_cancelled = Invoice(
        tenant_id=1,
        reservation_id=reservation_cancelled.id,
        invoice_number="INV-TEST-CANCELLED",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=5000,
        paid_amount=0,
        status=InvoiceStatus.CANCELLED
    )
    test_db.add(invoice_cancelled)
    test_db.commit()

    repo = InvoiceRepository(test_db)
    results = repo.list_unpaid(tenant_id=1)

    # Facture annulée ne doit PAS apparaître
    assert invoice_cancelled.id not in [i.id for i in results]


def test_list_unpaid_pagination(test_db, test_invoice_unpaid, test_invoice_partial):
    """Vérifie la pagination de list_unpaid."""
    repo = InvoiceRepository(test_db)

    # Première page (1 élément)
    results_page1 = repo.list_unpaid(tenant_id=1, skip=0, limit=1)

    assert len(results_page1) <= 1


def test_list_unpaid_empty(test_db, test_invoice_paid):
    """Liste vide si toutes les factures sont payées."""
    # Seule facture est payée
    repo = InvoiceRepository(test_db)

    # Créer tenant sans factures impayées (utiliser tenant_id=3)
    results = repo.list_unpaid(tenant_id=3)

    assert results == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_by_date_range()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_date_range_all_included(test_db, test_invoice_unpaid, test_invoice_paid):
    """Liste les factures dans une plage incluant toutes."""
    repo = InvoiceRepository(test_db)

    start_date = date.today() - timedelta(days=15)
    end_date = date.today() + timedelta(days=5)

    results = repo.list_by_date_range(start_date, end_date, tenant_id=1)

    # Vérifier que toutes les factures sont dans la plage
    assert all(start_date <= i.issue_date <= end_date for i in results)
    assert len(results) >= 2


def test_list_by_date_range_partial(test_db, test_invoice_unpaid, test_invoice_paid):
    """Liste les factures dans une plage partielle."""
    repo = InvoiceRepository(test_db)

    # Plage incluant seulement unpaid (issue_date = today)
    start_date = date.today() - timedelta(days=1)
    end_date = date.today() + timedelta(days=1)

    results = repo.list_by_date_range(start_date, end_date, tenant_id=1)

    assert test_invoice_unpaid.id in [i.id for i in results]


def test_list_by_date_range_with_status_filter(test_db, test_invoice_unpaid, test_invoice_paid):
    """Liste les factures dans une plage avec filtre status."""
    repo = InvoiceRepository(test_db)

    start_date = date.today() - timedelta(days=15)
    end_date = date.today() + timedelta(days=5)

    results = repo.list_by_date_range(
        start_date, end_date, tenant_id=1, status="paid"
    )

    # Seules factures payées
    assert all(i.status == "paid" for i in results)
    assert test_invoice_paid.id in [i.id for i in results]


def test_list_by_date_range_empty(test_db):
    """Plage de dates sans facture retourne liste vide."""
    repo = InvoiceRepository(test_db)

    # Plage future (aucune facture)
    start_date = date.today() + timedelta(days=100)
    end_date = date.today() + timedelta(days=200)

    results = repo.list_by_date_range(start_date, end_date, tenant_id=1)

    assert results == []


def test_list_by_date_range_pagination(test_db, test_invoice_unpaid, test_invoice_paid):
    """Vérifie la pagination de list_by_date_range."""
    repo = InvoiceRepository(test_db)

    start_date = date.today() - timedelta(days=15)
    end_date = date.today() + timedelta(days=5)

    # Première page (1 élément)
    results_page1 = repo.list_by_date_range(
        start_date, end_date, tenant_id=1, skip=0, limit=1
    )

    assert len(results_page1) <= 1


# ═══════════════════════════════════════════════════════════════════════════
# Tests Multi-Tenant Isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_list_unpaid_cross_tenant_isolation(test_db, test_invoice_unpaid):
    """Vérifie l'isolation multi-tenant dans list_unpaid."""
    # Créer customer tenant=2
    customer_tenant2 = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Tenant2",
        last_name="Invoice",
        email="tenant2invoice@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001"
    )
    test_db.add(customer_tenant2)
    test_db.flush()

    # Créer réservation tenant=2
    reservation_tenant2 = Reservation(
        tenant_id=2,
        customer_id=customer_tenant2.id,
        reference="RES-TENANT2-INV",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Tenant 2 Event",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=True
    )
    test_db.add(reservation_tenant2)
    test_db.flush()

    # Créer facture tenant=2
    invoice_tenant2 = Invoice(
        tenant_id=2,
        reservation_id=reservation_tenant2.id,
        invoice_number="INV-TENANT2",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=InvoiceStatus.SENT
    )
    test_db.add(invoice_tenant2)
    test_db.commit()

    repo = InvoiceRepository(test_db)

    # Liste tenant=1 ne doit PAS voir invoice_tenant2
    results = repo.list_unpaid(tenant_id=1)

    assert all(i.tenant_id == 1 for i in results)
    assert invoice_tenant2.id not in [i.id for i in results]
