"""Tests P1 — Phase 1 : verrouillage résa convertie + release stock ciblé.

Couvre :
  1. ``release_n(reservation_id=...)`` filtre par résa : annuler résa A
     ne libère pas les items réservés pour résa B (bug structurel trou 9).
  2. ``release_n(reservation_id=X)`` raise si aucun item ne correspond.
  3. ``update_reservation`` 409 sur champs périmétriques quand devis_id != None.
  4. ``update_reservation`` autorise les champs opérationnels quand devis_id != None.
  5. ``update_reservation`` libre quand devis_id is None (legacy).
"""
import pytest
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.constants import (
    CustomerType,
    ProductCategory,
    ProductCondition,
    ReservationStatus,
)
from app.models.customer import Customer
from app.models.product import Product
from app.models.reservation import Reservation
from app.models.stock_item import StockItem
from app.repositories.stock_item import AsyncStockItemRepository
from app.schemas.reservation import ReservationUpdate
from app.services.reservation import ReservationService

from tests.conftest import ASYNC_TEST_DATABASE_URL

TENANT_ID = 1


# ── Fixtures ──────────────────────────────────────────────────────────────────


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
        email=f"reslock-{suffix}@test.local",
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
    devis_id: int | None,
) -> Reservation:
    today = date.today()
    res = Reservation(
        tenant_id=TENANT_ID,
        customer_id=customer_id,
        reference=reference,
        event_date=today + timedelta(days=10),
        delivery_date=today + timedelta(days=9),
        return_date=today + timedelta(days=11),
        status=ReservationStatus.DRAFT,
        total_amount_cents=10_000,
        deposit_amount_cents=1_000,
        devis_id=devis_id,
    )
    db.add(res)
    await db.flush()
    await db.refresh(res)
    return res


