"""Tests P8 — Detection auto risques (Celery beat).

Couvre :
  1. detect_reservation_risks_daily cree un risque `deposit_missing` quand
     event_date <= J+7 et aucune caution encaissee.
  2. Idempotence : run 2x ne duplique pas le risque (existing actif filtre).
  3. Reservations hors fenetre J-7 ou statut DRAFT/CANCELLED ignorees.
"""
import pytest
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.constants import CustomerType, ReservationStatus
from app.models.customer import Customer
from app.models.reservation import Reservation, ReservationRisk
from app.tasks.risk_detection import _run_detection

from tests.conftest import ASYNC_TEST_DATABASE_URL

TENANT_ID = 1


@pytest.fixture
async def async_db(test_engine, monkeypatch):
    """Fixture async session + monkeypatch AsyncSessionLocal pour la tâche Celery.

    `_run_detection` ouvre sa propre session via `AsyncSessionLocal()`. On la
    pointe vers le même engine de test pour que les commits soient visibles
    par la session du test.
    """
    engine = create_async_engine(
        ASYNC_TEST_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )
    from app.core import database as db_module
    monkeypatch.setattr(db_module, "AsyncSessionLocal", session_factory)

    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed_customer(db: AsyncSession, suffix: str) -> Customer:
    customer = Customer(
        tenant_id=TENANT_ID,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Risk",
        last_name=suffix,
        email=f"risk-{suffix}@test.local",
        phone="+33611111111",
        is_active=True,
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


async def _seed_reservation(
    db: AsyncSession,
    customer_id: int,
    reference: str,
    event_offset_days: int,
    status: str = ReservationStatus.CONFIRMED.value,
) -> Reservation:
    today = date.today()
    event_date = today + timedelta(days=event_offset_days)
    res = Reservation(
        tenant_id=TENANT_ID,
        customer_id=customer_id,
        reference=reference,
        event_date=event_date,
        delivery_date=event_date - timedelta(days=1),
        return_date=event_date + timedelta(days=1),
        status=status,
        total_amount_cents=10_000,
        deposit_amount_cents=1_000,
    )
    db.add(res)
    await db.flush()
    await db.refresh(res)
    return res


@pytest.mark.asyncio
async def test_detect_creates_deposit_missing_risk_within_7_days(async_db, test_tenant_record):
    """Resa CONFIRMED sans caution avec event_date a J+5 -> risque cree."""
    db = async_db
    customer = await _seed_customer(db, "j5")
    res = await _seed_reservation(db, customer.id, "RES-RISK-J5", event_offset_days=5)
    await db.commit()

    result = await _run_detection()

    assert result["created"] >= 1

    risks_q = await db.execute(
        select(ReservationRisk).where(
            ReservationRisk.reservation_id == res.id,
            ReservationRisk.type == "deposit_missing",
        )
    )
    risks = risks_q.scalars().all()
    assert len(risks) == 1
    assert risks[0].severity == "high"
    assert risks[0].blocking is True


@pytest.mark.asyncio
async def test_detect_is_idempotent_does_not_duplicate(async_db, test_tenant_record):
    """Run 2x consecutifs -> 1 seul risque actif (dedup par type non resolu)."""
    db = async_db
    customer = await _seed_customer(db, "idem")
    res = await _seed_reservation(db, customer.id, "RES-RISK-IDEM", event_offset_days=3)
    await db.commit()

    await _run_detection()
    await _run_detection()

    risks_q = await db.execute(
        select(ReservationRisk).where(
            ReservationRisk.reservation_id == res.id,
            ReservationRisk.type == "deposit_missing",
        )
    )
    risks = risks_q.scalars().all()
    assert len(risks) == 1


@pytest.mark.asyncio
async def test_detect_ignores_far_future_and_draft(async_db, test_tenant_record):
    """Resa J+30 ou DRAFT/CANCELLED -> aucun risque cree."""
    db = async_db
    customer = await _seed_customer(db, "skip")
    res_far = await _seed_reservation(
        db, customer.id, "RES-RISK-FAR", event_offset_days=30,
    )
    res_draft = await _seed_reservation(
        db, customer.id, "RES-RISK-DRAFT",
        event_offset_days=3, status=ReservationStatus.DRAFT.value,
    )
    await db.commit()

    await _run_detection()

    for rid in (res_far.id, res_draft.id):
        risks_q = await db.execute(
            select(ReservationRisk).where(ReservationRisk.reservation_id == rid)
        )
        assert len(risks_q.scalars().all()) == 0
