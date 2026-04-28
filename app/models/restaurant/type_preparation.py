"""Modèle TypePreparation — Templates de recettes (cuisine restaurant).

Un TypePreparation définit une recette standard (ex: "Sauce rougail") avec
ses ingrédients requis par batch (via recettes_type_preparation).
Les marmites cuisinées au quotidien sont des `InstancesPreparation`.

`seuil_alerte_portions` : nombre de portions restantes en dessous duquel
le badge passe à "faible" (vs "dispo"). Si portions_restantes = 0 → "epuise".

Références :
    V2_API_RESTAURANT.md §Page: Cuisine (GET /types-preparation)
    FC_RESTAURANT_CUISINE.md §3 (statut_badge : dispo/faible/epuise)
    ADR-09 (niveau 1 stock restaurant)
"""
from sqlalchemy import BigInteger, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class TypePreparation(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Recette template pour le lancement de marmites.

    Chaque TypePreparation référence ses ingrédients via
    RecetteTypePreparation (table de liaison).
    is_active=False → recette archivée, non proposée pour le lancement.
    """

    __tablename__ = "restaurant_types_preparation"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    nom: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nom de la recette. Ex: 'Sauce rougail', 'Carry poulet'"
    )
    portions_par_batch: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Nombre de portions standard par batch de cuisson"
    )
    temps_cuisson_min: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Temps de cuisson indicatif en minutes"
    )
    seuil_alerte_portions: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5,
        comment="Portions restantes en dessous de ce seuil → badge 'faible'. 0 = pas d'alerte."
    )
    image_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="URL de l'image de la recette/base cuisinée"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Notes de recette libres (instructions, conseils)"
    )
    # is_active hérite de SoftDeleteMixin
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint("portions_par_batch >= 1", name="check_type_prep_batch_positif"),
        CheckConstraint("temps_cuisson_min >= 0", name="check_type_prep_cuisson_positif"),
        CheckConstraint("seuil_alerte_portions >= 0", name="check_type_prep_seuil_positif"),
        Index("idx_types_prep_tenant", "tenant_id"),
        Index("idx_types_prep_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<TypePreparation id={self.id} nom={self.nom!r} "
            f"portions_par_batch={self.portions_par_batch}>"
        )