# ── Tests release_n ciblé (trou 9) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_release_n_only_releases_items_of_target_reservation(async_db):
    """Annuler la résa A ne libère QUE l'item de la résa A (pas ceux de la résa B)."""
    db = async_db
    customer = await _seed_customer(db, "rel-multi")
    res_a = await _seed_reservation(db, customer.id, "RES-REL-A", devis_id=None)
    res_b = await _seed_reservation(db, customer.id, "RES-REL-B", devis_id=None)

    product = Product(
        tenant_id=TENANT_ID,
        name="Trône Royal Test",
        sku="TRONE-LOCK-001",
        category=ProductCategory.DECORATIONS,
        price_per_day_cents=10_000,
        deposit_amount_cents=20_000,
        stock_quantity=4,
        available_quantity=0,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    db.add(product)
    await db.flush()

    # 1 item réservé pour la résa A, 3 items réservés pour la résa B
    for i in range(4):
        db.add(StockItem(
            tenant_id=TENANT_ID,
            product_id=product.id,
            serial_number=f"TRONE-LOCK-{i + 1:03d}",
            status="reserved",
            current_reservation_id=(res_a.id if i == 0 else res_b.id),
        ))
    await db.flush()

    repo = AsyncStockItemRepository(db)
    released = await repo.release_n(
        product_id=product.id,
        n=1,
        tenant_id=TENANT_ID,
        reservation_id=res_a.id,
    )

    assert len(released) == 1
    assert released[0].current_reservation_id is None
    assert released[0].status == "available"

    # Les 3 items de la résa B doivent rester intacts
    result = await db.execute(
        select(StockItem).where(
            StockItem.product_id == product.id,
            StockItem.status == "reserved",
        )
    )
    still_reserved = list(result.scalars().all())
    assert len(still_reserved) == 3
    assert all(it.current_reservation_id == res_b.id for it in still_reserved)


@pytest.mark.asyncio
async def test_release_n_raises_when_reservation_id_has_no_match(async_db):
    """``reservation_id`` qui ne pointe sur aucun item → ValueError."""
    db = async_db
    customer = await _seed_customer(db, "rel-no-match")
    res_b = await _seed_reservation(db, customer.id, "RES-REL-NM", devis_id=None)

    product = Product(
        tenant_id=TENANT_ID,
        name="X",
        sku="X-LOCK-001",
        category=ProductCategory.DECORATIONS,
        price_per_day_cents=100,
        deposit_amount_cents=100,
        stock_quantity=1,
        available_quantity=0,
        condition=ProductCondition.NEUF,
        is_active=True,
    )
    db.add(product)
    await db.flush()
    db.add(StockItem(
        tenant_id=TENANT_ID,
        product_id=product.id,
        serial_number="X-LOCK-001",
        status="reserved",
        current_reservation_id=res_b.id,
    ))
    await db.flush()

    repo = AsyncStockItemRepository(db)
    # ID de résa inexistant → 0 items match → ValueError
    nonexistent_res_id = res_b.id + 999
    with pytest.raises(ValueError, match="seulement 0"):
        await repo.release_n(
            product_id=product.id,
            n=1,
            tenant_id=TENANT_ID,
            reservation_id=nonexistent_res_id,
        )


# ── Tests guard update_reservation (trou 8) ───────────────────────────────────


@pytest.mark.asyncio
async def test_update_reservation_locked_blocks_perimetric_fields(async_db):
    """Résa avec devis_id : modif event_date → 409 avec liste des forbidden."""
    db = async_db
    customer = await _seed_customer(db, "perim")
    res = await _seed_reservation(db, customer.id, "RES-LOCK-PERIM", devis_id=42)

    service = ReservationService(db)
    today = date.today()

    with pytest.raises(HTTPException) as exc_info:
        await service.update_reservation(
            reservation_id=res.id,
            reservation_data=ReservationUpdate(
                event_date=today + timedelta(days=30),
            ),
            tenant_id=TENANT_ID,
        )

    assert exc_info.value.status_code == 409
    assert "event_date" in exc_info.value.detail
    assert "amend" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_update_reservation_locked_allows_operational_fields(async_db):
    """Résa avec devis_id : notes + delivery_address autorisés (whitelist)."""
    db = async_db
    customer = await _seed_customer(db, "ops")
    res = await _seed_reservation(db, customer.id, "RES-LOCK-OPS", devis_id=42)

    service = ReservationService(db)
    updated = await service.update_reservation(
        reservation_id=res.id,
        reservation_data=ReservationUpdate(
            notes="Note interne post-conversion",
            delivery_address="3 rue Pasteur 75011 Paris",
        ),
        tenant_id=TENANT_ID,
    )

    assert updated.notes == "Note interne post-conversion"
    assert updated.delivery_address == "3 rue Pasteur 75011 Paris"


@pytest.mark.asyncio
async def test_update_reservation_locked_mixed_fields_blocks_all(async_db):
    """Mix périmétrique + opérationnel → 409 (rien n'est appliqué)."""
    db = async_db
    customer = await _seed_customer(db, "mix")
    res = await _seed_reservation(db, customer.id, "RES-LOCK-MIX", devis_id=42)
    original_notes = res.notes

    service = ReservationService(db)
    today = date.today()

    with pytest.raises(HTTPException) as exc_info:
        await service.update_reservation(
            reservation_id=res.id,
            reservation_data=ReservationUpdate(
                notes="Devrait pas être appliquée",
                delivery_date=today + timedelta(days=20),
            ),
            tenant_id=TENANT_ID,
        )
    assert exc_info.value.status_code == 409

    # Vérif que rien n'a été appliqué (rollback transactionnel)
    await db.refresh(res)
    assert res.notes == original_notes


@pytest.mark.asyncio
async def test_update_reservation_without_devis_allows_all_fields(async_db):
    """Résa sans devis_id : modifications libres (legacy)."""
    db = async_db
    customer = await _seed_customer(db, "free")
    res = await _seed_reservation(db, customer.id, "RES-FREE", devis_id=None)

    service = ReservationService(db)
    # Pour respecter check_reservation_return_after_event, on déplace tout le triplet
    new_delivery = res.delivery_date + timedelta(days=10)
    new_event = res.event_date + timedelta(days=10)
    new_return = res.return_date + timedelta(days=10)
    updated = await service.update_reservation(
        reservation_id=res.id,
        reservation_data=ReservationUpdate(
            delivery_date=new_delivery,
            event_date=new_event,
            return_date=new_return,
        ),
        tenant_id=TENANT_ID,
    )
    assert updated.event_date == new_event
    assert updated.return_date == new_return


# ── Tests amend_reservation (Phase 2.3) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_amend_rejects_reservation_without_devis(async_db):
    """``amend_reservation`` sur résa sans devis_id → 400."""
    db = async_db
    customer = await _seed_customer(db, "amend-no-devis")
    res = await _seed_reservation(db, customer.id, "RES-AMEND-ND", devis_id=None)

    from app.schemas.reservation import ReservationAmendRequest
    service = ReservationService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.amend_reservation(
            reservation_id=res.id,
            payload=ReservationAmendRequest(
                reason="Test rejet sans devis",
                event_date=date.today() + timedelta(days=15),
            ),
            tenant_id=TENANT_ID,
            user_id=1,
        )
    assert exc_info.value.status_code == 400
    assert "n'est pas issue d'un devis" in exc_info.value.detail


@pytest.mark.asyncio
async def test_amend_rejects_terminal_reservation(async_db):
    """``amend_reservation`` sur résa COMPLETED/CANCELLED → 400."""
    db = async_db
    customer = await _seed_customer(db, "amend-terminal")
    res = await _seed_reservation(db, customer.id, "RES-AMEND-TERM", devis_id=42)
    res.status = ReservationStatus.CANCELLED
    await db.flush()

    from app.schemas.reservation import ReservationAmendRequest
    service = ReservationService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.amend_reservation(
            reservation_id=res.id,
            payload=ReservationAmendRequest(
                reason="Tentative sur cancelled",
                event_date=date.today() + timedelta(days=15),
            ),
            tenant_id=TENANT_ID,
            user_id=1,
        )
    assert exc_info.value.status_code == 400
    assert "Avenant impossible" in exc_info.value.detail


@pytest.mark.asyncio
async def test_amend_with_orphan_devis_id_returns_404(async_db):
    """devis_id renseigné mais devis inexistant → 404 (résa orpheline)."""
    db = async_db
    customer = await _seed_customer(db, "amend-orphan")
    res = await _seed_reservation(db, customer.id, "RES-AMEND-ORPH", devis_id=99999)

    from app.schemas.reservation import ReservationAmendRequest
    service = ReservationService(db)
    with pytest.raises(HTTPException) as exc_info:
        await service.amend_reservation(
            reservation_id=res.id,
            payload=ReservationAmendRequest(
                reason="Tentative sur résa orpheline",
                event_date=date.today() + timedelta(days=15),
            ),
            tenant_id=TENANT_ID,
            user_id=1,
        )
    assert exc_info.value.status_code == 404
    assert "Devis source" in exc_info.value.detail


@pytest.mark.asyncio
async def test_amend_appends_reason_to_notes(async_db):
    """Avenant valide : raison concaténée dans notes."""
    db = async_db
    # On crée un devis réel + une résa liée pour pouvoir snapshot
    customer = await _seed_customer(db, "amend-ok")
    today = date.today()

    from app.models.devis import Devis
    devis = Devis(
        tenant_id=TENANT_ID,
        customer_id=customer.id,
        reference="DEV-AMEND-001",
        status="sent",
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

    res = await _seed_reservation(db, customer.id, "RES-AMEND-OK", devis_id=devis.id)
    res.notes = "Note initiale"
    await db.flush()

    from app.schemas.reservation import ReservationAmendRequest
    service = ReservationService(db)
    new_event = today + timedelta(days=30)
    new_delivery = today + timedelta(days=29)
    new_return = today + timedelta(days=31)
    updated = await service.amend_reservation(
        reservation_id=res.id,
        payload=ReservationAmendRequest(
            reason="Client demande report 10 jours",
            event_date=new_event,
            delivery_date=new_delivery,
            return_date=new_return,
        ),
        tenant_id=TENANT_ID,
        user_id=1,
    )

    assert updated.event_date == new_event
    assert "Note initiale" in updated.notes
    assert "Avenant" in updated.notes
    assert "Client demande report 10 jours" in updated.notes


@pytest.mark.asyncio
async def test_amend_creates_new_devis_version(async_db):
    """Avenant valide : DevisVersion supplémentaire créée pre-amend."""
    db = async_db
    customer = await _seed_customer(db, "amend-version")
    today = date.today()

    from app.models.devis import Devis, DevisVersion
    devis = Devis(
        tenant_id=TENANT_ID,
        customer_id=customer.id,
        reference="DEV-AMEND-VER",
        status="sent",
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

    res = await _seed_reservation(db, customer.id, "RES-AMEND-VER", devis_id=devis.id)

    # Compte les versions avant
    before = await db.execute(
        select(DevisVersion).where(DevisVersion.devis_id == devis.id)
    )
    count_before = len(list(before.scalars().all()))

    from app.schemas.reservation import ReservationAmendRequest
    service = ReservationService(db)
    await service.amend_reservation(
        reservation_id=res.id,
        payload=ReservationAmendRequest(
            reason="Snapshot avenant",
            event_date=today + timedelta(days=25),
            delivery_date=today + timedelta(days=24),
            return_date=today + timedelta(days=26),
        ),
        tenant_id=TENANT_ID,
        user_id=1,
    )

    after = await db.execute(
        select(DevisVersion).where(DevisVersion.devis_id == devis.id)
    )
    count_after = len(list(after.scalars().all()))
    assert count_after == count_before + 1
