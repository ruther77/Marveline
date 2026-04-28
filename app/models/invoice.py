"""Modèle Invoice - Facturation des réservations."""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin
from app.constants import InvoiceStatus


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

    # Réservation (relation one-to-many : 1 réservation → N factures selon split)
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID de la réservation (peut avoir 2 factures : advance + balance)"
    )

    # Type de facture (split 40/60)
    invoice_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="full",
        comment="Type : full (100%), advance (40%), balance (60%)"
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
    total_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Montant total en centimes"
    )

    paid_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant payé en centimes"
    )

    # Statut
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InvoiceStatus.DRAFT,
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

    # TVA (Option A — taux capturé à la création)
    tva_rate: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Taux TVA appliqué (ex: 0.20 = 20%) — capturé à la création"
    )

    # Taux d'acompte CGV — capture par facture (peut différer de tenant_settings)
    advance_rate: Mapped[float] = mapped_column(
        nullable=False,
        default=0.40,
        comment="Taux d'acompte CGV appliqué (0.40 = 40%) — capturé à la création facture"
    )

    tva_amount_cents: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Montant TVA en centimes (= total_amount * tva_rate)"
    )

    total_ttc_cents: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Total TTC en centimes (= total_amount + tva_amount_cents)"
    )

    # Timeline audit — timestamps des événements métier clés
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'envoi de la facture au client"
    )

    opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'ouverture (suivi email, optionnel)"
    )

    first_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de la première relance envoyée"
    )

    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de la dernière relance envoyée"
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'annulation de la facture"
    )

    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Raison d'annulation (obligatoire dès qu'on annule).",
    )

    # TVA multi-taux (breakdown par taux)
    tva_breakdown: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Détail TVA multi-taux [{'rate':0.20,'base_ht_cents':8000,"
            "'tva_cents':1600,'ttc_cents':9600}]. NULL = taux unique."
        )
    )

    # Relations
    reservation: Mapped["Reservation"] = relationship(
        "Reservation",
        back_populates="invoices"
    )

    charges: Mapped[list["InvoiceCharge"]] = relationship(
        "InvoiceCharge",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )

    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )

    relances: Mapped[list["Relance"]] = relationship(
        "Relance",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )

    # Contraintes
    __table_args__ = (
        # Numéro de facture unique par tenant
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoice_tenant_number"),
        # Une réservation ne peut avoir qu'un seul exemplaire de chaque type de facture
        UniqueConstraint("tenant_id", "reservation_id", "invoice_type", name="uq_invoice_tenant_reservation_type"),
        # Dates cohérentes
        CheckConstraint(
            "due_date >= issue_date",
            name="check_invoice_due_after_issue"
        ),
        # Montant payé ≤ total
        CheckConstraint(
            "paid_amount_cents <= total_amount_cents",
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
        # Type de facture valide
        CheckConstraint(
            "invoice_type IN ('full', 'advance', 'balance')",
            name="check_invoice_type_valid"
        ),
    )

    @property
    def is_paid(self) -> bool:
        """Facture entièrement payée."""
        return self.paid_amount_cents >= self.total_amount_cents

    @property
    def remaining_amount_cents(self) -> int:
        """Montant restant à payer en centimes."""
        return max(0, self.total_amount_cents - self.paid_amount_cents)

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number='{self.invoice_number}', status='{self.status}')>"
