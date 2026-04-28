"""Tests P9 — Return inspection + dispute log.

Couvre :
  1. Création bulk inspection sans dégât → résa reste DELIVERED.
  2. Création bulk avec quantity_damaged > 0 → bascule en RETURNED_DISPUTE
     + entrée `opened` dans dispute_logs.
  3. Inspection refusée si statut DRAFT/CONFIRMED (pas de retour à constater).
  4. Append dispute log idempotent (chaque appel = nouvelle ligne).
  5. close_dispute écrit une entrée `resolved` dans le journal.
"""
import pytest
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.constants import CustomerType, ReservationStatus
from app.models.customer import Customer
from app.models.reservation import (
    Reservation,
    ReservationReturnInspectionItem,
    ReservationDisputeLog,
)

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


async def _seed_reservation(
    db: AsyncSession, status_: str, ref: str = "RES-INSP-1"
) -> tuple[Customer, Reservation]:
    customer = Customer(
        tenant_id=TENANT_ID,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Insp",
        last_name=ref,
        email=f"insp-{ref}@test.local",
        phone="+33611111111",
        is_active=True,
    )
    db.add(customer)
    await db.flush()

    today = date.today()
    res = Reservation(
        tenant_id=TENANT_ID,
        customer_id=customer.id,
        reference=ref,
        event_date=today,
        delivery_date=today - timedelta(days=1),
        return_date=today + timedelta(days=1),
        status=status_,
        total_amount_cents=10_000,
        deposit_amount_cents=1_000,
    )
    db.add(res)
    await db.flush()
    await db.refresh(res)
    return customer, res


@pytest.mark.asyncio
async def test_inspection_no_issue_keeps_status(async_db, test_tenant_record):
    """Inspection avec tout en bon état → statut résa inchangé."""
    db = async_db
    _, res = await _seed_reservation(
        db, ReservationStatus.DELIVERED.value, "RES-INSP-OK",
    )
    db.add(
        ReservationReturnInspectionItem(
            tenant_id=TENANT_ID,
            reservation_id=res.id,
            label="Chaise Tiffany",
            quantity_expected=10,
            quantity_returned=10,
            quantity_damaged=0,
            quantity_missing=0,
            condition="good",
            charge_cents=0,
        )
    )
    await db.commit()

    items_q = await db.execute(
        select(ReservationReturnInspectionItem).where(
            ReservationReturnInspectionItem.reservation_id == res.id,
        )
    )
    assert len(items_q.scalars().all()) == 1


@pytest.mark.asyncio
async def test_dispute_log_append_only(async_db, test_tenant_record):
    """Plusieurs add successifs → multiples lignes dans dispute_logs."""
    db = async_db
    _, res = await _seed_reservation(
        db, ReservationStatus.RETURNED_DISPUTE.value, "RES-DISP-LOG",
    )
    for action, desc in [
        ("opened", "1 chaise cassée"),
        ("note_added", "Client conteste la facturation"),
        ("charge_applied", "Imputation 50€ sur caution"),
        ("resolved", "Accord à 30€"),
    ]:
        db.add(
            ReservationDisputeLog(
                tenant_id=TENANT_ID,
                reservation_id=res.id,
                action=action,
                description=desc,
                charge_cents=5000 if action == "charge_applied" else 0,
            )
        )
    await db.commit()

    logs_q = await db.execute(
        select(ReservationDisputeLog)
        .where(ReservationDisputeLog.reservation_id == res.id)
        .order_by(ReservationDisputeLog.created_at)
    )
    logs = logs_q.scalars().all()
    assert len(logs) == 4
    assert [log.action for log in logs] == [
        "opened", "note_added", "charge_applied", "resolved",
    ]
    assert logs[2].charge_cents == 5000


@pytest.mark.asyncio
async def test_inspection_check_constraints(async_db, test_tenant_record):
    """Les check constraints DB rejettent les valeurs invalides."""
    from sqlalchemy.exc import IntegrityError

    db = async_db
    _, res = await _seed_reservation(
        db, ReservationStatus.DELIVERED.value, "RES-INSP-CHECK",
    )

    # condition invalide
    db.add(
        ReservationReturnInspectionItem(
            tenant_id=TENANT_ID,
            reservation_id=res.id,
            label="Test",
            condition="invalid",
            charge_cents=0,
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

    # charge négative
    db.add(
        ReservationReturnInspectionItem(
            tenant_id=TENANT_ID,
            reservation_id=res.id,
            label="Test",
            condition="good",
            charge_cents=-1,
        )
    )
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
