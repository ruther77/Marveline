"""Modèle EpiceriePrixHistorique — Historique des changements de prix.

Chaque ligne trace un changement de prix (achat ou vente) sur un produit.
Permet de visualiser l'évolution des prix dans le temps.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class EpiceriePrixHistorique(Base, TenantMixin):
    """Historique de prix d'un produit épicerie."""

    __tablename__ = "epicerie_prix_historique"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="CASCADE"),
        nullable=False,
    )
    prix_achat_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Prix achat HT centimes au moment du changement",
    )
    prix_vente_cts: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Prix vente TTC centimes au moment du changement",
    )
    taux_marge_centieme: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Marge appliquée (centièmes %)",
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="etl",
        comment="etl | manual | recalcul",
    )
    source_fournisseur: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Code fournisseur (METRO, TAIYAT, ETHAN, EUROCIEL, ...)",
    )
    etl_import_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("etl_imports.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK vers etl_imports.id (nullable : entrées manuelles sans import)",
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Ref facture ou note libre",
    )
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True,
        comment="Date à laquelle le prix s'applique (date facture ETL, "
                "ou date saisie pour entrée manuelle). NULL = retomber sur created_at.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()",
    )

    __table_args__ = (
        Index("idx_prix_hist_produit", "tenant_id", "produit_id"),
        Index("idx_prix_hist_date", "created_at"),
        Index("idx_prix_hist_effective", "tenant_id", "produit_id", "effective_date"),
        Index("idx_prix_hist_etl_import", "etl_import_id"),
    )
