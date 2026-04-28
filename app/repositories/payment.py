"""Repository pour Payment."""
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Repository paiements avec isolation multi-tenant."""

    def __init__(self, db: Session):
        super().__init__(db, Payment)

    def list_by_invoice(self, invoice_id: int, tenant_id: int) -> list[Payment]:
        """Liste les paiements d'une facture, triés par date."""
        query = (
            select(Payment)
            .filter(
                Payment.invoice_id == invoice_id,
                Payment.tenant_id == tenant_id,
            )
            .order_by(Payment.payment_date, Payment.id)
        )
        return list(self.db.execute(query).scalars().all())

    def sum_by_invoice(self, invoice_id: int, tenant_id: int) -> int:
        """Somme totale des paiements d'une facture en centimes."""
        result = self.db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).filter(
                Payment.invoice_id == invoice_id,
                Payment.tenant_id == tenant_id,
            )
        ).scalar()
        return int(result)


class AsyncPaymentRepository:
    """Version async de PaymentRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def list_by_invoice(self, invoice_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.payment import Payment
        result = await self.db.execute(
            select(Payment)
            .filter(Payment.invoice_id == invoice_id, Payment.tenant_id == tenant_id)
            .order_by(Payment.payment_date, Payment.id)
        )
        return list(result.scalars().all())

    async def sum_by_invoice(self, invoice_id: int, tenant_id: int) -> int:
        from sqlalchemy import select, func
        from app.models.payment import Payment
        result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0))
            .filter(Payment.invoice_id == invoice_id, Payment.tenant_id == tenant_id)
        )
        return int(result.scalar())

    async def get_by_id(self, payment_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.payment import Payment
        result = await self.db.execute(
            select(Payment).filter(Payment.id == payment_id, Payment.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict):
        from app.models.payment import Payment
        obj = Payment(**data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
