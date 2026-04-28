"""Modèle CatalogueProduitEan — multi-EAN pour un même produit logique.

Un produit peut avoir plusieurs EANs selon le pays d'origine ou le packaging
régional (ex: Coca Cola 33cL FR vs DE). Ces EANs pointent tous sur le même
CatalogueProduit (principal).

Le CatalogueProduit.ean reste le EAN principal (backward compat). Cette table
stocke les EANs additionnels.

Contrainte UNIQUE globale sur `ean` : un EAN ne peut appartenir qu'à un produit
catalogue (cohérence cross-tenant du référentiel).
"""
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CatalogueProduitEan(Base, TimestampMixin):
    """EAN secondaire d'un produit catalogue (alias cross-pays)."""

    __tablename__ = "catalogue_produit_eans"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    catalogue_produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("catalogue_produits.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK produit catalogue propriétaire",
    )
    ean: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="EAN secondaire (cross-pays, cross-packaging)",
    )
    source_fournisseur: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Fournisseur d'origine de cet EAN (METRO, TAIYAT, etc.)",
    )

    __table_args__ = (
        Index("ix_catalogue_produit_eans_produit", "catalogue_produit_id"),
        Index("uq_catalogue_produit_eans_ean", "ean", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<CatalogueProduitEan id={self.id} "
            f"produit_id={self.catalogue_produit_id} ean={self.ean!r}>"
        )
