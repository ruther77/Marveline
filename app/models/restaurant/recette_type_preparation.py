"""Modèle RecetteTypePreparation — Ingrédients d'une recette restaurant.

Table de liaison TypePreparation ↔ IngredientRestaurant.
Définit la quantité requise de chaque ingrédient par batch de cuisson.

`quantite_par_batch` : quantité en unité de l'ingrédient (ex: kg) consommée
pour produire un batch complet (portions_par_batch portions).

Références :
    V2_API_RESTAURANT.md §Page: Cuisine (stock_requis dans shape TypePreparation)
    FC_RESTAURANT_CUISINE.md §3 (recettes_type_preparation, POST /lancer atomique)
    ADR-09 (niveau 1 → instances créées depuis TypePreparation + ses recettes)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3


class RecetteTypePreparation(Base, TenantMixin, TimestampMixin):
    """Ligne de recette : quantité d'un ingrédient pour un batch d'un type de préparation.

    Pas de SoftDeleteMixin : une ligne de recette se supprime ou se modifie,
    pas de soft-delete (l'historique est dans les mouvements de stock).
    """

    __tablename__ = "restaurant_recettes_type_preparation"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    type_preparation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_types_preparation.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers restaurant_types_preparation"
    )
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers restaurant_ingredients"
    )
    quantite_par_batch: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Quantité de l'ingrédient pour un batch complet (en unité de l'ingrédient)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre. Ex: 'à ajuster selon la taille des morceaux'"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "quantite_par_batch > 0",
            name="check_recette_quantite_positive"
        ),
        Index("idx_recettes_type_prep_tenant", "tenant_id"),
        Index("idx_recettes_type_prep_type", "type_preparation_id"),
        Index("idx_recettes_type_prep_ingredient", "ingredient_id"),
        Index(
            "uq_recettes_type_prep_pair",
            "type_preparation_id", "ingredient_id",
            unique=True
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RecetteTypePreparation id={self.id} "
            f"type_preparation_id={self.type_preparation_id} "
            f"ingredient_id={self.ingredient_id} "
            f"quantite_par_batch={self.quantite_par_batch}>"
        )
