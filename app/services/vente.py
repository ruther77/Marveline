"""Service métier pour les Ventes."""
from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import VenteStatus
from app.core.exceptions import BadRequest, NotFound
from app.models.vente import Vente
from app.repositories.vente import AsyncVenteRepository
from app.schemas.vente import VenteCreate, VentePaymentCreate, VenteUpdate

# Machine d'état des transitions
VENTE_TRANSITIONS: dict[str, list[str]] = {
    VenteStatus.DRAFT:        [VenteStatus.PENDING, VenteStatus.REFUNDED, VenteStatus.CANCELLED],
    VenteStatus.PENDING:      [VenteStatus.DEPOSIT_PAID, VenteStatus.FULLY_PAID, VenteStatus.OVERDUE, VenteStatus.REFUNDED, VenteStatus.CANCELLED],
    VenteStatus.DEPOSIT_PAID: [VenteStatus.FULLY_PAID, VenteStatus.OVERDUE, VenteStatus.REFUNDED, VenteStatus.CANCELLED],
    VenteStatus.FULLY_PAID:   [VenteStatus.REFUNDED],
    VenteStatus.OVERDUE:      [VenteStatus.FULLY_PAID, VenteStatus.REFUNDED, VenteStatus.CANCELLED],
    VenteStatus.REFUNDED:     [],
    VenteStatus.CANCELLED:    [],
}


async def _get_or_404(repo: AsyncVenteRepository, vente_id: int, tenant_id: int) -> Vente:
    vente = await repo.get_by_id_with_relations(vente_id, tenant_id)
    if not vente:
        raise NotFound(f"Vente {vente_id} introuvable")
    return vente


async def _refresh_overdue_statuses(
    db: AsyncSession, tenant_id: int, vente_id: Optional[int] = None
) -> int:
    """Active le statut `overdue` pour les ventes échues non soldées."""
    from sqlalchemy import update
    from app.models.vente import Vente

    stmt = (
        update(Vente)
        .where(
            Vente.tenant_id == tenant_id,
            Vente.is_active.is_(True),
            Vente.status.in_([VenteStatus.PENDING, VenteStatus.DEPOSIT_PAID]),
            Vente.payment_due_date.is_not(None),
            Vente.payment_due_date < date.today(),
            Vente.paid_cents < Vente.total_cents,
        )
        .values(status=VenteStatus.OVERDUE)
    )
    if vente_id is not None:
        stmt = stmt.where(Vente.id == vente_id)

    result = await db.execute(stmt)
    return result.rowcount or 0


async def create_vente(db: AsyncSession, tenant_id: int, data: VenteCreate) -> Vente:
    """Crée une vente et génère la référence."""
    repo = AsyncVenteRepository(db)
    reference = await repo.generate_reference(tenant_id)
    vente = await repo.create_vente(
        tenant_id=tenant_id,
        reference=reference,
        customer_id=data.customer_id,
        lines_data=[line.model_dump() for line in data.lines],
        deposit_pct=data.deposit_pct,
        payment_due_date=data.payment_due_date,
        notes=data.notes,
        invoice_id=data.invoice_id,
        reservation_id=data.reservation_id,
    )
    await db.commit()
    return await _get_or_404(repo, vente.id, tenant_id)


async def get_vente(db: AsyncSession, tenant_id: int, vente_id: int) -> Vente:
    repo = AsyncVenteRepository(db)
    updated = await _refresh_overdue_statuses(db, tenant_id, vente_id=vente_id)
    if updated:
        await db.commit()
    return await _get_or_404(repo, vente_id, tenant_id)


async def list_ventes(
    db: AsyncSession,
    tenant_id: int,
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    overdue_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Vente], int]:
    repo = AsyncVenteRepository(db)
    updated = await _refresh_overdue_statuses(db, tenant_id)
    if updated:
        await db.commit()
    return await repo.list_ventes(
        tenant_id=tenant_id,
        status=status,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        overdue_only=overdue_only,
        skip=skip,
        limit=limit,
    )


async def update_vente(
    db: AsyncSession, tenant_id: int, vente_id: int, data: VenteUpdate
) -> Vente:
    repo = AsyncVenteRepository(db)
    vente = await _get_or_404(repo, vente_id, tenant_id)
    if vente.status not in (VenteStatus.DRAFT, VenteStatus.PENDING):
        raise BadRequest("Seules les ventes draft ou pending peuvent être modifiées")
    updates = data.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(vente, field, value)
    await db.commit()
    return await _get_or_404(repo, vente_id, tenant_id)


async def add_payment(
    db: AsyncSession,
    tenant_id: int,
    vente_id: int,
    data: VentePaymentCreate,
    user_id: int,
):
    """Enregistre un paiement et met à jour le statut automatiquement."""
    repo = AsyncVenteRepository(db)
    vente = await _get_or_404(repo, vente_id, tenant_id)

    if vente.status == VenteStatus.REFUNDED:
        raise BadRequest("Impossible d'enregistrer un paiement sur une vente remboursée")

    payment = await repo.add_payment(
        vente=vente,
        tenant_id=tenant_id,
        amount_cents=data.amount_cents,
        payment_method=data.payment_method,
        payment_date=data.payment_date,
        is_deposit=data.is_deposit,
        created_by=user_id,
        notes=data.notes,
    )

    # Auto-transition statut
    if vente.paid_cents >= vente.total_cents:
        vente.status = VenteStatus.FULLY_PAID
    elif data.is_deposit and vente.status == VenteStatus.PENDING:
        vente.status = VenteStatus.DEPOSIT_PAID
    elif vente.status == VenteStatus.DRAFT:
        vente.status = VenteStatus.PENDING

    await db.commit()
    await db.refresh(payment)
    return payment


async def get_payments(db: AsyncSession, tenant_id: int, vente_id: int):
    repo = AsyncVenteRepository(db)
    await _get_or_404(repo, vente_id, tenant_id)  # vérification existence + tenant
    return await repo.get_payments(vente_id, tenant_id)


async def refund_vente(db: AsyncSession, tenant_id: int, vente_id: int) -> Vente:
    """Transition vers REFUNDED."""
    repo = AsyncVenteRepository(db)
    vente = await _get_or_404(repo, vente_id, tenant_id)
    allowed = VENTE_TRANSITIONS.get(vente.status, [])
    if VenteStatus.REFUNDED not in allowed:
        raise BadRequest(f"Transition {vente.status} → refunded invalide")
    vente.status = VenteStatus.REFUNDED
    await db.commit()
    return await _get_or_404(repo, vente_id, tenant_id)


async def cancel_vente(db: AsyncSession, tenant_id: int, vente_id: int) -> Vente:
    """Transition vers CANCELLED."""
    repo = AsyncVenteRepository(db)
    vente = await _get_or_404(repo, vente_id, tenant_id)
    allowed = VENTE_TRANSITIONS.get(vente.status, [])
    if VenteStatus.CANCELLED not in allowed:
        raise BadRequest(f"Transition {vente.status} → cancelled invalide")
    vente.status = VenteStatus.CANCELLED
    await db.commit()
    return await _get_or_404(repo, vente_id, tenant_id)


async def get_overdue(db: AsyncSession, tenant_id: int, skip: int = 0, limit: int = 50):
    repo = AsyncVenteRepository(db)
    updated = await _refresh_overdue_statuses(db, tenant_id)
    if updated:
        await db.commit()
    items, total = await repo.list_ventes(tenant_id, overdue_only=True, skip=skip, limit=limit)
    return items, total
