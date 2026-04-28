"""Service orchestrateur pour workflows Réservation + Inventory.

Résout la dépendance circulaire reservation.py ↔ inventory_movement.py
en centralisant les opérations cross-domain.
"""
import logging
from datetime import date, datetime, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ErrorMessages, MovementType, ReservationStatus
from app.models.inventory_movement import InventoryMovement
from app.models.invoice import Invoice
from app.models.reservation import Reservation

logger = logging.getLogger(__name__)


async def assert_delivery_guards(
    db: AsyncSession,
    reservation: Reservation,
    tenant_id: int,
) -> None:
    """Bloque la livraison si les guards business ne sont pas verts.

    Vérifie selon settings tenant :
        - block_delivery_without_advance : acompte payé (default true)
        - require_signature_before_delivery : contrat signé (default true)

    Raises HTTPException 422 avec message clair pour l'UI.

    Why: défaut de design détecté 2026-04-26 — un opérateur pouvait livrer
    sans acompte ni signature. Les pertes business potentielles (matériel
    non récupéré, contestation contractuelle) justifient ces guards par
    défaut, désactivables par tenant pour les modèles B2B.
    """
    from app.models.tenant_settings import TenantSettings

    settings_q = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    settings = settings_q.scalar_one_or_none()

    block_advance = (
        settings.block_delivery_without_advance if settings is not None else True
    )
    require_sig = (
        settings.require_signature_before_delivery if settings is not None else True
    )

    if block_advance:
        await _assert_advance_paid(db, reservation, tenant_id)

    if require_sig and not reservation.signature_url:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorMessages.RESERVATION_SIGNATURE_REQUIRED,
        )


async def _assert_advance_paid(
    db: AsyncSession,
    reservation: Reservation,
    tenant_id: int,
) -> None:
    """Vérifie que l'acompte attendu sur la résa est encaissé sur sa facture.

    Logique : la résa porte ``advance_payment_amount_cents`` (calculé à la
    confirmation depuis tenant_settings.advance_rate). On compare au
    ``paid_amount_cents`` de la facture active liée à la résa.
    """
    advance_required = reservation.advance_payment_amount_cents or 0
    if advance_required <= 0:
        return  # pas d'acompte attendu

    # Facture active la plus récente liée à la résa
    invoice_q = await db.execute(
        select(Invoice)
        .where(
            Invoice.reservation_id == reservation.id,
            Invoice.tenant_id == tenant_id,
            Invoice.status != "cancelled",
        )
        .order_by(Invoice.id.desc())
        .limit(1)
    )
    invoice = invoice_q.scalar_one_or_none()
    paid = (invoice.paid_amount_cents if invoice is not None else 0) or 0

    if paid < advance_required:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorMessages.RESERVATION_ADVANCE_NOT_PAID,
        )


