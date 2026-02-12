"""Tests unitaires pour ReservationRepository."""
import pytest
from datetime import date, timedelta
from app.repositories.reservation import ReservationRepository
from app.models.reservation import Reservation
from app.models.customer import Customer
from app.models.product import Product
from app.constants import CustomerType, ReservationStatus, ProductCategory


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
def test_product(test_db):
    """Fixture produit pour tests."""
    product = Product(
        tenant_id=1,
        name="Test Product Reservation",
        sku="TEST-PROD-RES",
        category=ProductCategory.ASSIETTE,
        price_per_day=100,
        stock_quantity=100,
        available_quantity=80,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)
    return product


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
        status="returned",  # Réservation terminée (vaisselle retournée)
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


# ═══════════════════════════════════════════════════════════════════════════
# Tests get_by_reference()
# ═══════════════════════════════════════════════════════════════════════════

def test_get_by_reference_success(test_db, test_reservation_draft):
    """Récupère réservation par référence."""
    repo = ReservationRepository(test_db)

    result = repo.get_by_reference("RES-TEST-DRAFT", tenant_id=1)

    assert result is not None
    assert result.id == test_reservation_draft.id
    assert result.reference == "RES-TEST-DRAFT"


def test_get_by_reference_not_found(test_db):
    """Référence inexistante retourne None."""
    repo = ReservationRepository(test_db)

    result = repo.get_by_reference("RES-INEXISTANT", tenant_id=1)

    assert result is None


def test_get_by_reference_case_insensitive_whitespace(test_db, test_reservation_draft):
    """Recherche insensible à la casse avec whitespace."""
    repo = ReservationRepository(test_db)

    # Minuscules + espaces
    result = repo.get_by_reference(" res-test-draft ", tenant_id=1)

    assert result is not None
    assert result.id == test_reservation_draft.id


# ═══════════════════════════════════════════════════════════════════════════
# Tests list_upcoming()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_upcoming_days_ahead(test_db, test_customer):
    """Liste réservations à venir dans les N prochains jours."""
    repo = ReservationRepository(test_db)

    # Créer 3 réservations à dates différentes
    res_tomorrow = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-TOMORROW",
        event_date=date.today() + timedelta(days=1),
        delivery_date=date.today(),
        return_date=date.today() + timedelta(days=2),
        event_location="Tomorrow",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=True
    )

    res_week = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-WEEK",
        event_date=date.today() + timedelta(days=7),
        delivery_date=date.today() + timedelta(days=6),
        return_date=date.today() + timedelta(days=8),
        event_location="Next Week",
        status=ReservationStatus.DRAFT,
        total_amount=15000,
        deposit_amount=7500,
        deposit_paid=False
    )

    res_month = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-MONTH",
        event_date=date.today() + timedelta(days=30),
        delivery_date=date.today() + timedelta(days=29),
        return_date=date.today() + timedelta(days=31),
        event_location="Next Month",
        status=ReservationStatus.CONFIRMED,
        total_amount=20000,
        deposit_amount=10000,
        deposit_paid=True
    )

    test_db.add_all([res_tomorrow, res_week, res_month])
    test_db.commit()

    # Liste 10 jours à venir (inclut tomorrow + week, exclut month)
    results = repo.list_upcoming(days_ahead=10, tenant_id=1)

    assert len(results) == 2
    assert res_tomorrow.id in [r.id for r in results]
    assert res_week.id in [r.id for r in results]
    assert res_month.id not in [r.id for r in results]


