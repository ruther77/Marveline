"""Modèle VariantePlat — Plats, boissons et formules du menu restaurant.

Chaque VariantePlat est un article commandable. Le `type` distingue :
  - plat    : plat cuisiné servi depuis une InstancePreparation
  - boisson : boisson servie à l'unité
  - formule : formule combinant plat + boisson (price bundle)

`taux_tva` : stocké en centièmes de % (ex: 550 = 5,5%, 1000 = 10%, 2000 = 20%).
Conforme ADR-06-BIS : TVA variable par catégorie d'article, pas de taux global.

`ingredient_proteine_id` + `quantite_proteine` : FK vers l'ingrédient protéine
principal du plat. Permet à la formule boissons de calculer si l'unité est
un multiple de 3 (ex: 3 boissons → 1 bouteille suggérée).

`type_preparation_id` : FK vers le TypePreparation associé au plat
(null pour boissons et formules sans cuisson).

Références :
    V2_API_RESTAURANT.md §Page: Salle — Menu, §Formule boissons
    FC_RESTAURANT_COMMANDES.md §4 (atomicité POST /lignes, stock-requis)
    ADR-06-BIS (TVA variable par catégorie)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3

TYPES_VARIANTE = ('plat', 'boisson', 'formule')


class VariantePlat(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Article commandable du menu (plat, boisson ou formule).

    `prix_vente_cts` : prix en centimes (BigInteger, ex: 150000 = 1 500 XPF).
    is_active=False → article retiré du menu, non affichable dans l'UI.
    """

    __tablename__ = "restaurant_variantes_plat"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    nom: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Nom affiché sur le menu. Ex: 'Carry poulet', 'Jus de goyave'"
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type d'article : plat | boisson | formule"
    )
    prix_vente_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Prix de vente en centimes. Ex: 150000 = 1 500 XPF"
    )
    taux_tva: Mapped[int] = mapped_column(
        Integer, nullable=False, default=550,
        comment="Taux TVA en centièmes de % (ADR-06-BIS). Ex: 550 = 5,5%, 2000 = 20%"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Description libre affichée sur le menu (optionnel)"
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="URL de l'image du plat (relative ou absolue)"
    )
    type_preparation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_types_preparation.id", ondelete="SET NULL"),
        nullable=True,
        comment="TypePreparation associé (null pour boissons et formules sans cuisson)"
    )
    ingredient_proteine_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="SET NULL"),
        nullable=True,
        comment="Ingrédient protéine principal du plat (pour dashboard ruptures)"
    )
    quantite_proteine: Mapped[Optional[float]] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=True,
        comment="Quantité de protéine par portion (en unité de l'ingrédient protéine)"
    )
    categorie: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Catégorie de l'article (ex: 'softs', 'alcools', 'jus'). Surtout utile pour les boissons."
    )
    # is_active hérite de SoftDeleteMixin (article actif dans le menu)
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"type IN {TYPES_VARIANTE}",
            name="check_variante_plat_type_valide"
        ),
        CheckConstraint(
            "prix_vente_cts >= 0",
            name="check_variante_plat_prix_positif"
        ),
        CheckConstraint(
            "taux_tva >= 0",
            name="check_variante_plat_tva_positive"
        ),
        CheckConstraint(
            "quantite_proteine IS NULL OR quantite_proteine > 0",
            name="check_variante_plat_qtite_proteine_positive"
        ),
        Index("idx_variantes_plat_tenant", "tenant_id"),
        Index("idx_variantes_plat_type_prep", "type_preparation_id"),
        Index("idx_variantes_plat_proteine", "ingredient_proteine_id"),
        Index("idx_variantes_plat_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<VariantePlat id={self.id} nom={self.nom!r} "
            f"type={self.type!r} prix={self.prix_vente_cts}cts>"
        )
