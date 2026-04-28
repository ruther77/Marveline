"""Modèle IngredientEpicerieMapping — Mapping ingrédient restaurant ↔ produits épicerie.

Pour chaque `IngredientRestaurant`, définit la liste ordonnée des `EpicerieProduit`
qui peuvent servir de source de réapprovisionnement, avec un facteur de conversion
entre l'unité de vente épicerie et l'unité de stock ingrédient.

Exemples :
  - Ingrédient "Huile d'olive" (unité stock = L)
      → produit "Bidon 5L" (unité vente = U) avec facteur_conv = 5.0
      → produit "Bouteille 1L × 6" (unité vente = U) avec facteur_conv = 6.0
  - Ingrédient "Farine" (unité stock = kg)
      → produit "Sac 25kg" (unité vente = U) avec facteur_conv = 25.0

Résolution cascade mixte (ADR — 2026-04-21) : le résolveur parcourt les mappings
triés par `ordre`, lit le stock épicerie disponible de chaque produit, cumule les
prélèvements (qté × facteur_conv) jusqu'à couvrir le besoin ingrédient.
S'il reste un déficit après le dernier produit, le transfert est créé en
"couverture partielle" avec un warning côté service.

Isolation multi-tenant :
  - `tenant_id` = tenant restaurant (propriétaire du mapping)
  - `produit_id` référence epicerie_produits (tenant épicerie) — cross-tenant
  - Contrôle métier : le service valide que le produit appartient au tenant
    épicerie jumelé du tenant restaurant (architecture ISO-APP-01)

Références :
    memory/transferts-analysis.md
    memory/monorepo-architecture-decisions.md
"""
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin

CONV_PRECISION = 10
CONV_SCALE = 4


class IngredientEpicerieMapping(Base, TenantMixin, TimestampMixin):
    """Mapping durable ingrédient restaurant → produit épicerie source.

    Cardinalité : un ingrédient peut avoir N mappings (un par produit source) ;
    un produit épicerie peut apparaître dans les mappings de plusieurs
    ingrédients (ex : même bouteille d'huile pour 'huile cuisson' et
    'huile assaisonnement').
    """

    __tablename__ = "restaurant_ingredient_epicerie_mappings"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True,
    )
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK ingrédient restaurant (propriétaire du mapping)",
    )
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK produit épicerie source (cross-tenant)",
    )
    ordre: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Ordre de préférence (0 = préféré, 1 = fallback suivant, ...)",
    )
    facteur_conv: Mapped[float] = mapped_column(
        Numeric(CONV_PRECISION, CONV_SCALE), nullable=False, default=1,
        comment=(
            "Facteur de conversion : 1 unité vente produit = facteur_conv unités "
            "de stock ingrédient. Ex : pack 6×1L → facteur_conv=6.0 (litres)."
        ),
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Notes libres (ex: 'préféré pour cuisson', 'rupture fréquente')",
    )
    # tenant_id hérite de TenantMixin (= tenant restaurant)
    # created_at / updated_at hérités de TimestampMixin

    ingredient: Mapped["IngredientRestaurant"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "IngredientRestaurant",
        foreign_keys=[ingredient_id],
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "ingredient_id", "produit_id",
            name="uq_ingr_epi_mapping_ingr_prod",
        ),
        CheckConstraint("ordre >= 0", name="ck_ingr_epi_mapping_ordre_positif"),
        CheckConstraint("facteur_conv > 0", name="ck_ingr_epi_mapping_facteur_positif"),
        Index("ix_ingr_epi_mapping_tenant", "tenant_id"),
        Index("ix_ingr_epi_mapping_ingredient_ordre", "ingredient_id", "ordre"),
        Index("ix_ingr_epi_mapping_produit", "produit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<IngredientEpicerieMapping id={self.id} "
            f"ingr={self.ingredient_id} prod={self.produit_id} "
            f"ordre={self.ordre} facteur={self.facteur_conv}>"
        )
