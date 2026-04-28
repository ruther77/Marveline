"""Modèle Deposit — Cautions associées aux réservations."""
from datetime import date
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin
from app.constants import DepositStatus


class Deposit(Base, TimestampMixin, TenantMixin):
    """Caution associée à une réservation.

    Statuts :
        held     : Caution encaissée, en attente de restitution
        released : Caution restituée intégralement
        retained : Caution retenue (partiellement ou totalement)

    Attributes:
        reservation_id: FK vers la réservation
        amount_cents: Montant de la caution en centimes (> 0)
        status: État de la caution (held/released/retained)
        retained_amount_cents: Montant retenu en cas de rétention partielle
        collection_date: Date d'encaissement
        release_date: Date de restitution
        notes: Notes optionnelles
    """

    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    reservation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la réservation parente"
    )

    amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Montant de la caution en centimes (> 0)"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DepositStatus.HELD,
        comment="Statut : held, released, retained"
    )

    retained_amount_cents: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Montant retenu en centimes (rétention partielle)"
    )

    collection_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date d'encaissement de la caution"
    )

    release_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date de restitution de la caution"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Notes libres"
    )

    reservation: Mapped["Reservation"] = relationship("Reservation", back_populates="deposits")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="check_deposit_amount_positive"),
        CheckConstraint(
            "status IN ('held', 'released', 'retained')",
            name="check_deposit_status_valid"
        ),
        CheckConstraint(
            "retained_amount_cents IS NULL OR retained_amount_cents > 0",
            name="check_deposit_retained_positive"
        ),
        Index("ix_deposits_tenant_reservation", "tenant_id", "reservation_id"),
    )

    def __repr__(self) -> str:
        return f"<Deposit(id={self.id}, reservation={self.reservation_id}, status='{self.status}')>"
