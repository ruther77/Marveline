"""Tests de validation des schemas Pydantic (edge cases)."""
import pytest
from datetime import date, timedelta
from pydantic import ValidationError
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.reservation import ReservationCreate, ReservationLineCreate
from app.schemas.invoice import InvoiceCreate, AddPaymentRequest
from app.constants import CustomerType, InvoiceStatus, PaymentMethod, ProductCategory, ProductCondition, ReservationStatus


# ═══════════════════════════════════════════════════════════════════════════
# Tests CustomerCreate Validation
# ═══════════════════════════════════════════════════════════════════════════

def test_customer_create_individual_requires_names():
    """Test individual requiert first_name et last_name."""
    with pytest.raises(ValidationError) as exc_info:
        CustomerCreate(
            customer_type=CustomerType.INDIVIDUAL,
            # first_name et last_name manquants
            email="test@example.com",
            phone="+33612345678",
            city="Paris",
            postal_code="75001"
        )

    errors = exc_info.value.errors()
    assert any("first_name" in str(e) or "last_name" in str(e) for e in errors)


def test_customer_create_company_requires_company_name():
    """Test company requiert company_name."""
    with pytest.raises(ValidationError) as exc_info:
        CustomerCreate(
            customer_type=CustomerType.COMPANY,
            # company_name manquant
            siret="12345678901234",
            email="test@company.com",
            phone="+33612345678",
            city="Paris",
            postal_code="75001"
        )

    errors = exc_info.value.errors()
    assert any("company_name" in str(e) for e in errors)


def test_customer_create_email_validation():
    """Test email doit être valide."""
    with pytest.raises(ValidationError) as exc_info:
        CustomerCreate(
            customer_type=CustomerType.INDIVIDUAL,
            first_name="John",
            last_name="Doe",
            email="invalid-email",  # Pas de @
            phone="+33612345678",
            city="Paris",
            postal_code="75001"
        )

    errors = exc_info.value.errors()
    assert any("email" in str(e) for e in errors)


def test_customer_create_email_lowercase():
    """Test email converti en lowercase."""
    customer = CustomerCreate(
        customer_type=CustomerType.INDIVIDUAL,
        first_name="John",
        last_name="Doe",
        email="Test@Example.COM",  # Mixed case
        phone="+33612345678",
        city="Paris",
        postal_code="75001"
    )

    assert customer.email == "test@example.com"


def test_customer_create_phone_optional():
    """Test phone est optionnel."""
    customer = CustomerCreate(
        customer_type=CustomerType.INDIVIDUAL,
        first_name="John",
        last_name="Doe",
        email="test@example.com",
        # phone manquant
        city="Paris",
        postal_code="75001"
    )

    assert customer.phone is None


# ═══════════════════════════════════════════════════════════════════════════
# Tests ProductCreate Validation
# ═══════════════════════════════════════════════════════════════════════════

def test_product_create_price_must_be_positive():
    """Test price_per_day_cents doit être positif."""
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Test Product",
            sku="TEST-SKU",
            category=ProductCategory.AUTRE,
            price_per_day_cents=-1000,  # Négatif
            deposit_amount_cents=2000,
            stock_quantity=10,
            available_quantity=10,
            condition=ProductCondition.BON
        )

    errors = exc_info.value.errors()
    assert any("price_per_day_cents" in str(e) for e in errors)


def test_product_create_deposit_must_be_positive():
    """Test deposit_amount_cents doit être positif."""
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Test Product",
            sku="TEST-SKU",
            category=ProductCategory.AUTRE,
            price_per_day_cents=1000,
            deposit_amount_cents=-2000,  # Négatif
            stock_quantity=10,
            available_quantity=10,
            condition=ProductCondition.BON
        )

    errors = exc_info.value.errors()
    assert any("deposit_amount_cents" in str(e) for e in errors)


def test_product_create_available_lte_stock():
    """Test available_quantity <= stock_quantity."""
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Test Product",
            sku="TEST-SKU",
            category=ProductCategory.AUTRE,
            price_per_day_cents=1000,
            deposit_amount_cents=2000,
            stock_quantity=10,
            available_quantity=15,  # > stock_quantity
            condition=ProductCondition.BON
        )

    errors = exc_info.value.errors()
    assert any("available_quantity" in str(e) for e in errors)


def test_product_create_condition_enum():
    """Test condition doit être valeur valide."""
    with pytest.raises(ValidationError) as exc_info:
        ProductCreate(
            name="Test Product",
            sku="TEST-SKU",
            category=ProductCategory.AUTRE,
            price_per_day_cents=1000,
            deposit_amount_cents=2000,
            stock_quantity=10,
            available_quantity=10,
            condition="invalid_condition"  # Pas dans enum
        )

    errors = exc_info.value.errors()
    assert any("condition" in str(e) for e in errors)


def test_product_create_sku_stripped():
    """Test SKU est strippé des espaces."""
    product = ProductCreate(
        name="Test Product",
        sku="  TEST-SKU-001  ",  # Espaces
        category=ProductCategory.AUTRE,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON
    )

    assert product.sku == "TEST-SKU-001"


# ═══════════════════════════════════════════════════════════════════════════
# Tests ReservationCreate Validation
# ═══════════════════════════════════════════════════════════════════════════

