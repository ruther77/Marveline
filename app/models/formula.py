"""Modèles ORM Formula et FormulaItem — formules Marveline prix/personne."""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Formula(Base, TimestampMixin, SoftDeleteMixin):
    """Formule Marveline : composition fixe × nombre de convives.

    Deux sous-types :
    - classic : price_per_person_cents × nb_guests → montant total
    - vin_honneur : price_per_person_cents × nb_guests (par tranches)

    Relations :
        - items : FormulaItem (composition détaillée)
    """

    __tablename__ = "formulas"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)

    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    formula_type = Column(String(20), nullable=False, default="classic")
    """'classic' | 'vin_honneur'"""

    price_per_person_cents = Column(BigInteger, nullable=False)
    """Prix TTC par personne en centimes (ex: 226 = 2,26€)."""

    featured = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    items = relationship(
        "FormulaItem",
        back_populates="formula",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class FormulaItem(Base, TimestampMixin):
    """Ligne de composition d'une formule : ratio de produit par personne.

    quantity_per_person est un ratio flottant :
    - 3.0 → 3 verres / convive
    - 0.5 → 1 article pour 2 convives
    """

    __tablename__ = "formula_items"

    id = Column(Integer, primary_key=True)
    formula_id = Column(
        Integer, ForeignKey("formulas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(Integer, nullable=False)
    """Référence produit (pas FK car cross-tenant possible)."""

    quantity_per_person = Column(Float, nullable=False)
    """Ratio : nb unités par convive."""

    formula = relationship("Formula", back_populates="items")
