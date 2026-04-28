"""Modèle SideRestaurant — Accompagnements du restaurant.

Un Side est un accompagnement sélectionnable lors d'une commande.
Il peut consommer un ingrédient du stock au service (ex: riz, rougail tomates).

`ingredient_id` + `quantite_par_portion` : si renseignés, le service
génère un MouvementStockRestaurant (consommation) lors du service.
Si null, le side est informatif uniquement (ex: "sans sauce").

Références :
    V2_API_RESTAURANT.md §Page: Salle — Menu (sides par plat)
    FC_RESTAURANT_COMMANDES.md §5 (side_id dans LigneCommande)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3


class SideRestaurant(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Accompagnement commandable associé à un plat.

    is_active=False → accompagnement retiré du menu, non proposé à la commande.
    """

    __tablename__ = "restaurant_sides"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    nom: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nom affiché de l'accompagnement. Ex: 'Riz blanc', 'Rougail tomates'"
    )
    ingredient_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="SET NULL"),
        nullable=True,
        comment="Ingrédient consommé au service (null si side informatif sans stock)"
    )
    quantite_par_portion: Mapped[Optional[float]] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=True,
        comment="Quantité de l'ingrédient consommée par portion servie"
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="URL de l'image de l'accompagnement"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note interne. Ex: 'Ne pas proposer avec le carry végétarien'"
    )
    # is_active hérite de SoftDeleteMixin
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "quantite_par_portion IS NULL OR quantite_par_portion > 0",
            name="check_side_qtite_positive"
        ),
        CheckConstraint(
            "(ingredient_id IS NULL) = (quantite_par_portion IS NULL)",
            name="check_side_ingredient_qtite_couplees"
        ),
        Index("idx_sides_resto_tenant", "tenant_id"),
        Index("idx_sides_resto_ingredient", "ingredient_id"),
        Index("idx_sides_resto_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<SideRestaurant id={self.id} nom={self.nom!r} "
            f"ingredient_id={self.ingredient_id}>"
        )
