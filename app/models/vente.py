"""Modèles Vente — ventes directes et leurs sous-entités."""
from datetime import date
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, TIMESTAMP
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.constants import VenteStatus

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.reservation import Reservation
    from app.models.product import Product


class Vente(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Vente directe associée à un client.

    Attributes:
        reference: Référence unique (VTE-YYYY-NNNN) par tenant
        customer_id: FK vers le client
        status: Statut (draft|pending|deposit_paid|fully_paid|overdue|refunded)
        total_cents: Montant TTC total en centimes
        paid_cents: Montant payé en centimes (SUM vente_payments)
    """

    __tablename__ = "ventes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    reference: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Référence unique VTE-YYYY-NNNN"
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=VenteStatus.DRAFT
    )

    subtotal_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False, default=0)
    tva_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False, default=0)
    paid_cents: Mapped[int] = mapped_column(
        BigInteger(), nullable=False, default=0,
        comment="SUM des paiements enregistrés"
    )

    deposit_pct: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    payment_due_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    # FKs optionnelles sans contrainte ORM pour éviter circularités
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    reservation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True
    )

    # Relations
    customer: Mapped["Customer"] = relationship("Customer", foreign_keys=[customer_id])
    lines: Mapped[list["VenteLine"]] = relationship(
        "VenteLine", back_populates="vente", cascade="all, delete-orphan"
    )
    payments: Mapped[list["VentePayment"]] = relationship(
        "VentePayment", back_populates="vente", cascade="all, delete-orphan",
        order_by="VentePayment.payment_date"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "reference", name="uq_vente_tenant_reference"),
        CheckConstraint(
            "status IN ('draft','pending','deposit_paid','fully_paid','overdue','refunded','cancelled')",
            name="check_vente_status_valid"
        ),
        CheckConstraint("total_cents >= 0", name="check_vente_total_positive"),
        CheckConstraint("paid_cents >= 0", name="check_vente_paid_positive"),
        Index("ix_ventes_tenant_composite", "tenant_id", "id"),
        Index("ix_ventes_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_ventes_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Vente(id={self.id}, ref='{self.reference}', status='{self.status}')>"


class VenteLine(Base, TenantMixin):
    """Ligne d'une vente directe."""

    __tablename__ = "vente_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    vente_id: Mapped[int] = mapped_column(
        ForeignKey("ventes.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    label: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False)

    created_at: Mapped[date] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )

    vente: Mapped["Vente"] = relationship("Vente", back_populates="lines")
    product: Mapped[Optional["Product"]] = relationship("Product")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_vente_line_qty_positive"),
        CheckConstraint("unit_price_cents >= 0", name="check_vente_line_price_positive"),
        Index("ix_vente_lines_tenant_vente", "tenant_id", "vente_id"),
    )

    def __repr__(self) -> str:
        return f"<VenteLine(id={self.id}, vente={self.vente_id}, label='{self.label}')>"


class VentePayment(Base, TenantMixin):
    """Paiement associé à une vente directe."""

    __tablename__ = "vente_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    vente_id: Mapped[int] = mapped_column(
        ForeignKey("ventes.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date(), nullable=False)
    is_deposit: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    created_at: Mapped[date] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )
    created_by: Mapped[int] = mapped_column(BigInteger(), nullable=False)

    vente: Mapped["Vente"] = relationship("Vente", back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="check_vente_payment_amount_positive"),
        Index("ix_vente_payments_tenant_vente", "tenant_id", "vente_id"),
    )

    def __repr__(self) -> str:
        return f"<VentePayment(id={self.id}, vente={self.vente_id}, amount={self.amount_cents})>"
