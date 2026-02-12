"""Tests unitaires des services (business logic isolée)."""
import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from app.services.auth import AuthService
from app.services.product import ProductService
from app.services.reservation import ReservationService
from app.services.invoice import InvoiceService
from app.models.user import User
from app.models.product import Product
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.core.security import get_password_hash, verify_password
from app.constants import CustomerType, InvoiceStatus, PaymentMethod, ProductCategory, ProductCondition, ReservationStatus


# ═══════════════════════════════════════════════════════════════════════════
# Tests AuthService
# ═══════════════════════════════════════════════════════════════════════════

def test_auth_service_login_success(test_db):
    """Test login avec credentials valides retourne tokens."""
    user = User(
        tenant_id=1,
        email="test@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Test User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    service = AuthService(test_db)
    access_token, refresh_token, expires_in = service.login("test@example.com", "password123")

    assert access_token is not None
    assert refresh_token is not None
    assert expires_in == 30 * 60  # 30 minutes


def test_auth_service_login_wrong_password(test_db):
    """Test login avec mauvais mot de passe échoue."""
    user = User(
        tenant_id=1,
        email="test@example.com",
        hashed_password=get_password_hash("correct_password"),
        full_name="Test User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.login("test@example.com", "wrong_password")

    assert exc_info.value.status_code == 401
    assert "Incorrect email or password" in exc_info.value.detail


def test_auth_service_login_inactive_user(test_db):
    """Test login avec user inactif échoue."""
    user = User(
        tenant_id=1,
        email="inactive@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Inactive User",
        role="staff",
        is_active=False  # Inactif
    )
    test_db.add(user)
    test_db.commit()

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.login("inactive@example.com", "password123")

    assert exc_info.value.status_code == 403
    assert "inactive" in exc_info.value.detail.lower()


def test_auth_service_login_nonexistent_user(test_db):
    """Test login avec email inexistant échoue."""
    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.login("nonexistent@example.com", "password123")

    assert exc_info.value.status_code == 401


def test_auth_service_login_email_case_insensitive(test_db):
    """Test login fonctionne quelle que soit la casse de l'email."""
    user = User(
        tenant_id=1,
        email="Test@Example.COM",  # Mixed case
        hashed_password=get_password_hash("password123"),
        full_name="Test User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    service = AuthService(test_db)
    # Login avec lowercase
    access_token, _, _ = service.login("test@example.com", "password123")

    assert access_token is not None


# ═══════════════════════════════════════════════════════════════════════════
# Tests ProductService
# ═══════════════════════════════════════════════════════════════════════════

def test_product_service_reserve_stock_success(test_db):
    """Test reserve_stock réussit si stock suffisant."""
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="TEST-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    service = ProductService(test_db)
    result = service.reserve_stock(product.id, quantity=5, tenant_id=1)

    assert result is True
    test_db.refresh(product)
    assert product.available_quantity == 5


def test_product_service_reserve_stock_insufficient(test_db):
    """Test reserve_stock échoue avec HTTPException si stock insuffisant."""
    product = Product(
        tenant_id=1,
        name="Low Stock",
        sku="LOW-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=3,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    service = ProductService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.reserve_stock(product.id, quantity=5, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "Insufficient stock" in exc_info.value.detail


def test_product_service_reserve_stock_product_not_found(test_db):
    """Test reserve_stock échoue si produit inexistant."""
    service = ProductService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.reserve_stock(99999, quantity=1, tenant_id=1)

    assert exc_info.value.status_code == 404


def test_product_service_release_stock_success(test_db):
    """Test release_stock incrémente stock."""
    product = Product(
        tenant_id=1,
        name="Reserved Product",
        sku="RESERVED-SKU",
        category=ProductCategory.AUTRE,
        price_per_day=1000,
        deposit_amount=2000,
        stock_quantity=10,
        available_quantity=5,  # Partiellement réservé
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()

    service = ProductService(test_db)
    result = service.release_stock(product.id, quantity=3, tenant_id=1)

    assert result is True
    test_db.refresh(product)
    assert product.available_quantity == 8


# ═══════════════════════════════════════════════════════════════════════════
# Tests ReservationService
# ═══════════════════════════════════════════════════════════════════════════

def test_reservation_service_confirm_success(test_db):
    """Test confirm_reservation réserve stock et change status."""
    # Setup
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Table",
        sku="TABLE-001",
        category=ProductCategory.NAPPE,
        price_per_day=2000,
        deposit_amount=5000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test Location",
        status=ReservationStatus.DRAFT,
        total_amount=6000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=product.id,
        quantity=3,
        unit_price=2000,
        subtotal=6000
    )
    test_db.add(line)
    test_db.commit()

    # Test
    service = ReservationService(test_db)
    confirmed = service.confirm_reservation(reservation.id, tenant_id=1)

    assert confirmed.status == "confirmed"
    test_db.refresh(product)
    assert product.available_quantity == 7  # 10 - 3


def test_reservation_service_confirm_already_confirmed(test_db):
    """Test confirm_reservation échoue si déjà confirmée."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-002",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,  # Déjà confirmée
        total_amount=1000,
        deposit_amount=500,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    service = ReservationService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.confirm_reservation(reservation.id, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "draft" in exc_info.value.detail.lower()


def test_reservation_service_cancel_releases_stock(test_db):
    """Test cancel_reservation libère le stock."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Bob",
        last_name="Smith",
        email="bob@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    product = Product(
        tenant_id=1,
        name="Chair",
        sku="CHAIR-001",
        category="chairs",
        price_per_day=500,
        deposit_amount=1000,
        stock_quantity=50,
        available_quantity=45,  # 5 réservés
        condition=ProductCondition.NEUF,
        is_active=True
    )
    test_db.add_all([customer, product])
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-003",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=1500,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=product.id,
        quantity=5,
        unit_price=500,
        subtotal=1500
    )
    test_db.add(line)
    test_db.commit()

    # Test
    service = ReservationService(test_db)
    cancelled = service.cancel_reservation(reservation.id, tenant_id=1)

    assert cancelled.status == "cancelled"
    test_db.refresh(product)
    assert product.available_quantity == 50  # Stock libéré


def test_reservation_service_cancel_already_cancelled(test_db):
    """Test cancel_reservation échoue si déjà annulée."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Alice",
        last_name="Brown",
        email="alice@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-004",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CANCELLED,  # Déjà annulée
        total_amount=1000,
        deposit_amount=500,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    service = ReservationService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.cancel_reservation(reservation.id, tenant_id=1)

    assert exc_info.value.status_code == 400


def test_reservation_service_generate_reference_unique(test_db):
    """Test generate_reference génère références uniques."""
    service = ReservationService(test_db)

    ref1 = service.generate_reference()
    ref2 = service.generate_reference()

    assert ref1 != ref2
    assert ref1.startswith("RES-")
    assert ref2.startswith("RES-")


# ═══════════════════════════════════════════════════════════════════════════
# Tests InvoiceService
# ═══════════════════════════════════════════════════════════════════════════

def test_invoice_service_add_payment_partial(test_db):
    """Test add_payment paiement partiel."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Charlie",
        last_name="Davis",
        email="charlie@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-005",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=ReservationStatus.DRAFT
    )
    test_db.add(invoice)
    test_db.commit()

    # Test paiement partiel
    service = InvoiceService(test_db)
    from app.schemas.invoice import AddPaymentRequest
    payment_data = AddPaymentRequest(
        amount_cents=5000,  # 50%
        payment_method=PaymentMethod.CARD,
        payment_date=date.today()
    )

    updated = service.add_payment(invoice.id, payment_data, tenant_id=1)

    assert updated.paid_amount == 5000
    assert updated.status == "draft"  # Pas encore payé complet


def test_invoice_service_add_payment_full(test_db):
    """Test add_payment paiement complet change status."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Diana",
        last_name="Evans",
        email="diana@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-006",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-002",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=ReservationStatus.DRAFT
    )
    test_db.add(invoice)
    test_db.commit()

    # Test paiement complet
    service = InvoiceService(test_db)
    from app.schemas.invoice import AddPaymentRequest
    payment_data = AddPaymentRequest(
        amount_cents=10000,  # 100%
        payment_method=PaymentMethod.CARD,
        payment_date=date.today()
    )

    updated = service.add_payment(invoice.id, payment_data, tenant_id=1)

    assert updated.paid_amount == 10000
    assert updated.status == "paid"  # Auto-changé


def test_invoice_service_add_payment_exceeds_total(test_db):
    """Test add_payment échoue si paiement dépasse total."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Eve",
        last_name="Foster",
        email="eve@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-007",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-003",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=0,
        status=ReservationStatus.DRAFT
    )
    test_db.add(invoice)
    test_db.commit()

    service = InvoiceService(test_db)
    from app.schemas.invoice import AddPaymentRequest
    payment_data = AddPaymentRequest(
        amount_cents=15000,  # > total
        payment_method=PaymentMethod.CARD,
        payment_date=date.today()
    )

    with pytest.raises(HTTPException) as exc_info:
        service.add_payment(invoice.id, payment_data, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "exceed" in exc_info.value.detail.lower()


def test_invoice_service_cancel_paid_invoice_fails(test_db):
    """Test cancel_invoice échoue si facture payée."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Frank",
        last_name="Green",
        email="frank@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-008",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-004",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=10000,  # Payée
        status=InvoiceStatus.PAID
    )
    test_db.add(invoice)
    test_db.commit()

    service = InvoiceService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.cancel_invoice(invoice.id, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "paid" in exc_info.value.detail.lower()


def test_invoice_service_list_overdue(test_db):
    """Test list_overdue retourne factures en retard."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Grace",
        last_name="Hill",
        email="grace@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-009",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()

    # Facture en retard (due_date passée)
    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-005",
        issue_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=15),  # Passée
        total_amount=10000,
        paid_amount=0,
        status=InvoiceStatus.SENT
    )
    test_db.add(invoice)
    test_db.commit()

    service = InvoiceService(test_db)
    overdue = service.list_overdue(tenant_id=1)

    assert len(overdue) >= 1
    assert any(inv.id == invoice.id for inv in overdue)
