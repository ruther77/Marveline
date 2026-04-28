"""Modèle VarianteSide — Liaison many-to-many VariantePlat ↔ SideRestaurant.

Chaque plat peut proposer un sous-ensemble de sides avec un supplément
de prix spécifique (supplement_cts en centimes, ex: 200 = +2€ pour les frites).

Table de liaison :
    variante_plat_id → restaurant_variantes_plat.id
    side_id          → restaurant_sides.id
    supplement_cts   → supplément prix en centimes (0 = inclus)
    is_active        → permet de désactiver un side pour un plat sans supprimer

Contrainte d'unicité : (variante_plat_id, side_id) — un side par plat max.
"""
from sqlalchemy import BigInteger, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, SoftDeleteMixin


class VarianteSide(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Liaison plat → accompagnement avec supplément de prix."""

    __tablename__ = "restaurant_variante_sides"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    variante_plat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_variantes_plat.id", ondelete="CASCADE"),
        nullable=False,
        comment="Plat/boisson/formule concerné"
    )
    side_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_sides.id", ondelete="CASCADE"),
        nullable=False,
        comment="Accompagnement proposé"
    )
    supplement_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Supplément de prix en centimes. 0 = inclus dans le prix du plat"
    )
    # is_active hérite de SoftDeleteMixin

    __table_args__ = (
        UniqueConstraint("variante_plat_id", "side_id", name="uq_variante_side"),
        Index("ix_variante_side_variante", "variante_plat_id"),
        Index("ix_variante_side_side", "side_id"),
        Index("ix_variante_side_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<VarianteSide plat={self.variante_plat_id} side={self.side_id} +{self.supplement_cts}cts>"
