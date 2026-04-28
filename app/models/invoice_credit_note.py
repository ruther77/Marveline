"""Modèle InvoiceCreditNote — avoirs sur factures."""
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    BigInteger, CheckConstraint, Date, ForeignKey,
    Index, Integer, String, Text, TIMESTAMP, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TenantMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class InvoiceCreditNote(Base, TenantMixin):
    """Avoir associé à une facture originale.

    Attributes:
        original_invoice_id: FK vers la facture d'origine
        invoice_number: Numéro de l'avoir (AVOIR-YYYY-NNNN)
        amount_cents: Montant de l'avoir en centimes (≤ montant facture)
        reason: Motif de l'avoir
        status: Statut (draft|issued|applied)
    """

    __tablename__ = "invoice_credit_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    original_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    invoice_number: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Référence AVOIR-YYYY-NNNN"
    )

    amount_cents: Mapped[int] = mapped_column(
        BigInteger(), nullable=False, comment="Montant en centimes"
    )

    reason: Mapped[str] = mapped_column(Text(), nullable=False)

    issue_date: Mapped[date] = mapped_column(Date(), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )

    # Relation
    invoice: Mapped["Invoice"] = relationship(
        "Invoice", foreign_keys=[original_invoice_id]
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_credit_note_tenant_number"),
        CheckConstraint(
            "status IN ('draft','issued','applied','refunded')",
            name="check_credit_note_status_valid"
        ),
        CheckConstraint("amount_cents > 0", name="check_credit_note_amount_positive"),
        Index("ix_credit_notes_tenant_composite", "tenant_id", "id"),
        Index("ix_credit_notes_tenant_invoice", "tenant_id", "original_invoice_id"),
    )

    def __repr__(self) -> str:
        return f"<InvoiceCreditNote(id={self.id}, num='{self.invoice_number}', status='{self.status}')>"
