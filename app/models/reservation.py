"""Modèles Reservation et ReservationLine - Réservations d'événements."""
from datetime import date
from typing import Optional
from sqlalchemy import (
    BigInteger, CheckConstraint, Date, ForeignKey, Integer,
    String, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin
from app.constants import ReservationStatus


class Reservation(Base, TimestampMixin, TenantMixin):
    """Réservation d'un client pour un événement.

    Attributes:
        customer_id: ID du client (FK)
        reference: Référence unique (ex: "RES-2026-0001")
        event_date: Date de l'événement
        delivery_date: Date de livraison (≤ event_date)
        return_date: Date de retour (≥ event_date)
        event_location: Lieu de l'événement
        status: Statut (draft, confirmed, in_progress, completed, cancelled)
        total_amount: Montant total en CENTIMES
        deposit_amount: Montant caution en CENTIMES
        deposit_paid: Caution payée (oui/non)
    """

    __tablename__ = "reservations"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Client
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="ID du client"
    )

    # Référence unique
    reference: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Référence unique de réservation (RES-2026-0001)"
    )

    # Dates
    event_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date de l'événement"
    )

    delivery_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date de livraison"
    )

    return_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date de retour"
    )

    # Lieu
    event_location: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Lieu de l'événement"
    )

    # Statut
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReservationStatus.DRAFT,
        comment="Statut de la réservation"
    )

    # Montants (en centimes)
    total_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant total en centimes"
    )

    deposit_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant caution en centimes"
    )

    deposit_paid: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="Caution payée"
    )

    # Relations
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="reservations"
    )

    lines: Mapped[list["ReservationLine"]] = relationship(
        "ReservationLine",
        back_populates="reservation",
        cascade="all, delete-orphan"
    )

    invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice",
        back_populates="reservation",
        uselist=False
    )

    # Contraintes
    __table_args__ = (
        # Dates cohérentes
        CheckConstraint(
            "delivery_date <= event_date",
            name="check_reservation_delivery_before_event"
        ),
        CheckConstraint(
            "return_date >= event_date",
            name="check_reservation_return_after_event"
        ),
        CheckConstraint(
            "return_date >= delivery_date",
            name="check_reservation_return_after_delivery"
        ),
        # Statut valide
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'in_progress', 'completed', 'cancelled')",
            name="check_reservation_status_valid"
        ),
        # Montants positifs
        CheckConstraint(
            "total_amount >= 0",
            name="check_reservation_total_positive"
        ),
        CheckConstraint(
            "deposit_amount >= 0",
            name="check_reservation_deposit_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<Reservation(id={self.id}, ref='{self.reference}', status='{self.status}')>"


class ReservationLine(Base, TimestampMixin, TenantMixin):
    """Ligne de réservation - produit et quantité réservée.

    Attributes:
        reservation_id: ID de la réservation (FK)
        product_id: ID du produit (FK)
        quantity: Quantité réservée (> 0)
        unit_price: Prix unitaire par jour en CENTIMES (snapshot au moment de la réservation)
        subtotal: Sous-total en CENTIMES (quantity × unit_price)
    """

    __tablename__ = "reservation_lines"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Réservation
    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID de la réservation"
    )

    # Produit
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="ID du produit"
    )

    # Quantité
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Quantité réservée"
    )

    # Prix snapshot (en centimes)
    unit_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Prix unitaire par jour en centimes (snapshot)"
    )

    subtotal: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Sous-total en centimes (quantity × unit_price)"
    )

    # Relations
    reservation: Mapped["Reservation"] = relationship(
        "Reservation",
        back_populates="lines"
    )

    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="reservation_lines"
    )

    # Contraintes
    __table_args__ = (
        # Un produit une seule fois par réservation
        UniqueConstraint(
            "reservation_id", "product_id",
            name="uq_reservation_line_reservation_product"
        ),
        # Quantité positive
        CheckConstraint(
            "quantity > 0",
            name="check_reservation_line_quantity_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<ReservationLine(id={self.id}, reservation_id={self.reservation_id}, qty={self.quantity})>"