def test_reservation_create_delivery_before_event():
    """Test delivery_date doit être avant event_date."""
    with pytest.raises(ValidationError) as exc_info:
        ReservationCreate(
            customer_id=1,
            event_date=date.today() + timedelta(days=10),
            delivery_date=date.today() + timedelta(days=11),  # Après event
            return_date=date.today() + timedelta(days=12),
            event_location="Test Location",
            lines=[
                ReservationLineCreate(product_id=1, quantity=1)
            ]
        )

    errors = exc_info.value.errors()
    assert any("delivery_date" in str(e) for e in errors)


def test_reservation_create_return_after_event():
    """Test return_date doit être après event_date."""
    with pytest.raises(ValidationError) as exc_info:
        ReservationCreate(
            customer_id=1,
            event_date=date.today() + timedelta(days=10),
            delivery_date=date.today() + timedelta(days=9),
            return_date=date.today() + timedelta(days=8),  # Avant event
            event_location="Test Location",
            lines=[
                ReservationLineCreate(product_id=1, quantity=1)
            ]
        )

    errors = exc_info.value.errors()
    assert any("return_date" in str(e) for e in errors)


def test_reservation_create_requires_lines():
    """Test réservation requiert au moins une ligne."""
    with pytest.raises(ValidationError) as exc_info:
        ReservationCreate(
            customer_id=1,
            event_date=date.today() + timedelta(days=10),
            delivery_date=date.today() + timedelta(days=9),
            return_date=date.today() + timedelta(days=11),
            event_location="Test Location",
            lines=[]  # Vide
        )

    errors = exc_info.value.errors()
    assert any("lines" in str(e) for e in errors)


def test_reservation_line_quantity_positive():
    """Test quantity doit être positive."""
    with pytest.raises(ValidationError) as exc_info:
        ReservationLineCreate(
            product_id=1,
            quantity=0  # Doit être >= 1
        )

    errors = exc_info.value.errors()
    assert any("quantity" in str(e) for e in errors)


# ═══════════════════════════════════════════════════════════════════════════
# Tests InvoiceCreate Validation
# ═══════════════════════════════════════════════════════════════════════════

def test_invoice_create_due_date_after_issue_date():
    """Test due_date doit être après issue_date."""
    with pytest.raises(ValidationError) as exc_info:
        InvoiceCreate(
            reservation_id=1,
            issue_date=date.today(),
            due_date=date.today() - timedelta(days=1)  # Avant issue_date
        )

    errors = exc_info.value.errors()
    assert any("due_date" in str(e) for e in errors)


def test_add_payment_amount_positive():
    """Test amount_cents doit être positif."""
    with pytest.raises(ValidationError) as exc_info:
        AddPaymentRequest(
            amount_cents=-1000,  # Négatif
            payment_method=PaymentMethod.CARD,
            payment_date=date.today()
        )

    errors = exc_info.value.errors()
    assert any("amount_cents" in str(e) for e in errors)


def test_add_payment_amount_zero_invalid():
    """Test amount_cents ne peut être zéro."""
    with pytest.raises(ValidationError) as exc_info:
        AddPaymentRequest(
            amount_cents=0,  # Zéro
            payment_method=PaymentMethod.CARD,
            payment_date=date.today()
        )

    errors = exc_info.value.errors()
    assert any("amount_cents" in str(e) for e in errors)


def test_add_payment_method_enum():
    """Test payment_method doit être valeur valide."""
    with pytest.raises(ValidationError) as exc_info:
        AddPaymentRequest(
            amount_cents=1000,
            payment_method="invalid_method",  # Pas dans enum
            payment_date=date.today()
        )

    errors = exc_info.value.errors()
    assert any("payment_method" in str(e) for e in errors)


# ═══════════════════════════════════════════════════════════════════════════
# Tests Computed Fields
# ═══════════════════════════════════════════════════════════════════════════

def test_product_response_computed_field_euros(test_db):
    """Test computed field price_per_day_euros."""
    from app.models.product import Product
    from app.schemas.product import ProductResponse

    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="COMPUTED-TEST",
        category=ProductCategory.AUTRE,
        price_per_day=2500,  # 2500 centimes
        deposit_amount=5000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    response = ProductResponse.model_validate(product)

    assert response.price_per_day_cents == 2500
    assert response.price_per_day_euros == 25.0  # Computed


def test_invoice_response_computed_is_paid(test_db):
    """Test computed field is_paid."""
    from app.models.customer import Customer
    from app.models.reservation import Reservation
    from app.models.invoice import Invoice
    from app.schemas.invoice import InvoiceResponse

    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="User",
        email="test@example.com",
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
        reference="RES-COMPUTED",
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
        invoice_number="INV-COMPUTED",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount=10000,
        paid_amount=10000,  # Payé complet
        status=InvoiceStatus.PAID
    )
    test_db.add(invoice)
    test_db.commit()
    test_db.refresh(invoice)

    response = InvoiceResponse.model_validate(invoice)

    assert response.is_paid is True  # Computed
    assert response.remaining_amount_cents == 0  # Computed


def test_reservation_response_computed_rental_days(test_db):
    """Test computed field rental_days."""
    from app.models.customer import Customer
    from app.models.reservation import Reservation
    from app.schemas.reservation import ReservationResponse

    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="User",
        email="test2@example.com",
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
        reference="RES-DAYS",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),  # 3 jours
        event_location="Test",
        status=ReservationStatus.DRAFT,
        total_amount=10000,
        deposit_amount=5000,
        deposit_paid=False
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)

    response = ReservationResponse.model_validate(reservation)

    assert response.rental_days == 3  # Computed: (11 - 9) + 1
