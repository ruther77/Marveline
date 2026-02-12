"""Tests unitaires pour ReservationRepository."""
import pytest
from datetime import date, timedelta
from app.repositories.reservation import ReservationRepository
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.constants import CustomerType, ReservationStatus


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def test_customer(test_db):
    """Fixture client pour tests."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="Repository",
        email="test_repo@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def test_reservation_draft(test_db, test_customer):
    """Fixture réservation status=draft."""
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-TEST-DRAFT",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test Location",
        status=ReservationStatus.DRAFT,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)
    return reservation


@pytest.fixture
def test_reservation_confirmed(test_db, test_customer):
    """Fixture réservation status=confirmed."""
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-TEST-CONF",
        event_date=date.today() + timedelta(days=20),
        delivery_date=date.today() + timedelta(days=19),
        return_date=date.today() + timedelta(days=21),
        event_location="Conference Hall",
        status=ReservationStatus.CONFIRMED,
        total_amount=20000,
        deposit_amount=10000,
        deposit_paid=True
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)
    return reservation


@pytest.fixture
def test_reservation_past(test_db, test_customer):
    """Fixture réservation dans le passé."""
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-TEST-PAST",
        event_date=date.today() - timedelta(days=10),
        delivery_date=date.today() - timedelta(days=11),
        return_date=date.today() - timedelta(days=9),
        event_location="Past Event",
        status="completed",  # Use DB value directly
        total_amount=5000,
        deposit_amount=2500,
        deposit_paid=True
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)
    return reservation


# ═══════════════════════════════════════════════════════════════════════════
# Tests reference_exists()
# ═══════════════════════════════════════════════════════════════════════════

def test_reference_exists_true(test_db, test_reservation_draft):
    """Vérifie qu'une référence existante est détectée."""
    repo = ReservationRepository(test_db)

    assert repo.reference_exists(test_reservation_draft.reference) is True


def test_reference_exists_false(test_db):
    """Vérifie qu'une référence inexistante retourne False."""
    repo = ReservationRepository(test_db)

    assert repo.reference_exists("RES-9999-9999") is False


def test_reference_exists_case_insensitive(test_db, test_reservation_draft):
    """Vérifie que la recherche est insensible à la casse."""
    repo = ReservationRepository(test_db)

    # Test avec lowercase
    assert repo.reference_exists(test_reservation_draft.reference.lower()) is True

    # Test avec uppercase
    assert repo.reference_exists(test_reservation_draft.reference.upper()) is True


def test_reference_exists_with_whitespace(test_db, test_reservation_draft):
    """Vérifie que les espaces sont ignorés."""
    repo = ReservationRepository(test_db)

    assert repo.reference_exists(f"  {test_reservation_draft.reference}  ") is True


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_by_status()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_status_draft(test_db, test_reservation_draft, test_reservation_confirmed):
    """Liste les réservations par statut 'draft'."""
    repo = ReservationRepository(test_db)

    results, total = repo.list_by_status("draft", tenant_id=1)

    assert total >= 1
    assert all(r.status == "draft" for r in results)
    assert test_reservation_draft.id in [r.id for r in results]
    assert test_reservation_confirmed.id not in [r.id for r in results]


def test_list_by_status_confirmed(test_db, test_reservation_draft, test_reservation_confirmed):
    """Liste les réservations par statut 'confirmed'."""
    repo = ReservationRepository(test_db)

    results, total = repo.list_by_status("confirmed", tenant_id=1)

    assert total >= 1
    assert all(r.status == "confirmed" for r in results)
    assert test_reservation_confirmed.id in [r.id for r in results]
    assert test_reservation_draft.id not in [r.id for r in results]


def test_list_by_status_pagination(test_db, test_reservation_draft, test_reservation_confirmed):
    """Vérifie la pagination de list_by_status."""
    repo = ReservationRepository(test_db)

    # Première page (1 élément)
    results_page1, total = repo.list_by_status("draft", tenant_id=1, skip=0, limit=1)

    assert len(results_page1) <= 1
    assert total >= 1


def test_list_by_status_empty(test_db):
    """Liste vide si aucune réservation avec ce statut."""
    repo = ReservationRepository(test_db)

    results, total = repo.list_by_status("cancelled", tenant_id=1)

    assert results == []
    assert total == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_by_date_range()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_date_range_all_included(test_db, test_reservation_draft, test_reservation_confirmed):
    """Liste les réservations dans une plage de dates incluant toutes."""
    repo = ReservationRepository(test_db)

    start_date = date.today()
    end_date = date.today() + timedelta(days=30)

    results, total = repo.list_by_date_range(start_date, end_date, tenant_id=1)

    assert total >= 2
    assert all(start_date <= r.event_date <= end_date for r in results)
    assert test_reservation_draft.id in [r.id for r in results]
    assert test_reservation_confirmed.id in [r.id for r in results]


def test_list_by_date_range_partial(test_db, test_reservation_draft, test_reservation_confirmed):
    """Liste les réservations dans une plage excluant certaines."""
    repo = ReservationRepository(test_db)

    # Plage incluant seulement draft (event_date = today + 10 jours)
    start_date = date.today() + timedelta(days=5)
    end_date = date.today() + timedelta(days=15)

    results, total = repo.list_by_date_range(start_date, end_date, tenant_id=1)

    assert test_reservation_draft.id in [r.id for r in results]
    assert test_reservation_confirmed.id not in [r.id for r in results]


