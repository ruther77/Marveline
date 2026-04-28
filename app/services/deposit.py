"""Service Deposit — logique métier cautions de réservations."""
import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import func as sa_func

from app.constants import DepositStatus
from app.models.deposit import Deposit
from app.models.reservation import Reservation
from app.repositories.deposit import AsyncDepositRepository
from app.schemas.deposit import DepositCreate, DepositUpdate, DepositWithReservation, DepositSummary

logger = logging.getLogger(__name__)


class DepositService:
    """Service pour la gestion des cautions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncDepositRepository(db)

    async def list_all_deposits(
        self,
        tenant_id: int,
        *,
        deposit_status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[DepositWithReservation], int]:
        """Liste toutes les cautions du tenant avec infos reservation."""
        from app.models.customer import Customer

        query = (
            select(Deposit, Reservation, Customer)
            .join(Reservation, Deposit.reservation_id == Reservation.id)
            .outerjoin(Customer, Reservation.customer_id == Customer.id)
            .where(Deposit.tenant_id == tenant_id)
        )
        if deposit_status:
            query = query.where(Deposit.status == deposit_status)
        if date_from:
            query = query.where(Deposit.created_at >= date_from)
        if date_to:
            query = query.where(Deposit.created_at <= date_to)

        count_query = (
            select(sa_func.count())
            .select_from(Deposit)
            .where(Deposit.tenant_id == tenant_id)
        )
        if deposit_status:
            count_query = count_query.where(Deposit.status == deposit_status)
        if date_from:
            count_query = count_query.where(Deposit.created_at >= date_from)
        if date_to:
            count_query = count_query.where(Deposit.created_at <= date_to)

        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                query.order_by(Deposit.created_at.desc()).offset(skip).limit(limit)
            )
        ).all()

        result = []
        for dep, resa, customer in rows:
            name = None
            if customer:
                first = getattr(customer, "first_name", "") or ""
                last = getattr(customer, "last_name", "") or ""
                name = f"{first} {last}".strip() or None
            result.append(DepositWithReservation(
                id=dep.id,
                tenant_id=dep.tenant_id,
                reservation_id=dep.reservation_id,
                amount_cents=dep.amount_cents,
                status=dep.status,
                retained_amount_cents=dep.retained_amount_cents,
                collection_date=dep.collection_date,
                release_date=dep.release_date,
                notes=dep.notes,
                created_at=dep.created_at,
                updated_at=dep.updated_at,
                reservation_reference=resa.reference if resa else f"#{dep.reservation_id}",
                customer_name=name,
                event_date=resa.event_date if resa else None,
            ))
        return result, total

    async def get_summary(self, tenant_id: int) -> DepositSummary:
        """KPI agrégés des cautions du tenant."""
        data = await self.repo.summary(tenant_id)
        return DepositSummary(**data)

    async def has_held_deposit(self, reservation_id: int, tenant_id: int) -> bool:
        """Verifie si au moins une caution est encaissee (held) pour cette reservation."""
        deposits = await self.repo.list_by_reservation(reservation_id, tenant_id)
        return any(d.status == DepositStatus.HELD for d in deposits)

    async def list_deposits(self, reservation_id: int, tenant_id: int) -> list[Deposit]:
        """Liste les cautions d'une réservation."""
        await self._get_reservation_or_404(reservation_id, tenant_id)
        return await self.repo.list_by_reservation(reservation_id, tenant_id)

    async def create_deposit(
        self, reservation_id: int, data: DepositCreate, tenant_id: int
    ) -> Deposit:
        """Crée une caution pour une réservation.

        Raises:
            HTTPException 404: Si réservation non trouvée.
        """
        reservation = await self._get_reservation_or_404(reservation_id, tenant_id)

        deposit = Deposit(
            tenant_id=tenant_id,
            reservation_id=reservation_id,
            amount_cents=data.amount_cents,
            status=DepositStatus.HELD,
            collection_date=data.collection_date,
            notes=data.notes,
        )
        self.db.add(deposit)

        # Marquer la caution comme reçue (deposit_amount_cents conserve le montant CGV calculé)
        reservation.deposit_paid = True

        return deposit

    async def get_deposit(
        self, reservation_id: int, deposit_id: int, tenant_id: int
    ) -> Deposit:
        """Récupère une caution d'une réservation.

        Raises:
            HTTPException 404: Si réservation ou caution non trouvée.
        """
        await self._get_reservation_or_404(reservation_id, tenant_id)

        deposit = await self.repo.get_by_id(deposit_id, tenant_id)
        if not deposit or deposit.reservation_id != reservation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Deposit {deposit_id} not found for reservation {reservation_id}",
            )
        return deposit

    async def update_deposit(
        self, reservation_id: int, deposit_id: int, data: DepositUpdate, tenant_id: int
    ) -> Deposit:
        """Met à jour le statut d'une caution.

        Raises:
            HTTPException 404: Si réservation ou caution non trouvée.
        """
        await self._get_reservation_or_404(reservation_id, tenant_id)

        deposit = (await self.db.execute(
            select(Deposit).filter(
                Deposit.id == deposit_id,
                Deposit.reservation_id == reservation_id,
                Deposit.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()

        if not deposit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Deposit {deposit_id} not found for reservation {reservation_id}",
            )

        # Bloquer le release si des dommages factures existent
        if data.status == DepositStatus.RELEASED:
            damage_total = await self.compute_damage_total(reservation_id, tenant_id)
            if damage_total > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Impossible de restituer la caution : {damage_total} centimes "
                        f"de dommages factures. Utilisez le statut 'retained' avec "
                        f"retained_amount_cents >= {damage_total}."
                    ),
                )

        # Valider retained_amount_cents <= amount_cents
        if data.status == DepositStatus.RETAINED and data.retained_amount_cents is not None:
            if data.retained_amount_cents > deposit.amount_cents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Montant retenu ({data.retained_amount_cents}) depasse "
                        f"la caution ({deposit.amount_cents})."
                    ),
                )

        deposit.status = data.status
        if data.release_date is not None:
            deposit.release_date = data.release_date
        if data.retained_amount_cents is not None:
            deposit.retained_amount_cents = data.retained_amount_cents
        if data.notes is not None:
            deposit.notes = data.notes

        # Sync reservation.deposit_paid avec l'etat reel des deposits
        reservation = await self._get_reservation_or_404(reservation_id, tenant_id)
        if data.status in (DepositStatus.RELEASED, DepositStatus.RETAINED):
            remaining_held = await self.has_held_deposit(reservation_id, tenant_id)
            if not remaining_held:
                reservation.deposit_paid = False
        elif data.status == DepositStatus.HELD:
            reservation.deposit_paid = True

        return deposit

    async def compute_damage_total(
        self, reservation_id: int, tenant_id: int
    ) -> int:
        """Calcule la somme des charges DAMAGE sur les factures de la reservation."""
        from app.models.invoice import Invoice
        from app.models.invoice_charge import InvoiceCharge

        result = await self.db.execute(
            select(sa_func.coalesce(sa_func.sum(InvoiceCharge.amount_cents), 0))
            .join(Invoice, InvoiceCharge.invoice_id == Invoice.id)
            .where(
                Invoice.reservation_id == reservation_id,
                Invoice.tenant_id == tenant_id,
                InvoiceCharge.charge_type == "DAMAGE",
                InvoiceCharge.tenant_id == tenant_id,
            )
        )
        return int(result.scalar_one())

    async def auto_retain_from_damages(
        self, reservation_id: int, tenant_id: int
    ) -> Deposit | None:
        """Auto-met a jour le deposit si des dommages sont declares.

        Appele apres chaque declaration de dommage. Si un deposit est held,
        met a jour retained_amount_cents = sum(damage charges).
        """
        deposits = await self.repo.list_by_reservation(reservation_id, tenant_id)
        held_deposit = next((d for d in deposits if d.status == DepositStatus.HELD), None)
        if not held_deposit:
            return None

        damage_total = await self.compute_damage_total(reservation_id, tenant_id)
        if damage_total <= 0:
            return None

        retained = min(damage_total, held_deposit.amount_cents)
        held_deposit.retained_amount_cents = retained
        held_deposit.status = DepositStatus.RETAINED
        logger.info(
            "Auto-retained %d cents on deposit %d (reservation %d, damages=%d)",
            retained, held_deposit.id, reservation_id, damage_total,
        )
        return held_deposit

    async def _get_reservation_or_404(self, reservation_id: int, tenant_id: int) -> Reservation:
        """Récupère la réservation ou lève 404."""
        result = (await self.db.execute(
            select(Reservation).filter(
                Reservation.id == reservation_id,
                Reservation.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation {reservation_id} not found",
            )
        return result
