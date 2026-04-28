"""Modèle Payment — Paiements associés aux factures."""
from datetime import date
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin


class Payment(Base, TimestampMixin, TenantMixin):
    """Paiement associé à une facture.

    Attributes:
        invoice_id: FK vers la facture
        amount_cents: Montant en centimes (> 0)
        payment_method: Méthode de paiement (cash/card/transfer/check)
        payment_date: Date du paiement
        notes: Notes optionnelles
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la facture parente"
    )

    amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Montant du paiement en centimes (> 0)"
    )

    payment_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Méthode : cash, card, transfer, check"
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date du paiement"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Notes libres"
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="check_payment_amount_positive"),
        CheckConstraint(
            "payment_method IN ('cash', 'card', 'transfer', 'check')",
            name="check_payment_method_valid"
        ),
        Index("ix_payments_tenant_invoice", "tenant_id", "invoice_id"),
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, invoice={self.invoice_id}, amount={self.amount_cents})>"
