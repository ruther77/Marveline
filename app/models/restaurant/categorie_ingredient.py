"""Modèle CategorieIngredient — Catégories d'ingrédients restaurant (tenant_id=3).

Les catégories regroupent les ingrédients pour l'affichage et les filtres
de l'UI (FC_RESTAURANT_INGREDIENTS.md §3 : categorie_id + categorie_nom).

Le champ `is_proteine` permet de filtrer les protéines pour le dashboard
ruptures (V2_API_RESTAURANT.md : "protéines uniquement — filtre est_proteine").

Références :
    FC_RESTAURANT_INGREDIENTS.md §3 (categorie_id, categorie_nom)
    V2_API_RESTAURANT.md §Page: Dashboard (ruptures protéines uniquement)
"""
from sqlalchemy import BigInteger, Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class CategorieIngredient(Base, TenantMixin, TimestampMixin):
    """Catégorie d'ingrédient du restaurant.

    Ex: 'Protéines', 'Légumes', 'Épices', 'Base', 'Condiments'.
    Pas de SoftDeleteMixin : une catégorie est stable — désactivée
    en supprimant les ingrédients qui l'utilisent.
    """

    __tablename__ = "restaurant_categories_ingredient"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    nom: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Nom affiché de la catégorie. Ex: 'Protéines', 'Légumes'"
    )
    image_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="URL de l'icône/image de la catégorie"
    )
    is_proteine: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True si protéine : incluse dans le calcul des ruptures dashboard"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        Index("idx_categories_ingredient_tenant", "tenant_id"),
        Index("uq_categories_ingredient_tenant_nom", "tenant_id", "nom", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<CategorieIngredient id={self.id} nom={self.nom!r} "
            f"is_proteine={self.is_proteine}>"
        )
