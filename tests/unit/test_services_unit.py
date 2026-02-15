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
        first_name="Test", last_name="User",
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
        first_name="Test", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.login("test@example.com", "wrong_password")

    assert exc_info.value.status_code == 401
    assert "Invalid email or password" in exc_info.value.detail


def test_auth_service_login_inactive_user(test_db):
    """Test login avec user inactif échoue."""
    user = User(
        tenant_id=1,
        email="inactive@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="Inactive", last_name="User",
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
        first_name="Test", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    service = AuthService(test_db)
    # Login avec lowercase
    access_token, _, _ = service.login("test@example.com", "password123")

    assert access_token is not None


def test_refresh_access_token_valid(test_db):
    """Test refresh d'un token valide génère nouveau access + refresh token (rotation)."""
    from app.core.security import decode_token
    from app.services.token import token_service

    user = User(
        tenant_id=1,
        email="refresh@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="Refresh", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Émettre tokens via TokenService (whitelist refresh JTI)
    _, refresh_token, _ = token_service.issue_tokens(
        user_id=user.id, tenant_id=user.tenant_id,
        email=user.email, role=user.role,
    )

    service = AuthService(test_db)
    new_access_token, new_refresh_token, expires_in = service.refresh_access_token(refresh_token)

    assert new_access_token is not None
    assert new_refresh_token is not None
    assert new_refresh_token != refresh_token  # Rotation: nouveau refresh
    assert expires_in == 30 * 60

    # Vérifier claims du nouveau access token
    payload = decode_token(new_access_token)
    assert int(payload["sub"]) == user.id
    assert int(payload["tenant_id"]) == user.tenant_id
    assert payload["email"] == user.email
    assert payload["role"] == user.role


def test_refresh_access_token_invalid(test_db):
    """Test refresh d'un token invalide lève HTTPException 401."""
    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.refresh_access_token("invalid_token_string")

    assert exc_info.value.status_code == 401
    assert "Invalid refresh token" in exc_info.value.detail


def test_refresh_access_token_wrong_type(test_db):
    """Test refresh avec access token (pas refresh) lève 401."""
    from app.core.security import create_access_token

    user = User(
        tenant_id=1,
        email="wrong@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="Wrong Type", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Créer ACCESS token (pas refresh)
    access_token = create_access_token({"sub": user.id, "tenant_id": user.tenant_id})

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.refresh_access_token(access_token)

    assert exc_info.value.status_code == 401
    assert "refresh token" in exc_info.value.detail.lower()


def test_refresh_access_token_inactive_user(test_db):
    """Test refresh avec user inactif lève HTTPException 403."""
    from app.core.security import create_refresh_token

    user = User(
        tenant_id=1,
        email="inactive_refresh@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="Inactive Refresh", last_name="User",
        role="staff",
        is_active=False  # Inactif
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Créer refresh token pour user inactif
    refresh_token = create_refresh_token({"sub": user.id, "tenant_id": user.tenant_id})

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.refresh_access_token(refresh_token)

    assert exc_info.value.status_code == 403
    assert "inactive" in exc_info.value.detail.lower()


def test_change_password_success(test_db):
    """Test change_password réussit avec current password correct."""
    user = User(
        tenant_id=1,
        email="change@example.com",
        hashed_password=get_password_hash("old_password"),
        first_name="Change Password", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    service = AuthService(test_db)
    result = service.change_password(
        user_id=user.id,
        current_password="old_password",
        new_password="NewSecure123!"
    )

    assert result is True

    # Vérifier que le password a changé
    test_db.refresh(user)
    assert verify_password("NewSecure123!", user.hashed_password) is True
    assert verify_password("old_password", user.hashed_password) is False


def test_change_password_wrong_current(test_db):
    """Test change_password échoue si current password incorrect."""
    user = User(
        tenant_id=1,
        email="wrong_current@example.com",
        hashed_password=get_password_hash("correct_password"),
        first_name="Wrong Current", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.change_password(
            user_id=user.id,
            current_password="wrong_current_password",
            new_password="NewSecure123!"
        )

    assert exc_info.value.status_code == 401
    assert "Current password" in exc_info.value.detail


def test_change_password_weak_new(test_db):
    """Test change_password échoue si nouveau password trop faible."""
    user = User(
        tenant_id=1,
        email="weak_new@example.com",
        hashed_password=get_password_hash("old_password"),
        first_name="Weak New", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.change_password(
            user_id=user.id,
            current_password="old_password",
            new_password="123"  # Trop court
        )

    assert exc_info.value.status_code == 400


def test_change_password_user_not_found(test_db):
    """Test change_password échoue si user inexistant."""
    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.change_password(
            user_id=9999,  # ID inexistant
            current_password="old_password",
            new_password="NewSecure123!"
        )

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_create_user_success(test_db):
    """Test create_user réussit avec données valides."""
    service = AuthService(test_db)

    new_user = service.create_user(
        email="newuser@example.com",
        password="SecurePass123!",
        first_name="New", last_name="User",
        role="manager",
        tenant_id=1
    )

    assert new_user is not None
    assert new_user.id is not None
    assert new_user.email == "newuser@example.com"
    assert new_user.role == "manager"
    assert new_user.tenant_id == 1
    assert new_user.is_active is True
    assert verify_password("SecurePass123!", new_user.hashed_password) is True


def test_create_user_duplicate_email(test_db):
    """Test create_user échoue si email existe déjà."""
    existing_user = User(
        tenant_id=1,
        email="existing@example.com",
        hashed_password=get_password_hash("password123"),
        first_name="Existing", last_name="User",
        role="staff",
        is_active=True
    )
    test_db.add(existing_user)
    test_db.commit()

    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.create_user(
            email="existing@example.com",  # Déjà existe
            password="SecurePass123!",
            first_name="Duplicate", last_name="User",
            role="staff",
            tenant_id=1
        )

    assert exc_info.value.status_code == 400
    assert "already registered" in exc_info.value.detail.lower()


def test_create_user_weak_password(test_db):
    """Test create_user échoue si password trop faible."""
    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.create_user(
            email="weak@example.com",
            password="123",  # Trop court
            first_name="Weak Password", last_name="User",
            role="staff",
            tenant_id=1
        )

    assert exc_info.value.status_code == 400


def test_create_user_invalid_role(test_db):
    """Test create_user échoue si rôle invalide."""
    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc_info:
        service.create_user(
            email="invalid_role@example.com",
            password="SecurePass123!",
            first_name="Invalid Role", last_name="User",
            role="superuser",  # Rôle invalide
            tenant_id=1
        )

    assert exc_info.value.status_code == 400
    assert "Invalid role" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════════
# Tests ProductService
# ═══════════════════════════════════════════════════════════════════════════

def test_product_service_reserve_stock_success(test_db):
    """Test reserve_stock réussit si stock suffisant."""
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="TEST-SKU",
        category=ProductCategory.MOBILIER,
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
        category=ProductCategory.MOBILIER,
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
        category=ProductCategory.MOBILIER,
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
        category=ProductCategory.NAPPES,
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
        category="mobilier",
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
