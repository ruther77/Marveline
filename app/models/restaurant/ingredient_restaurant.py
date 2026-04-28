"""Modèle IngredientRestaurant — Matières premières du restaurant (tenant_id=3).

Niveau 2 du stock restaurant (ADR-09) : ingrédients bruts en kg.
`stock_actuel` est mis à jour atomiquement à chaque mouvement de stock.
ADR-14 : `stock_actuel` doit être lu directement en DB, jamais depuis Redis.

Les seuils et statuts badge calculés côté service :
  - ok      : stock_actuel > stock_alerte
  - alerte  : 0 < stock_actuel <= stock_alerte
  - rupture : stock_actuel = 0

Références :
    V2_API_RESTAURANT.md §Page: Ingrédients & Stock
    FC_RESTAURANT_INGREDIENTS.md §3, §4
    ADR-09 (2 niveaux de stock), ADR-14 (lecture directe DB)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3


class IngredientRestaurant(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Ingrédient brut du restaurant (matière première en stock).

    stock_actuel et stock_alerte en NUMERIC(10,3) — précision kg.
    cout_unitaire_cts en centimes BigInteger (ex: 89000 = 890,00 XPF/kg).
    """

    __tablename__ = "restaurant_ingredients"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    categorie_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_categories_ingredient.id", ondelete="SET NULL"),
        nullable=True,
        comment="Catégorie de l'ingrédient (FK restaurant_categories_ingredient)"
    )
    nom: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nom de l'ingrédient. Ex: 'Poulet', 'Tomates concassées'"
    )
    unite_stock: Mapped[str] = mapped_column(
        String(10), nullable=False, default="kg",
        comment="Unité de mesure. Ex: 'kg', 'L', 'pièce'"
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="URL de l'image de l'ingrédient"
    )
    stock_actuel: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False, default=0,
        comment="Stock actuel en unité de mesure (ADR-14: lecture directe DB)"
    )
    stock_alerte: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False, default=0,
        comment="Seuil bas — déclenche badge alerte si stock_actuel <= stock_alerte"
    )
    cout_unitaire_cts: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Coût d'achat par unité en centimes. Ex: 89000 = 890,00 XPF/kg"
    )
    categorie_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment=(
            "Code catégorie unifié (91 codes alimentaires, même taxonomie que "
            "epicerie_produits.categorie). Rempli par le pipeline ETL. "
            "categorie_id (15 cats resto) reste pour compat UI."
        )
    )
    categorie: Mapped[Optional["CategorieIngredient"]] = relationship(  # type: ignore[name-defined]
        "CategorieIngredient",
        foreign_keys=[categorie_id],
        lazy="selectin",
    )
    # is_active hérite de SoftDeleteMixin
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint("stock_actuel >= 0", name="check_ingredient_stock_positif"),
        CheckConstraint("stock_alerte >= 0", name="check_ingredient_alerte_positif"),
        Index("idx_ingredients_resto_tenant", "tenant_id"),
        Index("idx_ingredients_resto_categorie", "categorie_id"),
        Index("idx_ingredients_resto_tenant_active", "tenant_id", "is_active"),
        Index("idx_resto_ingredients_categorie_code", "categorie_code"),
    )

    def __repr__(self) -> str:
        return (
            f"<IngredientRestaurant id={self.id} nom={self.nom!r} "
            f"stock={self.stock_actuel} {self.unite_stock}>"
        )
