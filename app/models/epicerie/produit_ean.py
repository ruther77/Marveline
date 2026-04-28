"""Modele EpicerieProduitEan — Table pivot multi-EAN pour produits epicerie.

Un produit epicerie peut avoir plusieurs EAN (fournisseurs differents).
Le champ EpicerieProduit.ean reste le EAN principal (backward compat).
Cette table stocke les EAN secondaires (alias cross-fournisseur).

Le scan caisse cherche dans EpicerieProduit.ean d'abord, puis ici.

Contrainte UNIQUE (tenant_id, ean) : un EAN ne peut appartenir qu'a un produit.
"""
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class EpicerieProduitEan(Base, TenantMixin, TimestampMixin):
    """EAN secondaire d'un produit epicerie (alias cross-fournisseur)."""

    __tablename__ = "epicerie_produit_eans"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK produit epicerie proprietaire de cet EAN"
    )
    ean: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Code EAN-13/EAN-8 secondaire"
    )
    source_fournisseur: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Fournisseur d'origine de cet EAN (ex: METRO, TAIYAT)"
    )
    # tenant_id herite de TenantMixin
    # created_at / updated_at herites de TimestampMixin

    __table_args__ = (
        Index("uq_epicerie_produit_ean_tenant", "tenant_id", "ean", unique=True),
        Index("idx_epicerie_produit_ean_produit", "produit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EpicerieProduitEan id={self.id} produit_id={self.produit_id} "
            f"ean={self.ean!r} source={self.source_fournisseur!r}>"
        )
