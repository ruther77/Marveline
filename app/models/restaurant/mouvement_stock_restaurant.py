"""Modèle MouvementStockRestaurant — Journal des mouvements de stock ingrédients.

Chaque mutation de stock (entree, consommation, inventaire, perte,
transfert_entrant) génère une ligne immuable dans cette table.

`quantite` est SIGNÉ : positif pour entrees/inventaires correctifs positifs,
négatif pour consommations et pertes.
`stock_apres` est enregistré atomiquement pour permettre de rejouer
l'historique sans recalcul.

Types de mouvement :
  - entree           : réception livraison fournisseur (+)
  - consommation     : usage lors du lancement d'une marmite ou ajout ligne (−)
  - transfert_entrant: réception depuis épicerie (créé par service transfert) (+)
  - inventaire       : correction écart comptage (± selon delta)
  - perte            : déchets, casse, péremption (−)

Références :
    V2_API_RESTAURANT.md §Page: Ingrédients & Stock
    FC_RESTAURANT_INGREDIENTS.md §4 (types, sémantique, invariant atomique)
    ADR-14 (stock_actuel lecture directe DB)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3

TYPES_MOUVEMENT = ('entree', 'consommation', 'transfert_entrant', 'inventaire', 'perte')


class MouvementStockRestaurant(Base, TenantMixin):
    """Ligne de journal immuable d'un mouvement de stock ingrédient.

    Pas de TimestampMixin : `date_mouvement` est fourni explicitement
    (timestamp du mouvement réel, pas de la ligne DB). `created_at`
    seul suffit pour l'audit technique.
    Pas de SoftDeleteMixin : journal immuable.
    """

    __tablename__ = "restaurant_mouvements_stock"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ingredient_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK vers restaurant_ingredients (null pour transferts sans ingrédient associé)"
    )
    type_mouvement: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="Type: entree | consommation | transfert_entrant | inventaire | perte"
    )
    quantite: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Quantité signée : + pour entrée, − pour consommation/perte"
    )
    stock_apres: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Stock ingrédient après ce mouvement — enregistré atomiquement"
    )
    date_mouvement: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Timestamp du mouvement réel (fourni par le frontend via now())"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre. Ex: 'Livraison METRO', 'Périmé'"
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant créé le mouvement (null si mouvement automatique)"
    )
    etl_import_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("etl_imports.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK vers etl_imports.id (traçabilité origine ETL + idempotence/revert)"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de création de la ligne DB"
    )
    # tenant_id hérite de TenantMixin (= 3 pour restaurant)

    __table_args__ = (
        CheckConstraint(
            f"type_mouvement IN {TYPES_MOUVEMENT}",
            name="check_mouvement_stock_type_valide"
        ),
        CheckConstraint("stock_apres >= 0", name="check_mouvement_stock_apres_positif"),
        Index("idx_mvt_stock_resto_tenant", "tenant_id"),
        Index("idx_mvt_stock_resto_ingredient", "ingredient_id"),
        Index("idx_mvt_stock_resto_date", "date_mouvement"),
        Index("idx_mvt_stock_resto_created_by", "created_by_id"),
        Index("idx_mvt_stock_resto_etl_import", "etl_import_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MouvementStockRestaurant id={self.id} type={self.type_mouvement!r} "
            f"ingredient_id={self.ingredient_id} quantite={self.quantite}>"
        )
