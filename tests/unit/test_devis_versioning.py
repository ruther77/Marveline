"""Tests P2.1 : snapshots de versions auto à accept et convert.

Couvre :
  - ``DevisService.accept(user_id=...)`` crée une nouvelle DevisVersion.
  - Les snapshots sont strictement séquentiels (V1 send, V2 accept).
"""
import pytest
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.constants import CustomerType, DevisStatus
from app.models.customer import Customer
from app.models.devis import Devis, DevisVersion
from app.services.devis import DevisService

from tests.conftest import ASYNC_TEST_DATABASE_URL

TENANT_ID = 1
USER_ID = 1


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


async def _seed_devis_sent(db: AsyncSession, suffix: str) -> Devis:
    """Crée un devis en statut SENT (avec V1 snapshot déjà créée par send())."""
    customer = Customer(
        tenant_id=TENANT_ID,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="V",
        last_name=suffix,
        email=f"version-{suffix}@test.local",
        phone="+33611111111",
        is_active=True,
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)

    today = date.today()
    devis = Devis(
        tenant_id=TENANT_ID,
        customer_id=customer.id,
        reference=f"DEV-VER-{suffix}",
        status=DevisStatus.DRAFT,
        valid_until=today + timedelta(days=30),
        delivery_date=today + timedelta(days=20),
        return_date=today + timedelta(days=22),
        event_date=today + timedelta(days=21),
        event_location="Test",
        subtotal_cents=10_000,
        tva_cents=2_000,
        tva_rate=20,
        total_cents=12_000,
    )
    db.add(devis)
    await db.flush()
    await db.refresh(devis)

    # send : draft → sent + V1
    svc = DevisService(db)
    await svc.send(devis.id, TENANT_ID, user_id=USER_ID)
    return devis


async def _count_versions(db: AsyncSession, devis_id: int) -> int:
    result = await db.execute(
        select(DevisVersion).where(DevisVersion.devis_id == devis_id)
    )
    return len(list(result.scalars().all()))


@pytest.mark.asyncio
async def test_accept_creates_a_new_version_snapshot(async_db):
    """`accept()` doit ajouter une 2ᵉ version (V1 = send, V2 = accept)."""
    db = async_db
    devis = await _seed_devis_sent(db, "accept")
    assert await _count_versions(db, devis.id) == 1  # V1 créée par send()

    svc = DevisService(db)
    accepted = await svc.accept(devis.id, TENANT_ID, user_id=USER_ID)

    assert accepted.status == DevisStatus.ACCEPTED
    assert await _count_versions(db, devis.id) == 2

    # La V2 doit avoir version_number = 2
    result = await db.execute(
        select(DevisVersion)
        .where(DevisVersion.devis_id == devis.id)
        .order_by(DevisVersion.version_number.desc())
    )
    versions = list(result.scalars().all())
    assert versions[0].version_number == 2
    assert versions[0].snapshot_json["status"] == DevisStatus.ACCEPTED


@pytest.mark.asyncio
async def test_list_versions_enriches_created_by_name(async_db):
    """``list_versions`` expose ``created_by_name`` (first_name + last_name)."""
    db = async_db
    # Crée un Account réel
    from app.models.account import Account
    account = Account(
        email=f"author-{id(db)}@test.local",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$fake",
        first_name="Alice",
        last_name="Auteur",
        is_active=True,
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)

    devis = await _seed_devis_sent(db, "enrich-name")
    svc = DevisService(db)
    # Force la version V1 à pointer sur notre Account de test
    result = await db.execute(
        select(DevisVersion).where(DevisVersion.devis_id == devis.id)
    )
    v1 = result.scalar_one()
    v1.created_by = account.id
    await db.flush()

    versions = await svc.list_versions(devis.id, TENANT_ID)
    assert len(versions) >= 1
    assert versions[0].created_by_name == "Alice Auteur"


@pytest.mark.asyncio
async def test_accept_idempotent_does_not_double_snapshot(async_db):
    """Tenter d'accepter un devis déjà accepté → erreur, pas de V supplémentaire."""
    db = async_db
    devis = await _seed_devis_sent(db, "idem")

    svc = DevisService(db)
    await svc.accept(devis.id, TENANT_ID, user_id=USER_ID)
    assert await _count_versions(db, devis.id) == 2

    # 2ᵉ accept : doit échouer (FSM accepted -> accepted interdit)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await svc.accept(devis.id, TENANT_ID, user_id=USER_ID)
    assert exc_info.value.status_code == 400

    # Toujours 2 versions (pas 3)
    assert await _count_versions(db, devis.id) == 2
