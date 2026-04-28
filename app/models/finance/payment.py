"""Modèle FinancePayment — Paiements de factures.

Chaque enregistrement représente un paiement (ou partiel) d'une FinanceInvoice.
Une facture peut avoir plusieurs paiements (règlement partiel).

Modes de paiement : ESPECES | CB | CHEQUE | VIREMENT | MIXTE
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

MODES_PAIEMENT = ('ESPECES', 'CB', 'CHEQUE', 'VIREMENT', 'MIXTE')


class FinancePayment(Base, TenantMixin, TimestampMixin):
    """Paiement d'une facture finance."""

    __tablename__ = "finance_payments"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la facture réglée"
    )
    montant_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Montant du paiement en centimes"
    )
    mode_paiement: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Mode : ESPECES | CB | CHEQUE | VIREMENT | MIXTE"
    )
    date_paiement: Mapped[object] = mapped_column(
        Date, nullable=False,
        comment="Date effective du paiement"
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Référence de paiement (numéro chèque, transaction CB, etc.)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre"
    )
    # tenant_id hérite de TenantMixin
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"mode_paiement IN {MODES_PAIEMENT}",
            name="check_finance_payment_mode_valide"
        ),
        CheckConstraint(
            "montant_cts > 0",
            name="check_finance_payment_montant_positif"
        ),
        Index("idx_finance_payment_tenant", "tenant_id"),
        Index("idx_finance_payment_invoice", "invoice_id"),
        Index("idx_finance_payment_date", "date_paiement"),
        Index("idx_finance_payment_tenant_invoice", "tenant_id", "invoice_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancePayment id={self.id} invoice_id={self.invoice_id} "
            f"montant_cts={self.montant_cts} mode={self.mode_paiement!r}>"
        )
