"""Service métier pour les Ventes."""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from app.models.vente import Vente
from app.repositories.vente import VenteRepository
from app.schemas.vente import VenteCreate, VenteUpdate, VentePaymentCreate
from app.core.exceptions import NotFound, BadRequest
from app.constants import VenteStatus

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


def _get_or_404(repo: VenteRepository, vente_id: int, tenant_id: int) -> Vente:
    vente = repo.get_by_id_with_relations(vente_id, tenant_id)
    if not vente:
        raise NotFound(f"Vente {vente_id} introuvable")
    return vente


def create_vente(db: Session, tenant_id: int, data: VenteCreate) -> Vente:
    """Crée une vente et génère la référence."""
    repo = VenteRepository(db)
    reference = repo.generate_reference(tenant_id)
    vente = repo.create_vente(
        tenant_id=tenant_id,
        reference=reference,
        customer_id=data.customer_id,
        lines_data=[l.model_dump() for l in data.lines],
        deposit_pct=data.deposit_pct,
        payment_due_date=data.payment_due_date,
        notes=data.notes,
        invoice_id=data.invoice_id,
        reservation_id=data.reservation_id,
    )
    db.commit()
    db.refresh(vente)
    return vente


def get_vente(db: Session, tenant_id: int, vente_id: int) -> Vente:
    repo = VenteRepository(db)
    return _get_or_404(repo, vente_id, tenant_id)


def list_ventes(
    db: Session,
    tenant_id: int,
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    overdue_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Vente], int]:
    repo = VenteRepository(db)
    return repo.list_ventes(tenant_id, status, customer_id, overdue_only, skip, limit)


def update_vente(db: Session, tenant_id: int, vente_id: int, data: VenteUpdate) -> Vente:
    repo = VenteRepository(db)
    vente = _get_or_404(repo, vente_id, tenant_id)
    if vente.status not in (VenteStatus.DRAFT, VenteStatus.PENDING):
        raise BadRequest("Seules les ventes draft ou pending peuvent être modifiées")
    updates = data.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(vente, field, value)
    db.commit()
    db.refresh(vente)
    return vente


def add_payment(
    db: Session,
    tenant_id: int,
    vente_id: int,
    data: VentePaymentCreate,
    user_id: int,
):
    """Enregistre un paiement et met à jour le statut automatiquement."""
    repo = VenteRepository(db)
    vente = _get_or_404(repo, vente_id, tenant_id)

    if vente.status == VenteStatus.REFUNDED:
        raise BadRequest("Impossible d'enregistrer un paiement sur une vente remboursée")

    payment = repo.add_payment(
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

    db.commit()
    db.refresh(payment)
    return payment


def get_payments(db: Session, tenant_id: int, vente_id: int):
    repo = VenteRepository(db)
    _get_or_404(repo, vente_id, tenant_id)  # vérification existence + tenant
    return repo.get_payments(vente_id, tenant_id)


def refund_vente(db: Session, tenant_id: int, vente_id: int) -> Vente:
    """Transition vers REFUNDED."""
    repo = VenteRepository(db)
    vente = _get_or_404(repo, vente_id, tenant_id)
    allowed = VENTE_TRANSITIONS.get(vente.status, [])
    if VenteStatus.REFUNDED not in allowed:
        raise BadRequest(f"Transition {vente.status} → refunded invalide")
    vente.status = VenteStatus.REFUNDED
    db.commit()
    db.refresh(vente)
    return vente


def cancel_vente(db: Session, tenant_id: int, vente_id: int) -> Vente:
    """Transition vers CANCELLED."""
    repo = VenteRepository(db)
    vente = _get_or_404(repo, vente_id, tenant_id)
    allowed = VENTE_TRANSITIONS.get(vente.status, [])
    if VenteStatus.CANCELLED not in allowed:
        raise BadRequest(f"Transition {vente.status} → cancelled invalide")
    vente.status = VenteStatus.CANCELLED
    db.commit()
    db.refresh(vente)
    return vente


def get_overdue(db: Session, tenant_id: int, skip: int = 0, limit: int = 50):
    repo = VenteRepository(db)
    items, total = repo.list_ventes(tenant_id, overdue_only=True, skip=skip, limit=limit)
    return items, total
