"""Modèle CatalogueProduit — Référentiel produits alimentaires partagé (M01).

Table sans tenant_id : référentiel ETL partagé entre épicerie (tenant_id=2)
et restaurant (tenant_id=3). Chaque fournisseur (METRO, TAIYAT…) alimente
ce catalogue via les parsers ETL (ADR-08).

Références :
    ADR-01  : catalogue sans tenant_id
    ADR-07  : déduplication Jaro-Winkler sur designation_norm
    §6.1    : schéma SQL validé
"""
from typing import Optional

from sqlalchemy import BigInteger, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CatalogueProduit(Base, TimestampMixin):
    """Entrée du catalogue alimentaire normalisé.

    Chaque ligne représente un produit unique identifié par son EAN (si présent)
    ou par sa désignation normalisée (déduplication Jaro-Winkler ADR-07).
    Pas de SoftDeleteMixin : le catalogue est un log ETL, on ne "supprime" pas
    une entrée — on crée un conflit si collision (table etl_conflicts).
    """

    __tablename__ = "catalogue_produits"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    ean: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Code EAN-8 ou EAN-13. NULL pour produits sans code-barres (maison, TAIYAT)"
    )
    designation: Mapped[str] = mapped_column(
        String(300), nullable=False,
        comment="Désignation telle que reçue du fournisseur. Sert à l'affichage."
    )
    designation_norm: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True,
        comment="Version normalisée (lowercase, sans accents, sans mots vides). "
                "Sert à la déduplication Jaro-Winkler (ADR-07)."
    )
    marque: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Marque commerciale. Ex: 'Président', 'Ricard'"
    )
    unite_base: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Unité de stockage. Ex: 'kg', 'L', 'piece', 'carton'"
    )
    conditionnement: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Description du conditionnement. Ex: '1 carton de 6 × 1L'"
    )
    volume_unitaire_ml: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Volume unitaire en mL (330 pour 33cL, 1500 pour 1.5L). "
                "Alimente le matching OFF (marque, volume) et l'ETL."
    )
    colisage: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Nombre d'unités de base par colis reçu. "
                "Ex: 150 (sucettes/sachet), 6 (bouteilles/carton). "
                "Extrait du libellé par le parser ETL (LigneParsee.colisage)."
    )
    source_fournisseur: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Code fournisseur source. Ex: 'METRO', 'TAIYAT', 'EUROCIEL'"
    )
    categorie_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="FK applicative vers categories_produit.code. NULL si catégorie inconnue à l'import."
    )
    prix_unitaire_cts: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Dernier prix unitaire HT en centimes (ADR-25). Mis à jour à chaque import."
    )
    taux_tva_centieme: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Taux TVA en centièmes (2000=20%, 550=5.5%). Déduit du code TVA fournisseur."
    )
    merged_into_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Si ce produit a été fusionné (conflit MERGED), pointe vers le produit cible."
    )
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        # UNIQUE partielle : deux produits sans EAN ne doivent pas se bloquer mutuellement
        Index(
            "uq_catalogue_ean",
            "ean",
            unique=True,
            postgresql_where=text("ean IS NOT NULL"),
        ),
        # Index de jointure vers categories_produit (ADR-05)
        Index("idx_catalogue_categorie", "categorie_code"),
        # Index pour la déduplication Jaro-Winkler (recherche fuzzy par fournisseur)
        Index("idx_catalogue_source", "source_fournisseur"),
    )

    def __repr__(self) -> str:
        return (
            f"<CatalogueProduit id={self.id} ean={self.ean!r} "
            f"designation={self.designation[:40]!r}>"
        )
