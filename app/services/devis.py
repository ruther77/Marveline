"""Service Devis — logique métier et transitions d'état."""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.devis import (
    Devis, DevisLine, DevisModule, DevisPhase,
    DevisNegotiation, DevisChangeRequest,
)
from app.models.reservation import Reservation, ReservationLine
from app.repositories.devis import DevisRepository
from app.repositories.customer import CustomerRepository
from app.repositories.reservation import ReservationRepository
from app.schemas.devis import (
    DevisCreate, DevisUpdate, DevisConvert,
    DevisModuleCreate, DevisModuleUpdate,
    DevisPhaseCreate, DevisPhaseUpdate,
    DevisNegotiationCreate,
    DevisChangeRequestCreate, DevisChangeRequestUpdate,
)
from app.constants import DevisStatus, ReservationStatus

logger = logging.getLogger(__name__)

# Transitions autorisées par statut
DEVIS_TRANSITIONS: dict[str, list[str]] = {
    DevisStatus.DRAFT:          [DevisStatus.SENT, DevisStatus.CANCELLED],
    DevisStatus.SENT:           [DevisStatus.NEGOTIATION, DevisStatus.ACCEPTED,
                                  DevisStatus.REFUSED, DevisStatus.EXPIRED],
    DevisStatus.NEGOTIATION:    [DevisStatus.ACCEPTED, DevisStatus.REFUSED,
                                  DevisStatus.EXPIRED, DevisStatus.VERSION_PENDING],
    DevisStatus.VERSION_PENDING: [DevisStatus.NEGOTIATION, DevisStatus.ACCEPTED,
                                   DevisStatus.REFUSED],
    DevisStatus.ACCEPTED:       [DevisStatus.CONVERTED, DevisStatus.CANCELLED],
    DevisStatus.REFUSED:        [],
    DevisStatus.EXPIRED:        [DevisStatus.DRAFT],
    DevisStatus.CONVERTED:      [],
    DevisStatus.CANCELLED:      [],
}


def _assert_transition(devis: Devis, new_status: str) -> None:
    """Valide une transition de statut ou lève HTTPException 400.

    Args:
        devis: Instance Devis actuelle
        new_status: Nouveau statut demandé

    Raises:
        HTTPException 400 si la transition est invalide
    """
    allowed = DEVIS_TRANSITIONS.get(devis.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Transition '{devis.status}' → '{new_status}' invalide. "
                f"Transitions autorisées : {allowed or 'aucune'}"
            ),
        )


