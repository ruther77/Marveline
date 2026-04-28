"""Modèle EpicerieProduit — Catalogue produits épicerie.

Produits vendus et stockés dans l'épicerie (tenant_id=2).
Lié optionnellement à un fournisseur FinanceVendor et à une catégorie.

Le champ `ean` est indexé mais nullable (certains produits n'ont pas de code-barre).
Prix en centimes (ADR BigInteger).
"""
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STOCK_PRECISION = 10
STOCK_SCALE = 3


class EpicerieProduit(Base, TenantMixin, TimestampMixin):
    """Produit du catalogue épicerie."""

    __tablename__ = "epicerie_produits"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ean: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Code EAN-13/EAN-8 (null si absent)"
    )
    designation_clean: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Désignation normalisée (majuscules, sans accents)"
    )
    nom_court: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Nom court affiché en caisse (optionnel)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Description longue du produit"
    )
    categorie: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Catégorie libre (ex: Épicerie sèche, Boissons, Hygiène)"
    )
    unite_vente: Mapped[str] = mapped_column(
        String(10), nullable=False, default="U",
        comment="Unité de vente affichée en caisse : U (pièce) | KG | L | etc."
    )
    unite_base: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Unité physique réelle ('piece', 'kg', 'L', 'g', 'cL', 'mL', 'colis'). "
                "Distincte de unite_vente. Ex: unite_vente=U, colisage=150, "
                "unite_base=piece → 1 U contient 150 pièces."
    )
    colisage: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Nombre d'unité_base par unité_vente. Propagé depuis "
                "catalogue_produits.colisage au sync. NULL si inconnu."
    )
    volume_unitaire_ml: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Volume unitaire en mL (750 pour 75cL, 1000 pour 1L). "
                "Propagé depuis catalogue_produits.volume_unitaire_ml au sync."
    )
    prix_achat_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Prix d'achat HT en centimes (facture fournisseur)"
    )
    prix_unitaire_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Prix de vente TTC en centimes (= achat × (1+marge) × (1+TVA))"
    )
    taux_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=2000,
        comment="Taux TVA en centièmes de pourcent (2000 = 20%, 550 = 5.5%)"
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_vendors.id", ondelete="SET NULL"),
        nullable=True,
        comment="Fournisseur principal (optionnel)"
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Chemin relatif image produit. Ex: 'products/epicerie/42.jpg'"
    )
    actif: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="Produit actif (False = archivé)"
    )
    # tenant_id hérite de TenantMixin (= 2 pour épicerie)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        Index("idx_epicerie_produit_tenant", "tenant_id"),
        Index("idx_epicerie_produit_ean", "tenant_id", "ean"),
        Index("idx_epicerie_produit_vendor", "vendor_id"),
        Index("idx_epicerie_produit_categorie", "categorie"),
        Index("idx_epicerie_produit_actif", "tenant_id", "actif"),
    )

    def __repr__(self) -> str:
        return (
            f"<EpicerieProduit id={self.id} ean={self.ean!r} "
            f"designation={self.designation_clean!r}>"
        )
