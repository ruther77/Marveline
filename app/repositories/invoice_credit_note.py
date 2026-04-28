"""Repository pour InvoiceCreditNote."""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.invoice_credit_note import InvoiceCreditNote
from app.repositories.base import BaseRepository


class CreditNoteRepository(BaseRepository[InvoiceCreditNote]):
    """Repository avec isolation tenant stricte."""

    def __init__(self, db: Session):
        super().__init__(db, InvoiceCreditNote)

    def get_by_invoice(self, invoice_id: int, tenant_id: int) -> list[InvoiceCreditNote]:
        """Retourne les avoirs d'une facture."""
        return list(
            self.db.execute(
                select(InvoiceCreditNote)
                .filter(
                    InvoiceCreditNote.original_invoice_id == invoice_id,
                    InvoiceCreditNote.tenant_id == tenant_id,
                )
                .order_by(InvoiceCreditNote.created_at.desc())
            ).scalars().all()
        )

    def total_credited(self, invoice_id: int, tenant_id: int) -> int:
        """Somme des avoirs non-annulés pour une facture (en centimes)."""
        result = self.db.execute(
            select(func.sum(InvoiceCreditNote.amount_cents))
            .filter(
                InvoiceCreditNote.original_invoice_id == invoice_id,
                InvoiceCreditNote.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        return result or 0

    def generate_number(self, tenant_id: int) -> str:
        """Génère un numéro unique AVOIR-YYYY-NNNN (MAX + 1)."""
        year = datetime.now().year
        prefix = f"AVOIR-{year}-"
        last = self.db.execute(
            select(func.max(InvoiceCreditNote.invoice_number)).filter(
                InvoiceCreditNote.tenant_id == tenant_id,
                InvoiceCreditNote.invoice_number.like(f"{prefix}%"),
            )
        ).scalar()
        last_counter = 0
        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                pass
        return f"{prefix}{last_counter + 1:04d}"

    def create(
        self,
        tenant_id: int,
        invoice_id: int,
        amount_cents: int,
        reason: str,
        issue_date: date,
    ) -> InvoiceCreditNote:
        """Crée un avoir."""
        number = self.generate_number(tenant_id)
        cn = InvoiceCreditNote(
            tenant_id=tenant_id,
            original_invoice_id=invoice_id,
            invoice_number=number,
            amount_cents=amount_cents,
            reason=reason,
            issue_date=issue_date,
            status="draft",
        )
        self.db.add(cn)
        self.db.flush()
        return cn


class AsyncCreditNoteRepository:
    """Version async de CreditNoteRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, cn_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.invoice_credit_note import InvoiceCreditNote
        result = await self.db.execute(
            select(InvoiceCreditNote).filter(
                InvoiceCreditNote.id == cn_id,
                InvoiceCreditNote.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_invoice(self, invoice_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.invoice_credit_note import InvoiceCreditNote
        result = await self.db.execute(
            select(InvoiceCreditNote)
            .filter(
                InvoiceCreditNote.original_invoice_id == invoice_id,
                InvoiceCreditNote.tenant_id == tenant_id,
            )
            .order_by(InvoiceCreditNote.created_at.desc())
        )
        return list(result.scalars().all())

    async def total_credited(self, invoice_id: int, tenant_id: int) -> int:
        from sqlalchemy import select, func
        from app.models.invoice_credit_note import InvoiceCreditNote
        result = await self.db.execute(
            select(func.sum(InvoiceCreditNote.amount_cents)).filter(
                InvoiceCreditNote.original_invoice_id == invoice_id,
                InvoiceCreditNote.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none() or 0

    async def generate_number(self, tenant_id: int) -> str:
        from datetime import datetime
        from sqlalchemy import select, func
        from app.models.invoice_credit_note import InvoiceCreditNote
        year = datetime.now().year
        prefix = f"AVOIR-{year}-"
        last = await self.db.scalar(
            select(func.max(InvoiceCreditNote.invoice_number)).filter(
                InvoiceCreditNote.tenant_id == tenant_id,
                InvoiceCreditNote.invoice_number.like(f"{prefix}%"),
            )
        )
        last_counter = 0
        if last:
            try:
                last_counter = int(last.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                pass
        return f"{prefix}{last_counter + 1:04d}"

    async def update_status(self, cn_id: int, tenant_id: int, new_status: str) -> object:
        cn = await self.get_by_id(cn_id, tenant_id)
        if cn is None:
            return None
        cn.status = new_status
        await self.db.flush()
        await self.db.refresh(cn)
        return cn

    async def create(self, tenant_id: int, invoice_id: int, amount_cents: int, reason: str, issue_date) -> object:
        from app.models.invoice_credit_note import InvoiceCreditNote
        number = await self.generate_number(tenant_id)
        cn = InvoiceCreditNote(
            tenant_id=tenant_id,
            original_invoice_id=invoice_id,
            invoice_number=number,
            amount_cents=amount_cents,
            reason=reason,
            issue_date=issue_date,
            status="draft",
        )
        self.db.add(cn)
        await self.db.flush()
        await self.db.refresh(cn)
        return cn
