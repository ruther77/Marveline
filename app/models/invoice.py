"""Modèle Invoice - Facturation des réservations."""
from datetime import date
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin


class Invoice(Base, TimestampMixin, TenantMixin):
    """Facture générée pour une réservation.

    Attributes:
        reservation_id: ID de la réservation (FK unique - one-to-one)
        invoice_number: Numéro de facture unique (ex: "INV-2026-0001")
        issue_date: Date d'émission
        due_date: Date d'échéance (≥ issue_date)
        total_amount: Montant total en CENTIMES
        paid_amount: Montant payé en CENTIMES (≤ total_amount)
        status: Statut (draft, sent, paid, overdue, cancelled)
        payment_method: Moyen de paiement (cash, card, transfer, check)
        payment_date: Date de paiement (nullable)
    """

    __tablename__ = "invoices"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Réservation (relation one-to-one)
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="ID de la réservation (one-to-one)"
    )

    # Numéro de facture
    invoice_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Numéro de facture unique (INV-2026-0001)"
    )

    # Dates
    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date d'émission de la facture"
    )

    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date d'échéance de paiement"
    )

    # Montants (en centimes)
    total_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Montant total en centimes"
    )

    paid_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant payé en centimes"
    )

    # Statut
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        comment="Statut de la facture"
    )

    # Paiement
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Moyen de paiement (cash, card, transfer, check)"
    )

    payment_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date de paiement"
    )

    # Relations
    reservation: Mapped["Reservation"] = relationship(
        "Reservation",
        back_populates="invoice"
    )

    # Contraintes
    __table_args__ = (
        # Numéro de facture unique par tenant
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoice_tenant_number"),
        # Dates cohérentes
        CheckConstraint(
            "due_date >= issue_date",
            name="check_invoice_due_after_issue"
        ),
        # Montant payé ≤ total
        CheckConstraint(
            "paid_amount <= total_amount",
            name="check_invoice_paid_lte_total"
        ),
        # Statut valide
        CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'overdue', 'cancelled')",
            name="check_invoice_status_valid"
        ),
        # Méthode paiement valide
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN ('cash', 'card', 'transfer', 'check')",
            name="check_invoice_payment_method_valid"
        ),
    )

    @property
    def is_paid(self) -> bool:
        """Facture entièrement payée."""
        return self.paid_amount >= self.total_amount

    @property
    def remaining_amount(self) -> int:
        """Montant restant à payer en centimes."""
        return max(0, self.total_amount - self.paid_amount)

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', status='{self.status}')>"
