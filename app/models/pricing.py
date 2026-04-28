"""Modèles ORM pour les règles de pricing."""
from datetime import date
from typing import Optional, List
from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin


class PricingRule(Base, TimestampMixin, TenantMixin):
    """Règle de tarification (flat, par jour, volume, saisonnier…)."""

    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # flat | per_day | tiered | volume | seasonal | custom
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False)
    # product | category | all
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tiers: Mapped[List["PricingTier"]] = relationship(
        "PricingTier", back_populates="rule", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PricingRule id={self.id} name={self.name!r} type={self.rule_type}>"


class PricingTier(Base, TenantMixin):
    """Palier de prix associé à une règle tiered/volume."""

    __tablename__ = "pricing_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pricing_rules.id", ondelete="CASCADE"), nullable=False
    )
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    max_qty: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

    rule: Mapped["PricingRule"] = relationship("PricingRule", back_populates="tiers")

    def __repr__(self) -> str:
        return f"<PricingTier id={self.id} rule_id={self.rule_id} min_qty={self.min_qty}>"
