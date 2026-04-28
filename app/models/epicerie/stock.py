"""Modèle EpicerieStock — Stock courant par produit.

Une ligne par produit (ONE-TO-ONE avec EpicerieProduit).
`quantite` est mis à jour atomiquement à chaque mouvement.
Lecture directe en DB (ADR-14 : pas de Redis pour le stock).
"""
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3


class EpicerieStock(Base, TenantMixin):
    """Stock courant d'un produit épicerie.

    Pas de TimestampMixin complet : `updated_at` seul suffit pour savoir
    quand le stock a été mis à jour. `created_at` via server_default.
    Pas de SoftDeleteMixin : liée 1-1 avec EpicerieProduit.
    """

    __tablename__ = "epicerie_stock"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers le produit épicerie"
    )
    quantite: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False, default=0,
        comment="Quantité en stock (peut être 0 mais jamais < 0)"
    )
    seuil_alerte: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False, default=0,
        comment="Seuil déclenchant une alerte stock bas"
    )
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de création"
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Dernière mise à jour du stock"
    )
    # tenant_id hérite de TenantMixin (= 2 pour épicerie)

    __table_args__ = (
        CheckConstraint(
            "quantite >= 0",
            name="check_epicerie_stock_quantite_positive"
        ),
        CheckConstraint(
            "seuil_alerte >= 0",
            name="check_epicerie_stock_seuil_positif"
        ),
        Index("idx_epicerie_stock_tenant", "tenant_id"),
        Index("idx_epicerie_stock_produit", "produit_id"),
        Index("idx_epicerie_stock_tenant_produit", "tenant_id", "produit_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<EpicerieStock id={self.id} produit_id={self.produit_id} quantite={self.quantite}>"
