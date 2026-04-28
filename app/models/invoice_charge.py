"""Modèle InvoiceCharge — Charges additionnelles sur facture (dommages, main-d'œuvre)."""
from typing import Optional
from decimal import Decimal
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin


class InvoiceCharge(Base, TimestampMixin, TenantMixin):
    """Charge additionnelle sur une facture.

    Types :
        DAMAGE : montant en centimes fourni directement
        LABOR  : calculé à partir de heures × taux horaire (weekday/weekend/night)

    Attributes:
        invoice_id: FK vers la facture parente
        charge_type: 'DAMAGE' ou 'LABOR'
        amount_cents: Montant en centimes (toujours positif)
        description: Description obligatoire de la charge
        hours: Nombre d'heures (LABOR uniquement, nullable)
        day_type: Type de jour pour tarification (weekday/weekend/night)
        damage_type_id: Référence type de dommage (optionnel, FK Session I)
    """

    __tablename__ = "invoice_charges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la facture parente"
    )

    charge_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type de charge : DAMAGE ou LABOR"
    )

    amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Montant de la charge en centimes (> 0)"
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Description de la charge"
    )

    hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Nombre d'heures (LABOR uniquement)"
    )

    day_type: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Type de jour : weekday, weekend, night"
    )

    damage_type_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("damage_types.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK vers le type de dommage (optionnel)"
    )

    # Relation
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="charges")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="check_charge_amount_positive"),
        CheckConstraint(
            "charge_type IN ('DAMAGE', 'LABOR', 'DELIVERY')",
            name="check_charge_type_valid"
        ),
        CheckConstraint(
            "day_type IS NULL OR day_type IN ('weekday', 'weekend', 'night')",
            name="check_charge_day_type_valid"
        ),
        Index("ix_invoice_charges_tenant_invoice", "tenant_id", "invoice_id"),
    )

    def __repr__(self) -> str:
        return f"<InvoiceCharge(id={self.id}, type='{self.charge_type}', amount={self.amount_cents})>"