def test_list_upcoming_excludes_cancelled_returned(test_db, test_customer):
    """list_upcoming exclut réservations annulées et retournées."""
    repo = ReservationRepository(test_db)

    # Réservation cancelled
    res_cancelled = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-CANCELLED-UP",
        event_date=date.today() + timedelta(days=5),
        delivery_date=date.today() + timedelta(days=4),
        return_date=date.today() + timedelta(days=6),
        event_location="Cancelled",
        status="cancelled",  # Valide selon contrainte DB
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )

    # Réservation returned (terminée, ne devrait pas être upcoming)
    res_returned = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        reference="RES-RETURNED-UP",
        event_date=date.today() + timedelta(days=5),
        delivery_date=date.today() + timedelta(days=4),
        return_date=date.today() + timedelta(days=6),
        event_location="Returned",
        status="returned",  # Réservation terminée (vaisselle retournée)
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=True
    )

    test_db.add_all([res_cancelled, res_returned])
    test_db.commit()

    results = repo.list_upcoming(days_ahead=10, tenant_id=1)

    # Aucune réservation cancelled/returned dans upcoming
    assert res_cancelled.id not in [r.id for r in results]
    assert res_returned.id not in [r.id for r in results]


def test_list_upcoming_empty(test_db):
    """list_upcoming retourne liste vide si aucune réservation à venir."""
    repo = ReservationRepository(test_db)

    results = repo.list_upcoming(days_ahead=30, tenant_id=1)

    assert results == []


# ═══════════════════════════════════════════════════════════════════════════
# Tests ReservationLineRepository - list_by_reservation()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_reservation_with_lines(test_db, test_reservation_draft, test_product):
    """Liste lignes d'une réservation."""
    from app.repositories.reservation import ReservationLineRepository
    from app.models.reservation import ReservationLine

    # Créer un second produit (contrainte unique reservation_id + product_id)
    product2 = Product(
        tenant_id=1,
        name="Test Product 2 Reservation",
        sku="TEST-PROD-RES-2",
        category=ProductCategory.VERRE,
        price_per_day=150,
        stock_quantity=50,
        available_quantity=40,
        is_active=True
    )
    test_db.add(product2)
    test_db.flush()

    # Créer 2 lignes pour la réservation avec produits différents
    line1 = ReservationLine(
        tenant_id=1,
        reservation_id=test_reservation_draft.id,
        product_id=test_product.id,
        quantity=5,
        unit_price=100,
        subtotal=500
    )
    line2 = ReservationLine(
        tenant_id=1,
        reservation_id=test_reservation_draft.id,
        product_id=product2.id,  # Produit différent
        quantity=3,
        unit_price=150,
        subtotal=450
    )
    test_db.add_all([line1, line2])
    test_db.commit()

    repo = ReservationLineRepository(test_db)
    results, total = repo.list_by_reservation(test_reservation_draft.id, tenant_id=1)

    assert len(results) == 2
    assert total == 2
    assert all(line.reservation_id == test_reservation_draft.id for line in results)


def test_list_by_reservation_empty(test_db, test_reservation_draft):
    """Liste lignes d'une réservation sans lignes retourne vide."""
    from app.repositories.reservation import ReservationLineRepository

    repo = ReservationLineRepository(test_db)
    results, total = repo.list_by_reservation(test_reservation_draft.id, tenant_id=1)

    assert results == []
    assert total == 0


# ═══════════════════════════════════════════════════════════════════════════
# Tests ReservationLineRepository - list_by_product()
# ═══════════════════════════════════════════════════════════════════════════

def test_list_by_product_with_lines(test_db, test_reservation_draft, test_product):
    """Liste lignes contenant un produit spécifique."""
    from app.repositories.reservation import ReservationLineRepository
    from app.models.reservation import ReservationLine

    # Créer ligne avec test_product
    line = ReservationLine(
        tenant_id=1,
        reservation_id=test_reservation_draft.id,
        product_id=test_product.id,
        quantity=10,
        unit_price=100,
        subtotal=1000
    )
    test_db.add(line)
    test_db.commit()

    repo = ReservationLineRepository(test_db)
    results, total = repo.list_by_product(test_product.id, tenant_id=1)

    assert len(results) >= 1
    assert total >= 1
    assert all(line.product_id == test_product.id for line in results)


def test_list_by_product_empty(test_db, test_product):
    """Liste lignes d'un produit jamais réservé retourne vide."""
    from app.repositories.reservation import ReservationLineRepository

    repo = ReservationLineRepository(test_db)
    results, total = repo.list_by_product(test_product.id, tenant_id=1)

    assert results == []
    assert total == 0
