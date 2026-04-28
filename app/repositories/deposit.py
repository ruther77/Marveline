"""Repository pour Deposit."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deposit import Deposit
from app.repositories.base import BaseRepository


class DepositRepository(BaseRepository[Deposit]):
    """Repository cautions avec isolation multi-tenant."""

    def __init__(self, db: Session):
        super().__init__(db, Deposit)

    def list_by_reservation(self, reservation_id: int, tenant_id: int) -> list[Deposit]:
        """Liste les cautions d'une réservation, triées par date de création."""
        query = (
            select(Deposit)
            .filter(
                Deposit.reservation_id == reservation_id,
                Deposit.tenant_id == tenant_id,
            )
            .order_by(Deposit.id)
        )
        return list(self.db.execute(query).scalars().all())


class AsyncDepositRepository:
    """Version async de DepositRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def list_by_reservation(self, reservation_id: int, tenant_id: int) -> list[Deposit]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Deposit).filter(
                Deposit.reservation_id == reservation_id, Deposit.tenant_id == tenant_id
            ).order_by(Deposit.id)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        tenant_id: int,
        *,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Deposit], int]:
        """Liste toutes les cautions du tenant avec filtres et pagination.

        Returns:
            Tuple (deposits, total_count).
        """
        from sqlalchemy import select, func
        from app.models.reservation import Reservation

        base = select(Deposit).filter(Deposit.tenant_id == tenant_id)

        if status:
            base = base.filter(Deposit.status == status)
        if date_from:
            base = base.filter(Deposit.created_at >= date_from)
        if date_to:
            from datetime import datetime, time
            end = datetime.combine(date_to, time.max)
            base = base.filter(Deposit.created_at <= end)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.db.scalar(count_q)) or 0

        rows_q = (
            base
            .join(Reservation, Deposit.reservation_id == Reservation.id)
            .order_by(Deposit.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(rows_q)
        return list(result.scalars().all()), total

    async def summary(self, tenant_id: int) -> dict:
        """KPI agrégés par statut pour le tenant."""
        from sqlalchemy import select, func, case
        q = (
            select(
                Deposit.status,
                func.count(Deposit.id).label("cnt"),
                func.coalesce(
                    func.sum(
                        case(
                            (Deposit.status == "retained", Deposit.retained_amount_cents),
                            else_=Deposit.amount_cents,
                        )
                    ),
                    0,
                ).label("total_cents"),
            )
            .filter(Deposit.tenant_id == tenant_id)
            .group_by(Deposit.status)
        )
        rows = (await self.db.execute(q)).all()
        out = {
            "count_held": 0, "count_retained": 0, "count_released": 0,
            "total_held_cents": 0, "total_retained_cents": 0, "total_released_cents": 0,
        }
        for row in rows:
            out[f"count_{row.status}"] = int(row.cnt)
            out[f"total_{row.status}_cents"] = int(row.total_cents)
        return out

    async def get_by_id(self, deposit_id: int, tenant_id: int) -> "Deposit | None":
        from sqlalchemy import select
        result = await self.db.execute(
            select(Deposit).filter(Deposit.id == deposit_id, Deposit.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Deposit:
        obj = Deposit(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: Deposit, data: dict) -> Deposit:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
