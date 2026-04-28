"""Modèle EpicerieStockMovement — Journal des mouvements de stock épicerie.

Chaque mutation de stock génère une ligne immuable (journal d'audit).
`quantite` est signée : positif pour entrées, négatif pour sorties/ventes/pertes.

Types :
  - ENTREE               : réception livraison fournisseur (+)
  - SORTIE               : retrait manuel (−)
  - VENTE                : vente POS (−)
  - AJUSTEMENT           : correction comptage ou annulation vente (± selon delta)
  - PERTE                : déchets, casse, péremption (−)
  - TRANSFERT_RESTAURANT : transfert vers restaurant (−)

Références :
    V2_API_EPICERIE.md §Matrice effets de bord stock
    FC_EPICERIE_INVENTAIRE.md §3 (types, invariant atomique)
    ADR-14 (stock_actuel lecture directe DB)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3

TYPES_MOUVEMENT_EPICERIE = (
    'ENTREE', 'SORTIE', 'VENTE', 'AJUSTEMENT', 'PERTE', 'TRANSFERT_RESTAURANT'
)


class EpicerieStockMovement(Base, TenantMixin):
    """Ligne de journal immuable d'un mouvement de stock épicerie.

    Pas de TimestampMixin : `date_mouvement` fourni explicitement.
    `created_at` seul pour l'audit technique.
    Pas de SoftDeleteMixin : journal immuable.
    """

    __tablename__ = "epicerie_stock_movements"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers le produit épicerie"
    )
    type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="Type : ENTREE | SORTIE | VENTE | AJUSTEMENT | PERTE | TRANSFERT_RESTAURANT"
    )
    quantite: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Quantité signée (+ entrée, − sortie/vente/perte)"
    )
    stock_apres: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Stock après ce mouvement — enregistré atomiquement"
    )
    date_mouvement: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Timestamp du mouvement réel"
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Référence (ex: ANNULATION-VTE-0001, COMPTAGE-2026-03-11)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre"
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant créé le mouvement (null si automatique)"
    )
    # Contexte — au plus une référence selon le type de mouvement
    vente_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK epicerie_ventes — renseigné pour type=VENTE ou AJUSTEMENT d'annulation"
    )
    supply_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK epicerie_supply_orders — renseigné pour type=ENTREE"
    )
    transfer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK internal_transfers — renseigné pour type=TRANSFERT_RESTAURANT"
    )
    etl_import_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK etl_imports — renseigné pour type=ENTREE via ETL validation"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de création de la ligne DB"
    )
    # tenant_id hérite de TenantMixin (= 2 pour épicerie)

    __table_args__ = (
        CheckConstraint(
            f"type IN {TYPES_MOUVEMENT_EPICERIE}",
            name="check_epicerie_movement_type_valide"
        ),
        CheckConstraint(
            "stock_apres >= 0",
            name="check_epicerie_movement_stock_apres_positif"
        ),
        Index("idx_epicerie_mvt_tenant", "tenant_id"),
        Index("idx_epicerie_mvt_produit", "produit_id"),
        Index("idx_epicerie_mvt_type", "type"),
        Index("idx_epicerie_mvt_date", "date_mouvement"),
        Index("idx_epicerie_mvt_vente", "vente_id"),
        Index("idx_epicerie_mvt_supply_order", "supply_order_id"),
        Index("idx_epicerie_mvt_transfer", "transfer_id"),
        Index("idx_epicerie_mvt_etl_import", "etl_import_id"),
        Index("idx_epicerie_mvt_created_by", "created_by_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EpicerieStockMovement id={self.id} type={self.type!r} "
            f"produit_id={self.produit_id} quantite={self.quantite}>"
        )