class DevisService:
    """Service pour la gestion des devis commerciaux."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DevisRepository(db)

    def _get_or_404(self, devis_id: int, tenant_id: int) -> Devis:
        devis = self.repo.get_by_id_full(devis_id, tenant_id)
        if not devis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Devis {devis_id} introuvable"
            )
        return devis

    def _get_customer_or_404(self, customer_id: int, tenant_id: int):
        repo = CustomerRepository(self.db)
        customer = repo.get_by_id(customer_id, tenant_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client {customer_id} introuvable"
            )
        return customer

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(self, tenant_id: int, data: DevisCreate) -> Devis:
        """Crée un devis avec ses lignes et génère la référence.

        Args:
            tenant_id: ID du tenant
            data: Données de création du devis

        Returns:
            Devis créé avec référence DEV-YYYY-NNNN
        """
        self._get_customer_or_404(data.customer_id, tenant_id)
        reference = self.repo.generate_reference(tenant_id)
        devis_data = data.model_dump(exclude={"lines"})
        lines_data = [line.model_dump() for line in data.lines]
        devis = self.repo.create_with_lines(tenant_id, devis_data, lines_data, reference)
        self.db.commit()
        self.db.refresh(devis)
        logger.info("Devis %d créé (ref=%s, tenant=%d)", devis.id, reference, tenant_id)
        return self.repo.get_by_id_full(devis.id, tenant_id)

    def get(self, devis_id: int, tenant_id: int) -> Devis:
        return self._get_or_404(devis_id, tenant_id)

    def list(
        self,
        tenant_id: int,
        status: Optional[str] = None,
        customer_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Devis]:
        return self.repo.list_by_tenant(
            tenant_id, status=status, customer_id=customer_id,
            skip=skip, limit=limit,
        )

    def update(self, devis_id: int, tenant_id: int, data: DevisUpdate) -> Devis:
        """Met à jour un devis en brouillon uniquement.

        Args:
            devis_id: ID du devis
            tenant_id: ID du tenant
            data: Champs à modifier

        Returns:
            Devis mis à jour

        Raises:
            HTTPException 400 si le devis n'est pas en statut 'draft'
        """
        devis = self._get_or_404(devis_id, tenant_id)
        if devis.status != DevisStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Seul un devis en statut 'draft' peut être modifié"
            )
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(devis, field, value)
        self.db.commit()
        self.db.refresh(devis)
        return self.repo.get_by_id_full(devis_id, tenant_id)

    def delete(self, devis_id: int, tenant_id: int) -> None:
        """Suppression logique d'un devis (soft delete).

        Seuls les devis en draft ou cancelled peuvent être supprimés.
        """
        devis = self._get_or_404(devis_id, tenant_id)
        if devis.status not in (DevisStatus.DRAFT, DevisStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Seuls les devis en statut 'draft' ou 'cancelled' peuvent être supprimés"
            )
        devis.soft_delete()
        self.db.commit()

    # ── Transitions d'état ───────────────────────────────────────────────────

    def send(self, devis_id: int, tenant_id: int, user_id: int) -> Devis:
        """Passe le devis de 'draft' à 'sent' et crée un snapshot v1."""
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.SENT)
        devis.status = DevisStatus.SENT
        self.repo.create_version_snapshot(devis, user_id)
        self.db.commit()
        logger.info("Devis %d envoyé (tenant=%d)", devis_id, tenant_id)
        return self.repo.get_by_id_full(devis_id, tenant_id)

    def accept(self, devis_id: int, tenant_id: int) -> Devis:
        """Accepte un devis."""
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.ACCEPTED)
        devis.status = DevisStatus.ACCEPTED
        self.db.commit()
        return self.repo.get_by_id_full(devis_id, tenant_id)

    def refuse(self, devis_id: int, tenant_id: int) -> Devis:
        """Refuse un devis."""
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.REFUSED)
        devis.status = DevisStatus.REFUSED
        self.db.commit()
        return self.repo.get_by_id_full(devis_id, tenant_id)

    def cancel(self, devis_id: int, tenant_id: int) -> Devis:
        """Annule un devis."""
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.CANCELLED)
        devis.status = DevisStatus.CANCELLED
        self.db.commit()
        return self.repo.get_by_id_full(devis_id, tenant_id)

    def expire(self, devis_id: int, tenant_id: int) -> Devis:
        """Marque un devis comme expiré."""
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.EXPIRED)
        devis.status = DevisStatus.EXPIRED
        self.db.commit()
        return self.repo.get_by_id_full(devis_id, tenant_id)

    def list_versions(self, devis_id: int, tenant_id: int) -> list:
        """Retourne les snapshots de versions du devis."""
        from sqlalchemy import select
        from app.models.devis import DevisVersion
        self._get_or_404(devis_id, tenant_id)
        result = self.db.execute(
            select(DevisVersion)
            .filter(DevisVersion.devis_id == devis_id, DevisVersion.tenant_id == tenant_id)
            .order_by(DevisVersion.version_number)
        ).scalars().all()
        return list(result)

    def renew(self, devis_id: int, tenant_id: int, new_valid_until: str) -> Devis:
        """Renouvelle un devis expiré en créant un nouveau brouillon.

        Args:
            devis_id: ID du devis expiré
            tenant_id: ID du tenant
            new_valid_until: Nouvelle date de validité (ISO date string)

        Returns:
            Nouveau devis en statut 'draft'
        """
        from datetime import date as date_type
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.DRAFT)

        reference = self.repo.generate_reference(tenant_id)
        new_valid_until_date = date_type.fromisoformat(new_valid_until)
        lines_data = [
            {
                "label": l.label,
                "product_id": l.product_id,
                "quantity": l.quantity,
                "unit_price_cents": l.unit_price_cents,
                "discount_pct": l.discount_pct,
                "sort_order": l.sort_order,
            }
            for l in devis.lines
        ]
        new_data = {
            "customer_id": devis.customer_id,
            "event_date": devis.event_date,
            "event_location": devis.event_location,
            "valid_until": new_valid_until_date,
            "tva_rate": devis.tva_rate,
            "discount_pct": devis.discount_pct,
            "caution_required": devis.caution_required,
            "caution_amount_cents": devis.caution_amount_cents,
            "notes": devis.notes,
        }
        new_devis = self.repo.create_with_lines(
            tenant_id, new_data, lines_data, reference
        )
        devis.status = DevisStatus.DRAFT  # ← transition expired→draft
        self.db.commit()
        logger.info("Devis %d renouvelé → %d (tenant=%d)", devis_id, new_devis.id, tenant_id)
        return self.repo.get_by_id_full(new_devis.id, tenant_id)

    def convert_to_reservation(
        self, devis_id: int, tenant_id: int, data: DevisConvert
    ) -> Devis:
        """Convertit un devis accepté en réservation.

        Args:
            devis_id: ID du devis
            tenant_id: ID du tenant
            data: Dates et lieu de l'événement

        Returns:
            Devis converti avec converted_reservation_id renseigné

        Raises:
            HTTPException 400 si le devis n'est pas 'accepted'
        """
        devis = self._get_or_404(devis_id, tenant_id)
        _assert_transition(devis, DevisStatus.CONVERTED)

        res_repo = ReservationRepository(self.db)
        year = datetime.now(tz=timezone.utc).year
        count = self.db.query(Reservation).filter(
            Reservation.tenant_id == tenant_id
        ).count()
        reference = f"RES-{year}-{count + 1:04d}"

        reservation = Reservation(
            tenant_id=tenant_id,
            customer_id=devis.customer_id,
            reference=reference,
            event_date=data.event_date,
            delivery_date=data.delivery_date,
            return_date=data.return_date,
            event_location=data.event_location,
            status=ReservationStatus.DRAFT,
            total_amount=devis.total_cents,
            deposit_amount=0,
        )
        self.db.add(reservation)
        self.db.flush()

        for line in devis.lines:
            res_line = ReservationLine(
                tenant_id=tenant_id,
                reservation_id=reservation.id,
                product_id=line.product_id,
                quantity=line.quantity,
                unit_price=line.unit_price_cents,
                subtotal=line.subtotal_cents,
            )
            self.db.add(res_line)

        devis.status = DevisStatus.CONVERTED
        devis.converted_reservation_id = reservation.id
        self.db.commit()
        logger.info(
            "Devis %d converti en réservation %d (tenant=%d)",
            devis_id, reservation.id, tenant_id
        )
        return self.repo.get_by_id_full(devis_id, tenant_id)

    # ── Modules ──────────────────────────────────────────────────────────────

    def add_module(
        self, devis_id: int, tenant_id: int, data: DevisModuleCreate
    ) -> DevisModule:
        devis = self._get_or_404(devis_id, tenant_id)
        module = DevisModule(
            tenant_id=tenant_id,
            devis_id=devis.id,
            **data.model_dump(),
        )
        self.db.add(module)
        self.db.commit()
        self.db.refresh(module)
        return module

    def update_module(
        self, devis_id: int, module_id: int, tenant_id: int, data: DevisModuleUpdate
    ) -> DevisModule:
        self._get_or_404(devis_id, tenant_id)
        module = self.db.query(DevisModule).filter(
            DevisModule.id == module_id,
            DevisModule.devis_id == devis_id,
            DevisModule.tenant_id == tenant_id,
        ).first()
        if not module:
            raise HTTPException(status_code=404, detail=f"Module {module_id} introuvable")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(module, field, value)
        self.db.commit()
        self.db.refresh(module)
        return module

    # ── Phases ───────────────────────────────────────────────────────────────

    def add_phase(
        self, devis_id: int, tenant_id: int, data: DevisPhaseCreate
    ) -> DevisPhase:
        devis = self._get_or_404(devis_id, tenant_id)
        phase = DevisPhase(
            tenant_id=tenant_id,
            devis_id=devis.id,
            **data.model_dump(),
        )
        self.db.add(phase)
        self.db.commit()
        self.db.refresh(phase)
        return phase

    def update_phase(
        self, devis_id: int, phase_id: int, tenant_id: int, data: DevisPhaseUpdate
    ) -> DevisPhase:
        self._get_or_404(devis_id, tenant_id)
        phase = self.db.query(DevisPhase).filter(
            DevisPhase.id == phase_id,
            DevisPhase.devis_id == devis_id,
            DevisPhase.tenant_id == tenant_id,
        ).first()
        if not phase:
            raise HTTPException(status_code=404, detail=f"Phase {phase_id} introuvable")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(phase, field, value)
        self.db.commit()
        self.db.refresh(phase)
        return phase

    # ── Négociations ──────────────────────────────────────────────────────────

    def add_negotiation(
        self, devis_id: int, tenant_id: int, user_id: int, data: DevisNegotiationCreate
    ) -> DevisNegotiation:
        devis = self._get_or_404(devis_id, tenant_id)
        if devis.status != DevisStatus.NEGOTIATION:
            raise HTTPException(
                status_code=400,
                detail="Négociation uniquement possible sur un devis en statut 'negotiation'"
            )
        neg = DevisNegotiation(
            tenant_id=tenant_id,
            devis_id=devis.id,
            author_id=user_id,
            message=data.message,
            proposed_amount_cents=data.proposed_amount_cents,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(neg)
        self.db.commit()
        self.db.refresh(neg)
        return neg

    # ── Change requests ───────────────────────────────────────────────────────

    def add_change_request(
        self, devis_id: int, tenant_id: int, user_id: int, data: DevisChangeRequestCreate
    ) -> DevisChangeRequest:
        devis = self._get_or_404(devis_id, tenant_id)
        cr = DevisChangeRequest(
            tenant_id=tenant_id,
            devis_id=devis.id,
            author_id=user_id,
            description=data.description,
        )
        self.db.add(cr)
        self.db.commit()
        self.db.refresh(cr)
        return cr

    def update_change_request(
        self,
        devis_id: int,
        cr_id: int,
        tenant_id: int,
        data: DevisChangeRequestUpdate,
    ) -> DevisChangeRequest:
        self._get_or_404(devis_id, tenant_id)
        cr = self.db.query(DevisChangeRequest).filter(
            DevisChangeRequest.id == cr_id,
            DevisChangeRequest.devis_id == devis_id,
            DevisChangeRequest.tenant_id == tenant_id,
        ).first()
        if not cr:
            raise HTTPException(status_code=404, detail=f"Change request {cr_id} introuvable")
        cr.status = data.status
        self.db.commit()
        self.db.refresh(cr)
        return cr

    # ── Duplication ───────────────────────────────────────────────────────────

    def duplicate(self, devis_id: int, tenant_id: int) -> Devis:
        """Duplique un devis existant en brouillon avec une nouvelle référence.

        Args:
            devis_id: ID du devis source
            tenant_id: ID du tenant

        Returns:
            Nouveau Devis DRAFT avec les mêmes lignes que l'original
        """
        original = self._get_or_404(devis_id, tenant_id)
        new_reference = self.repo.generate_reference(tenant_id)
        now = datetime.now(tz=timezone.utc)

        new_devis = Devis(
            tenant_id=tenant_id,
            reference=new_reference,
            customer_id=original.customer_id,
            status=DevisStatus.DRAFT,
            event_date=original.event_date,
            event_location=original.event_location,
            valid_until=original.valid_until,
            tva_rate=original.tva_rate,
            subtotal_cents=original.subtotal_cents,
            tva_cents=original.tva_cents,
            total_cents=original.total_cents,
            discount_pct=original.discount_pct,
            caution_required=original.caution_required,
            caution_amount_cents=original.caution_amount_cents,
            notes=original.notes,
            created_at=now,
            updated_at=now,
        )
        self.db.add(new_devis)
        self.db.flush()

        for line in original.lines:
            new_line = DevisLine(
                tenant_id=tenant_id,
                devis_id=new_devis.id,
                product_id=line.product_id,
                label=line.label,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
                discount_pct=line.discount_pct,
                subtotal_cents=line.subtotal_cents,
                sort_order=line.sort_order,
            )
            self.db.add(new_line)

        self.db.commit()
        logger.info(
            "Devis %d dupliqué → %d (ref=%s, tenant=%d)",
            devis_id, new_devis.id, new_reference, tenant_id,
        )
        return self.repo.get_by_id_full(new_devis.id, tenant_id)
