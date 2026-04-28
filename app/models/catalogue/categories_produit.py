"""Modèle CategorieProduit — Référentiel catégories alimentaires partagé (M00).

Table sans tenant_id : référentiel technique partagé par l'épicerie (tenant_id=2)
et le restaurant (tenant_id=3). Seedée intégralement par la migration M00.

Références :
    ADR-01  : catalogue sans tenant_id
    ADR-05  : 50 catégories, 12 familles, structure plate 3 niveaux
    ADR-06  : est_ingredient_resto filtre le lien épicerie → restaurant
    ADR-06-BIS : tva_defaut initialisé sur article_epicerie à la création
    ADR-14  : categories_produit en cache Redis TTL 24h (invalidé par migration)
"""
from typing import Optional

from sqlalchemy import Boolean, Float, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class CategorieProduit(Base, TimestampMixin, SoftDeleteMixin):
    """Catégorie produit du référentiel alimentaire partagé.

    Hiérarchie à 3 niveaux stockée en colonnes plates (ADR-05) :
      famille (niveau 1) → categorie (niveau 2) → sous_categorie (niveau 3, nullable)

    Pas de self-referencing FK — la hiérarchie est requêtable via GROUP BY famille.
    Pas de TenantMixin — les deux entités partagent ce référentiel via FK code.
    """

    __tablename__ = "categories_produit"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True,
        comment="Code court unique. Ex: 'frais_viande', 'bois_biere', 'epic_pate'"
    )
    nom: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Libellé affiché. Ex: 'Viandes fraîches', 'Bières'"
    )
    famille: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Niveau 1. Ex: 'Produits Frais', 'Boissons', 'Épicerie Salée'"
    )
    categorie: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Niveau 2. Ex: 'Viandes', 'Charcuterie', 'Bières'"
    )
    sous_categorie: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Niveau 3 optionnel. Ex: 'Bières artisanales', 'Rôtis'"
    )
    tva_defaut: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.20,
        comment="Taux TVA par défaut (ADR-06-BIS). 0.055 pour alim., 0.20 pour hygiène/entretien"
    )
    ordre_famille: Mapped[int] = mapped_column(
        Integer, nullable=False, default=99,
        comment="Ordre d'affichage de la famille dans les listes (tri ascendant)"
    )
    ordre_categorie: Mapped[int] = mapped_column(
        Integer, nullable=False, default=99,
        comment="Ordre d'affichage dans la famille (tri ascendant)"
    )
    est_ingredient_resto: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="True si la catégorie peut alimenter le restaurant (ADR-06). "
                "Filtre : article_epicerie → ingredient via transfert_interne"
    )
    priorite_ingredient: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Priorité de tri pour le sélecteur d'ingrédients restaurant. 0=non prioritaire"
    )
    # is_active héritée de SoftDeleteMixin (BOOLEAN NOT NULL DEFAULT true)

    __table_args__ = (
        Index("idx_categories_famille", "famille"),
        Index(
            "idx_categories_ingredient",
            "est_ingredient_resto",
            postgresql_where=text("est_ingredient_resto = TRUE"),
        ),
    )

    def __repr__(self) -> str:
        return f"<CategorieProduit code={self.code!r} famille={self.famille!r}>"
