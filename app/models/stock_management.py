"""Modèles StockInventaireSession + StockAdjustment — Gestion physique du stock."""
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class StockInventaireSession(Base, TenantMixin):
    """Session d'inventaire physique (comptage complet du stock).

    Attributes:
        status: in_progress | completed
        started_at: Début de la session
        completed_at: Fin de la session (NULL si en cours)
        created_by: ID utilisateur qui a lancé l'inventaire
        variances_json: { product_id: {expected, counted, delta} }
    """

    __tablename__ = "stock_inventaire_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="in_progress",
        comment="Statut de la session : in_progress | completed",
    )

    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="Horodatage de début",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Horodatage de fin (NULL si en cours)",
    )

    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Utilisateur ayant lancé l'inventaire",
    )

    variances_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Variances par produit : {product_id: {expected, counted, delta}}",
    )

    def __repr__(self) -> str:
        return f"<StockInventaireSession(id={self.id}, status='{self.status}')>"


class StockAdjustment(Base, TenantMixin):
    """Ajustement manuel du stock (correction, casse, retour fournisseur…).

    Attributes:
        product_id: Produit concerné
        delta: Variation (positif = entrée, négatif = sortie)
        reason: Motif obligatoire (audit)
        created_at: Horodatage
        created_by: Utilisateur auteur de l'ajustement
    """

    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Produit concerné par l'ajustement",
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Variante concernée (NULL = ajustement produit global)",
    )

    delta: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Variation de stock (positif = entrée, négatif = sortie)",
    )

    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Motif de l'ajustement (obligatoire pour audit)",
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="Horodatage de création",
    )

    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Utilisateur auteur de l'ajustement",
    )

    def __repr__(self) -> str:
        return f"<StockAdjustment(id={self.id}, product_id={self.product_id}, delta={self.delta})>"
