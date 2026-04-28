"""Modèle CatalogueProduitColisage — colisages observés par produit.

Un même produit logique (même marque + volume + unité + degré) peut être
livré en différents packs selon le fournisseur ou la référence interne
(ex: 1664 25cL existe en pack 18, 20, 24 chez METRO). Le colisage est un
attribut d'emballage, pas un critère de distinction du produit.

Cette table trace, pour chaque produit catalogue, les colisages rencontrés
dans les factures + quel fournisseur les propose, avec dates first/last seen.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CatalogueProduitColisage(Base):
    """Colisage observé pour un produit catalogue (pivot multi-valeurs)."""

    __tablename__ = "catalogue_produit_colisages"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    catalogue_produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("catalogue_produits.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK produit catalogue propriétaire",
    )
    colisage: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Nombre d'unités par pack (ex: 18, 20, 24)",
    )
    source_fournisseur: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Fournisseur observé (METRO, TAIYAT, ...). NULL = inconnu.",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="Premier import où ce colisage a été vu",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="Dernier import où ce colisage a été vu",
    )

    __table_args__ = (
        UniqueConstraint(
            "catalogue_produit_id", "colisage", "source_fournisseur",
            name="uq_cat_prod_colisage_source",
        ),
        Index("ix_cat_prod_colisages_produit", "catalogue_produit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CatalogueProduitColisage id={self.id} "
            f"produit_id={self.catalogue_produit_id} "
            f"colisage={self.colisage} source={self.source_fournisseur!r}>"
        )