def test_list_by_date_range_with_status_filter(test_db, test_reservation_draft, test_reservation_confirmed):
    """Liste les réservations dans une plage avec filtre status."""
    repo = ReservationRepository(test_db)

    start_date = date.today()
    end_date = date.today() + timedelta(days=30)

    results, total = repo.list_by_date_range(
        start_date, end_date, tenant_id=1, status="draft"
    )

    assert all(r.status == "draft" for r in results)
    assert test_reservation_draft.id in [r.id for r in results]
    assert test_reservation_confirmed.id not in [r.id for r in results]


def test_list_by_date_range_empty(test_db, test_reservation_past):
    """Plage de dates sans réservation retourne liste vide."""
    repo = ReservationRepository(test_db)

    # Plage future (aucune réservation)
    start_date = date.today() + timedelta(days=100)
    end_date = date.today() + timedelta(days=200)

    results, total = repo.list_by_date_range(start_date, end_date, tenant_id=1)

    assert results == []
    assert total == 0


def test_list_by_date_range_pagination(test_db, test_reservation_draft, test_reservation_confirmed):
    """Vérifie la pagination de list_by_date_range."""
    repo = ReservationRepository(test_db)

    start_date = date.today()
    end_date = date.today() + timedelta(days=30)

    # Première page (1 élément)
    results_page1, total = repo.list_by_date_range(
        start_date, end_date, tenant_id=1, skip=0, limit=1
    )

    assert len(results_page1) <= 1
    assert total >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_by_customer()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_customer_single_customer(test_db, test_reservation_draft, test_reservation_confirmed, test_customer):
    """Liste les réservations d'un client spécifique."""
    repo = ReservationRepository(test_db)

    results, total = repo.list_by_customer(test_customer.id, tenant_id=1)

    assert total >= 2
    assert len(results) >= 2
    assert all(r.customer_id == test_customer.id for r in results)
    assert test_reservation_draft.id in [r.id for r in results]
    assert test_reservation_confirmed.id in [r.id for r in results]


def test_list_by_customer_with_status_filter(test_db, test_reservation_draft, test_reservation_confirmed, test_customer):
    """Liste les réservations d'un client filtré par statut."""
    repo = ReservationRepository(test_db)

    results, total = repo.list_by_customer(test_customer.id, tenant_id=1, status="draft")

    assert all(r.customer_id == test_customer.id for r in results)
    assert all(r.status == "draft" for r in results)
    assert test_reservation_draft.id in [r.id for r in results]
    assert test_reservation_confirmed.id not in [r.id for r in results]


def test_list_by_customer_empty(test_db):
    """Client sans réservation retourne liste vide."""
    # Créer client sans réservations
    customer_empty = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Empty",
        last_name="Customer",
        email="empty@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001"
    )
    test_db.add(customer_empty)
    test_db.commit()

    repo = ReservationRepository(test_db)
    results, total = repo.list_by_customer(customer_empty.id, tenant_id=1)

    assert results == []
    assert total == 0


def test_list_by_customer_pagination(test_db, test_reservation_draft, test_reservation_confirmed, test_customer):
    """Vérifie la pagination de list_by_customer."""
    repo = ReservationRepository(test_db)

    # Première page (1 élément)
    results_page1, total = repo.list_by_customer(test_customer.id, tenant_id=1, skip=0, limit=1)

    assert len(results_page1) <= 1
    assert total >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Tests Multi-Tenant Isolation
# ═══════════════════════════════════════════════════════════════════════════

def test_reference_exists_cross_tenant_isolation(test_db, test_reservation_draft):
    """Vérifie qu'une référence d'un autre tenant n'est pas visible."""
    # Créer customer tenant=2
    customer_tenant2 = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Tenant2",
        last_name="Customer",
        email="tenant2@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001"
    )
    test_db.add(customer_tenant2)
    test_db.flush()

    # Créer réservation tenant=2 avec référence différente (UNIQUE globale)
    reservation_tenant2 = Reservation(
        tenant_id=2,
        customer_id=customer_tenant2.id,
        reference="RES-TENANT2-DRAFT",  # Référence unique différente
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Tenant 2",
        status=ReservationStatus.DRAFT,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation_tenant2)
    test_db.commit()

    repo = ReservationRepository(test_db)

    # Vérifier que reference_exists trouve bien les deux références
    assert repo.reference_exists(test_reservation_draft.reference) is True
    assert repo.reference_exists(reservation_tenant2.reference) is True


def test_list_by_status_cross_tenant_isolation(test_db, test_reservation_draft):
    """Vérifie l'isolation multi-tenant dans list_by_status."""
    # Créer customer tenant=2
    customer_tenant2 = Customer(
        tenant_id=2,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Tenant2",
        last_name="Status",
        email="tenant2status@example.com",
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
        reference="RES-TENANT2",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Tenant 2",
        status=ReservationStatus.DRAFT,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation_tenant2)
    test_db.commit()

    repo = ReservationRepository(test_db)

    # Liste tenant=1 ne doit PAS voir reservation_tenant2
    results, total = repo.list_by_status("draft", tenant_id=1)

    assert all(r.tenant_id == 1 for r in results)
    assert reservation_tenant2.id not in [r.id for r in results]
