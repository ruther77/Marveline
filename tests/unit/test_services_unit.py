"""Tests unitaires des services (business logic isolée)."""
import pytest
from datetime import date, timedelta
from fastapi import HTTPException
from app.services.product import ProductService
from app.services.reservation import ReservationService
from app.services.invoice import InvoiceService
from app.models.product import Product
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationLine
from app.models.invoice import Invoice
from app.core.security import get_password_hash, verify_password
from app.constants import (
    CustomerType, InvoiceStatus, PaymentMethod,
    ProductCategory, ProductCondition, ReservationStatus,
)


# ═══════════════════════════════════════════════════════════════════════════
# Tests ProductService
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_product_service_reserve_stock_success(async_db):
    """Test reserve_stock réussit si stock suffisant."""
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="TEST-SKU",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.BON,
        is_active=True
    )
    async_db.add(product)
    await async_db.flush()

    service = ProductService(async_db)
    result = await service.reserve_stock(product.id, quantity=5, tenant_id=1)

    assert result is True
    await async_db.refresh(product)
    assert product.available_quantity == 5


@pytest.mark.asyncio
async def test_product_service_reserve_stock_insufficient(async_db):
    """Test reserve_stock échoue avec HTTPException si stock insuffisant."""
    product = Product(
        tenant_id=1,
        name="Low Stock",
        sku="LOW-SKU",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
        stock_quantity=10,
        available_quantity=3,
        condition=ProductCondition.BON,
        is_active=True
    )
    async_db.add(product)
    await async_db.flush()

    service = ProductService(async_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.reserve_stock(product.id, quantity=5, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "Insufficient stock" in exc_info.value.detail


@pytest.mark.asyncio
async def test_product_service_reserve_stock_product_not_found(async_db):
    """Test reserve_stock échoue si produit inexistant."""
    service = ProductService(async_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.reserve_stock(99999, quantity=1, tenant_id=1)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_product_service_release_stock_success(async_db):
    """Test release_stock incrémente stock."""
    product = Product(
        tenant_id=1,
        name="Reserved Product",
        sku="RESERVED-SKU",
        category=ProductCategory.MOBILIER,
        price_per_day_cents=1000,
        deposit_amount_cents=2000,
        stock_quantity=10,
        available_quantity=5,  # Partiellement réservé
        condition=ProductCondition.BON,
        is_active=True
    )
    async_db.add(product)
    await async_db.flush()

    service = ProductService(async_db)
    result = await service.release_stock(product.id, quantity=3, tenant_id=1)

    assert result is True
    await async_db.refresh(product)
    assert product.available_quantity == 8


# ═══════════════════════════════════════════════════════════════════════════
# Tests ReservationService
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reservation_service_confirm_success(async_db):
    """Test confirm_reservation réserve stock et change status.

    Note: _auto_generate_invoice est mocké car InvoiceService._compute_tva_breakdown
    accède à reservation.lines via lazy load (incompatible AsyncSession — BUG-P2-LAZY-INVOICE).
    """
    from unittest.mock import AsyncMock, patch
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
        price_per_day_cents=2000,
        deposit_amount_cents=5000,
        stock_quantity=10,
        available_quantity=10,
        condition=ProductCondition.NEUF,
        is_active=True
    )
    async_db.add_all([customer, product])
    await async_db.flush()
    await async_db.refresh(customer)
    await async_db.refresh(product)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-001",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test Location",
        status=ReservationStatus.DRAFT,
        total_amount_cents=6000,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=product.id,
        quantity=3,
        unit_price_cents=2000,
        subtotal_cents=6000
    )
    async_db.add(line)
    await async_db.flush()

    # Test — mock méthodes avec lazy load (BUG-P2-LAZY-INVOICE: AsyncSession + lazy load)
    service = ReservationService(async_db)
    with patch.object(service, "_auto_generate_invoice", new=AsyncMock(return_value=None)), \
         patch.object(service, "_calculate_deposit", new=AsyncMock(return_value=5000)), \
         patch.object(service, "_notify_reservation_confirmed", return_value=None), \
         patch("app.services.reservation_workflow.AsyncReservationWorkflowService") as mock_wf_cls:
        mock_wf = AsyncMock()
        mock_wf_cls.return_value = mock_wf
        mock_wf.auto_generate_departure_movement = AsyncMock(return_value=None)
        confirmed = await service.confirm_reservation(reservation.id, tenant_id=1)

    assert confirmed.status == "confirmed"
    await async_db.refresh(product)
    assert product.available_quantity == 7  # 10 - 3


@pytest.mark.asyncio
async def test_reservation_service_confirm_already_confirmed(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-002",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,  # Déjà confirmée
        total_amount_cents=1000,
        deposit_amount_cents=500,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()

    service = ReservationService(async_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_reservation(reservation.id, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "draft" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_reservation_service_cancel_releases_stock(async_db):
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
        price_per_day_cents=500,
        deposit_amount_cents=1000,
        stock_quantity=50,
        available_quantity=45,  # 5 réservés
        condition=ProductCondition.NEUF,
        is_active=True
    )
    async_db.add_all([customer, product])
    await async_db.flush()
    await async_db.refresh(customer)
    await async_db.refresh(product)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-003",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=1500,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=product.id,
        quantity=5,
        unit_price_cents=500,
        subtotal_cents=1500
    )
    async_db.add(line)
    await async_db.flush()

    # Test
    service = ReservationService(async_db)
    cancelled = await service.cancel_reservation(reservation.id, tenant_id=1)

    assert cancelled.status == "cancelled"
    await async_db.refresh(product)
    assert product.available_quantity == 50  # Stock libéré


@pytest.mark.asyncio
async def test_reservation_service_cancel_already_cancelled(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-004",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CANCELLED,  # Déjà annulée
        total_amount_cents=1000,
        deposit_amount_cents=500,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()

    service = ReservationService(async_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_reservation(reservation.id, tenant_id=1)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_reservation_service_cancel_completed_forbidden(async_db):
    """Test cancel_reservation échoue sur réservation terminée (completed)."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Eva",
        last_name="Durand",
        email="eva@example.com",
        phone="+33612345678",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-004B",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.COMPLETED,
        total_amount_cents=1000,
        deposit_amount_cents=500,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()

    service = ReservationService(async_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_reservation(reservation.id, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "cannot cancel reservation" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_reservation_service_generate_reference_unique(async_db):
    """Test generate_reference retourne une référence au bon format.

    Note: l'unicité inter-appels est garantie par l'index DB unique + retry
    dans create_reservation(), pas par generate_reference() seul.
    """
    import re
    from datetime import datetime

    service = ReservationService(async_db)

    ref = await service.generate_reference()

    year = datetime.now().year
    assert ref.startswith("RES-")
    assert re.match(rf"^RES-{year}-\d{{4}}$", ref), f"Format inattendu: {ref}"


# ═══════════════════════════════════════════════════════════════════════════
# Tests InvoiceService
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_invoice_service_add_payment_partial(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-005",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=10000,
        paid_amount_cents=0,
        status=ReservationStatus.DRAFT
    )
    async_db.add(invoice)
    await async_db.flush()

    # Test paiement partiel
    service = InvoiceService(async_db)
    from app.schemas.invoice import AddPaymentRequest
    payment_data = AddPaymentRequest(
        amount_cents=5000,  # 50%
        payment_method=PaymentMethod.CARD,
        payment_date=date.today()
    )

    updated = await service.add_payment(invoice.id, payment_data, tenant_id=1)

    assert updated.paid_amount_cents == 5000
    assert updated.status == "draft"  # Pas encore payé complet


@pytest.mark.asyncio
async def test_invoice_service_add_payment_full(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-006",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-002",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=10000,
        paid_amount_cents=0,
        status=ReservationStatus.DRAFT
    )
    async_db.add(invoice)
    await async_db.flush()

    # Test paiement complet
    service = InvoiceService(async_db)
    from app.schemas.invoice import AddPaymentRequest
    payment_data = AddPaymentRequest(
        amount_cents=10000,  # 100%
        payment_method=PaymentMethod.CARD,
        payment_date=date.today()
    )

    updated = await service.add_payment(invoice.id, payment_data, tenant_id=1)

    assert updated.paid_amount_cents == 10000
    assert updated.status == "paid"  # Auto-changé


@pytest.mark.asyncio
async def test_invoice_service_add_payment_exceeds_total(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-007",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-003",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=10000,
        paid_amount_cents=0,
        status=ReservationStatus.DRAFT
    )
    async_db.add(invoice)
    await async_db.flush()

    service = InvoiceService(async_db)
    from app.schemas.invoice import AddPaymentRequest
    payment_data = AddPaymentRequest(
        amount_cents=15000,  # > total
        payment_method=PaymentMethod.CARD,
        payment_date=date.today()
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.add_payment(invoice.id, payment_data, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "exceed" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_invoice_service_cancel_paid_invoice_fails(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-008",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-004",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        total_amount_cents=10000,
        paid_amount_cents=10000,  # Payée
        status=InvoiceStatus.PAID
    )
    async_db.add(invoice)
    await async_db.flush()

    service = InvoiceService(async_db)

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_invoice(invoice.id, tenant_id=1)

    assert exc_info.value.status_code == 400
    assert "paid" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_invoice_service_list_overdue(async_db):
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
    async_db.add(customer)
    await async_db.flush()
    await async_db.refresh(customer)

    reservation = Reservation(
        tenant_id=1,
        customer_id=customer.id,
        reference="RES-TEST-009",
        event_date=date.today() + timedelta(days=10),
        delivery_date=date.today() + timedelta(days=9),
        return_date=date.today() + timedelta(days=11),
        event_location="Test",
        status=ReservationStatus.CONFIRMED,
        total_amount_cents=10000,
        deposit_amount_cents=5000,
        deposit_paid=False
    )
    async_db.add(reservation)
    await async_db.flush()
    await async_db.refresh(reservation)

    # Facture en retard (due_date passée)
    invoice = Invoice(
        tenant_id=1,
        reservation_id=reservation.id,
        invoice_number="INV-TEST-005",
        issue_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=15),  # Passée
        total_amount_cents=10000,
        paid_amount_cents=0,
        status=InvoiceStatus.SENT
    )
    async_db.add(invoice)
    await async_db.flush()

    service = InvoiceService(async_db)
    overdue = await service.list_overdue(tenant_id=1)

    assert len(overdue) >= 1
    assert any(inv.id == invoice.id for inv in overdue)
