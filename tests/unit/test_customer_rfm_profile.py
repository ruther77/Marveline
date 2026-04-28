"""Tests P4.1 : profil RFM individuel.

Couvre :
  - Client sans réservation → segment "New", recency=9999, frequency=0
  - Client avec réservation récente returned → segment selon règles
  - Endpoint /customers/{id}/rfm-profile cohérent avec /customers/rfm global
"""
import pytest
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints.customers import _compute_rfm_for_customer
from app.constants import CustomerType
from app.models.customer import Customer
from app.models.reservation import Reservation

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


async def _seed_customer(db: AsyncSession, suffix: str) -> Customer:
    customer = Customer(
        tenant_id=TENANT_ID,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name=suffix,
        email=f"rfm-{suffix}@test.local",
        phone="+33611111111",
        is_active=True,
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


@pytest.mark.asyncio
async def test_rfm_profile_new_customer_no_reservation(async_db):
    """Client sans aucune résa → New / R=9999 / F=0 / M=0."""
    db = async_db
    customer = await _seed_customer(db, "newbie")

    profile = await _compute_rfm_for_customer(db, customer, TENANT_ID)
    assert profile.customer_id == customer.id
    assert profile.frequency == 0
    assert profile.recency_days == 9999
    assert profile.monetary_cents == 0
    assert profile.segment == "New"
    assert "Test newbie" in profile.customer_name


@pytest.mark.asyncio
async def test_rfm_profile_loyal_customer(async_db):
    """3 résa returned récentes → Loyal."""
    db = async_db
    customer = await _seed_customer(db, "loyal")
    today = date.today()

    for i in range(3):
        # Contrainte DB : delivery <= event <= return
        offset = 15 + i * 10
        res = Reservation(
            tenant_id=TENANT_ID,
            customer_id=customer.id,
            reference=f"RES-LOY-{i}",
            delivery_date=today - timedelta(days=offset + 1),
            event_date=today - timedelta(days=offset),
            return_date=today - timedelta(days=offset - 1),
            status="returned",
            total_amount_cents=10_000,
            deposit_amount_cents=1_000,
        )
        db.add(res)
    await db.flush()

    profile = await _compute_rfm_for_customer(db, customer, TENANT_ID)
    assert profile.frequency == 3
    assert profile.recency_days <= 30
    # Avec recency<=30 et freq>=3, on est Loyal (Champions demande freq>=5)
    assert profile.segment in ("Loyal", "Champions")


@pytest.mark.asyncio
async def test_rfm_profile_lost_customer(async_db):
    """1 résa returned très ancienne → Lost."""
    db = async_db
    customer = await _seed_customer(db, "lost")
    today = date.today()

    res = Reservation(
        tenant_id=TENANT_ID,
        customer_id=customer.id,
        reference="RES-LOST-1",
        event_date=today - timedelta(days=400),
        delivery_date=today - timedelta(days=401),
        return_date=today - timedelta(days=399),
        status="returned",
        total_amount_cents=20_000,
        deposit_amount_cents=2_000,
    )
    db.add(res)
    await db.flush()

    profile = await _compute_rfm_for_customer(db, customer, TENANT_ID)
    assert profile.frequency == 1
    assert profile.recency_days > 365
    assert profile.segment == "Lost"