class ReservationWorkflowService:
    """Orchestre les workflows entre Réservations et Mouvements d'inventaire."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def auto_generate_departure_movement(
        self,
        reservation: Reservation,
        tenant_id: int,
    ) -> None:
        """Auto-crée un mouvement DEPARTURE lors de la confirmation d'une réservation.

        Idempotent : si un mouvement DEPARTURE existe déjà pour cette réservation,
        l'opération est ignorée silencieusement (log warning).

        Args:
            reservation: Réservation confirmée (avec lines chargées)
            tenant_id: ID du tenant
        """
        from app.services.inventory_movement import AsyncMovementService

        movement_service = AsyncMovementService(self.db)

        # Idempotence : vérifier qu'aucun DEPARTURE n'existe déjà
        existing, count = await movement_service.list_movements(
            tenant_id=tenant_id,
            reservation_id=reservation.id,
            movement_type=MovementType.DEPARTURE.value,
        )
        if count > 0:
            logger.warning(
                "Departure movement already exists for reservation %s",
                reservation.reference,
            )
            return

        # Construire les items depuis les lignes de réservation
        # Les bundles sont éclatés en produits individuels
        items = []
        for line in reservation.lines:
            if line.bundle_id and hasattr(line, "bundle") and line.bundle:
                bundle_items = getattr(line.bundle, "items", None) or []
                for bi in bundle_items:
                    items.append({
                        "product_id": bi.product_id,
                        "variant_id": bi.variant_id,
                        "quantity_expected": bi.quantity * line.quantity,
                        "event_item_id": line.id,
                    })
            elif line.product_id:
                items.append({
                    "product_id": line.product_id,
                    "variant_id": line.variant_id,
                    "quantity_expected": line.quantity,
                    "event_item_id": line.id,
                })

        scheduled_dt = datetime.combine(
            reservation.delivery_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        await movement_service.create_movement(
            tenant_id=tenant_id,
            movement_type=MovementType.DEPARTURE.value,
            scheduled_date=scheduled_dt,
            items=items,
            reservation_id=reservation.id,
            delivery_address=reservation.event_location,
            skip_stock_check=True,  # stock déjà réservé via reserve_n() lors de la confirmation
        )
        logger.info(
            "Auto-generated departure movement for reservation %s (tenant=%d)",
            reservation.reference,
            tenant_id,
        )

    async def update_reservation_on_movement_complete(
        self,
        movement: InventoryMovement,
    ) -> None:
        """Met à jour le statut réservation quand un mouvement lié est complété.

        Args:
            movement: Mouvement complété (avec reservation_id)
        """
        if not movement.reservation_id:
            return

        result = await self.db.execute(
            select(Reservation).where(
                Reservation.id == movement.reservation_id,
                Reservation.tenant_id == movement.tenant_id,
            )
        )
        reservation = result.scalars().first()
        if not reservation:
            logger.warning(
                "Reservation %d not found for movement %d",
                movement.reservation_id,
                movement.id,
            )
            return

        # Note: la transition DEPARTURE → DELIVERED est gérée par Operations
        # (validate_departure). Seul le RETURN est géré ici en fallback.
        if movement.movement_type == MovementType.RETURN.value:
            if reservation.status == ReservationStatus.DELIVERED:
                reservation.status = ReservationStatus.RETURNED
                await self.db.flush()
                logger.info(
                    "Reservation %s -> returned (return movement %d completed)",
                    reservation.reference,
                    movement.id,
                )

    async def detect_risks(
        self,
        reservation_id: int,
        tenant_id: int,
    ) -> list[dict]:
        """Detecte automatiquement les risques sur une reservation.

        Risques verifies :
        - deposit_missing : caution non encaissee + event_date < 7 jours
        - overdue_invoice : facture en retard
        """
        from app.services.deposit import DepositService
        from app.models.invoice import Invoice

        result = await self.db.execute(
            select(Reservation).where(
                Reservation.id == reservation_id,
                Reservation.tenant_id == tenant_id,
            )
        )
        reservation = result.scalars().first()
        if not reservation:
            return []

        risks: list[dict] = []

        deposit_service = DepositService(self.db)
        has_deposit = await deposit_service.has_held_deposit(reservation_id, tenant_id)
        if not has_deposit:
            days_until = (reservation.event_date - date.today()).days
            if days_until <= 7:
                risks.append({
                    "type": "deposit_missing",
                    "severity": "high",
                    "blocking": True,
                    "description": f"Caution non encaissee a J-{days_until}",
                })

        overdue_result = await self.db.execute(
            select(Invoice).where(
                Invoice.reservation_id == reservation_id,
                Invoice.tenant_id == tenant_id,
                Invoice.status == "overdue",
            )
        )
        if overdue_result.scalars().first():
            risks.append({
                "type": "overdue_invoice",
                "severity": "medium",
                "blocking": False,
                "description": "Facture en retard de paiement",
            })

        return risks


# Backward compat alias
AsyncReservationWorkflowService = ReservationWorkflowService
