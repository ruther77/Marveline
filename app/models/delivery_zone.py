"""Modèle DeliveryZone — zones de livraison couvertes par Marveline."""
from typing import Optional

from sqlalchemy import BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class DeliveryZone(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Zone de livraison (département) avec tarifs associés.

    Marveline couvre 7 départements :
        Oise (60), Somme (80), Aisne (02), Val d'Oise (95),
        Seine-Maritime (76), Eure (27), Pas-de-Calais (62).

    Attributes:
        department_code: Code INSEE du département (ex: "60")
        department_name: Nom du département (ex: "Oise")
        delivery_fee_cents: Tarif livraison de base en centimes (0 = sur devis)
        sunday_surcharge_cents: Supplément reprise dimanche en centimes
        notes: Informations complémentaires (conditions, distance max, etc.)
    """

    __tablename__ = "delivery_zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    department_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Code INSEE du département (ex: '60' pour Oise)",
    )

    department_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nom du département",
    )

    delivery_fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Tarif livraison de base en centimes (0 = sur devis)",
    )

    sunday_surcharge_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Supplément reprise dimanche en centimes",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Informations complémentaires (conditions, distance max…)",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "department_code",
            name="uq_delivery_zone_tenant_dept",
        ),
    )
