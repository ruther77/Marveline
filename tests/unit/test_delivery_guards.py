"""Tests B + C — Guards livraison (acompte + signature) selon tenant_settings.

Couvre :
  1. assert_delivery_guards bloque si acompte non payé (block_delivery_without_advance=true).
  2. assert_delivery_guards bloque si signature absente (require_signature_before_delivery=true).
  3. Settings désactivés (B2B) → pas de blocage.
  4. Pas de tenant_settings du tout → fallback sur défauts (true/true).
  5. Acompte payé OK + signature OK → passe.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.constants import CustomerType, ReservationStatus
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.models.tenant_settings import TenantSettings
from app.services.reservation_workflow import assert_delivery_guards

from tests.conftest import ASYNC_TEST_DATABASE_URL

TENANT_ID = 1


@pytest.fixture
async def async_db(test_engine):
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed(
    db: AsyncSession,
    *,
    advance_required: int = 10000,
    advance_paid: int = 0,
    has_signature: bool = False,
    settings: TenantSettings | None = None,
) -> Reservation:
    customer = Customer(
        tenant_id=TENANT_ID,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Demo",
        last_name=f"Guard-{advance_required}-{advance_paid}-{has_signature}",
        email=f"guard-{advance_required}-{advance_paid}-{has_signature}@test.local",
        phone="+33611111111",
        is_active=True,
    )
    db.add(customer)
    await db.flush()

    today = date.today()
    res = Reservation(
        tenant_id=TENANT_ID,
        customer_id=customer.id,
        reference=f"RES-GUARD-{advance_required}-{advance_paid}-{int(has_signature)}",
        event_date=today + timedelta(days=10),
        delivery_date=today + timedelta(days=9),
        return_date=today + timedelta(days=11),
        status=ReservationStatus.PRE_CHECK,
        total_amount_cents=advance_required * 3,
        deposit_amount_cents=10_000,
        advance_payment_amount_cents=advance_required,
        signature_url="https://example.com/sig.png" if has_signature else None,
    )
    db.add(res)
    await db.flush()

    if advance_required > 0:
        invoice = Invoice(
            tenant_id=TENANT_ID,
            reservation_id=res.id,
            invoice_number=f"INV-GUARD-{res.id}",
            issue_date=today,
            due_date=today + timedelta(days=30),
            total_amount_cents=res.total_amount_cents,
            paid_amount_cents=advance_paid,
            status="paid" if advance_paid >= res.total_amount_cents else "sent",
        )
        db.add(invoice)
        await db.flush()

    if settings is not None:
        db.add(settings)
        await db.flush()

    await db.refresh(res)
    return res


@pytest.mark.asyncio
async def test_blocks_when_advance_not_paid(async_db, test_tenant_record):
    """Default settings (block_delivery_without_advance=True) → 422."""
    res = await _seed(
        async_db,
        advance_required=10_000,
        advance_paid=0,
        has_signature=True,  # signature OK pour isoler le check acompte
    )
    with pytest.raises(HTTPException) as exc:
        await assert_delivery_guards(async_db, res, TENANT_ID)
    assert exc.value.status_code == 422
    assert "Acompte" in exc.value.detail


@pytest.mark.asyncio
async def test_blocks_when_signature_missing(async_db, test_tenant_record):
    """Default settings (require_signature_before_delivery=True) + acompte OK → 422 sig."""
    res = await _seed(
        async_db,
        advance_required=10_000,
        advance_paid=10_000,  # acompte OK pour isoler le check signature
        has_signature=False,
    )
    with pytest.raises(HTTPException) as exc:
        await assert_delivery_guards(async_db, res, TENANT_ID)
    assert exc.value.status_code == 422
    assert "Signature" in exc.value.detail


@pytest.mark.asyncio
async def test_passes_when_both_ok(async_db, test_tenant_record):
    """Acompte payé + signature → pas d'exception."""
    res = await _seed(
        async_db,
        advance_required=10_000,
        advance_paid=10_000,
        has_signature=True,
    )
    # Ne lève pas
    await assert_delivery_guards(async_db, res, TENANT_ID)


@pytest.mark.asyncio
async def test_passes_when_settings_disable_both(async_db, test_tenant_record):
    """Tenant B2B avec guards désactivés → passe même sans acompte ni signature."""
    settings = TenantSettings(
        tenant_id=TENANT_ID,
        block_delivery_without_advance=False,
        require_signature_before_delivery=False,
    )
    res = await _seed(
        async_db,
        advance_required=10_000,
        advance_paid=0,
        has_signature=False,
        settings=settings,
    )
    await assert_delivery_guards(async_db, res, TENANT_ID)


@pytest.mark.asyncio
async def test_no_advance_required_no_block(async_db, test_tenant_record):
    """Resa sans advance_payment_amount_cents → guard acompte ne s'applique pas."""
    res = await _seed(
        async_db,
        advance_required=0,
        advance_paid=0,
        has_signature=True,
    )
    # Ne lève pas (pas d'acompte attendu)
    await assert_delivery_guards(async_db, res, TENANT_ID)
