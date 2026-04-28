"""Modèles EpicerieVente et EpicerieVenteLigne — Ventes POS épicerie.

EpicerieVente : ticket de caisse avec statut (EN_COURS | VALIDEE | ANNULEE | REMBOURSEE)
EpicerieVenteLigne : lignes détaillées avec quantité, prix, TVA, remise

Numérotation ticket : VTE-YYYYMMDD-NNNN (séquentiel journalier).
Invariant POS : `POST /encaisser` atomique — crée vente + lignes + mouvements stock.

ADR BigInteger : tous les montants en centimes.
ADR-06-BIS : TVA 20% par défaut (taux_tva = 2000).
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STATUTS_VENTE = ('EN_COURS', 'VALIDEE', 'ANNULEE', 'REMBOURSEE')
MODES_PAIEMENT = ('ESPECES', 'CB', 'MIXTE', 'CHEQUE', 'VIREMENT')
STOCK_PRECISION = 10
STOCK_SCALE = 3


class EpicerieVente(Base, TenantMixin, TimestampMixin):
    """Ticket de caisse épicerie.

    Pas de SoftDeleteMixin : les ventes annulées ont statut=ANNULEE.
    """

    __tablename__ = "epicerie_ventes"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    numero_ticket: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Numéro ticket (VTE-YYYYMMDD-NNNN)"
    )
    date_vente: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="Date et heure de la vente"
    )
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default="EN_COURS",
        comment="Statut : EN_COURS | VALIDEE | ANNULEE | REMBOURSEE"
    )
    mode_paiement: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Mode : ESPECES | CB | MIXTE | CHEQUE | VIREMENT"
    )
    # Montants globaux
    total_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Total HT en centimes avant remise"
    )
    total_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Total TVA en centimes"
    )
    total_ttc: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Total TTC en centimes après remise"
    )
    remise_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=0,
        comment="Remise globale en pourcent (0.00 à 100.00)"
    )
    remise_montant: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant remise en centimes"
    )
    # Paiement détaillé (pour mode MIXTE ou ESPECES avec rendu)
    montant_especes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant payé en espèces (centimes)"
    )
    montant_cb: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant payé par CB (centimes)"
    )
    montant_rendu: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Monnaie rendue en centimes"
    )
    # Client (optionnel)
    client_nom: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Nom du client (optionnel)"
    )
    client_email: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Email du client (pour reçu électronique)"
    )
    # Vendeur
    vendeur_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte du vendeur ayant encaissé"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Note libre"
    )
    # Facture générée (nullable car créée lors de l'encaissement)
    invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK finance_invoices — créée lors de VALIDEE"
    )
    # tenant_id hérite de TenantMixin (= 2 pour épicerie)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"statut IN {STATUTS_VENTE}",
            name="check_epicerie_vente_statut_valide"
        ),
        CheckConstraint(
            "total_ttc >= 0",
            name="check_epicerie_vente_total_positif"
        ),
        CheckConstraint(
            "remise_pct >= 0 AND remise_pct <= 100",
            name="check_epicerie_vente_remise_valide"
        ),
        Index("idx_epicerie_vente_tenant", "tenant_id"),
        Index("idx_epicerie_vente_tenant_numero", "tenant_id", "numero_ticket", unique=True),
        Index("idx_epicerie_vente_statut", "statut"),
        Index("idx_epicerie_vente_date", "date_vente"),
        Index("idx_epicerie_vente_vendeur", "vendeur_id"),
        Index("idx_epicerie_vente_invoice", "invoice_id"),
        Index("idx_epicerie_vente_tenant_date", "tenant_id", "date_vente"),
    )

    def __repr__(self) -> str:
        return (
            f"<EpicerieVente id={self.id} numero={self.numero_ticket!r} "
            f"statut={self.statut!r} total_ttc={self.total_ttc}>"
        )


class EpicerieVenteLigne(Base, TenantMixin, TimestampMixin):
    """Ligne détaillée d'une vente épicerie."""

    __tablename__ = "epicerie_vente_lignes"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    vente_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_ventes.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la vente parente"
    )
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers le produit vendu"
    )
    quantite: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Quantité vendue"
    )
    prix_unitaire_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Prix unitaire HT en centimes au moment de la vente"
    )
    taux_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=2000,
        comment="Taux TVA en centièmes de pourcent (2000 = 20%)"
    )
    montant_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Montant HT ligne en centimes"
    )
    montant_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Montant TVA ligne en centimes"
    )
    montant_ttc: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Montant TTC ligne en centimes"
    )
    remise_pct: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, default=0,
        comment="Remise ligne en pourcent"
    )
    # tenant_id hérite de TenantMixin
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "quantite > 0",
            name="check_epicerie_ligne_quantite_positive"
        ),
        CheckConstraint(
            "montant_ttc >= 0",
            name="check_epicerie_ligne_montant_positif"
        ),
        CheckConstraint(
            "remise_pct >= 0 AND remise_pct <= 100",
            name="check_epicerie_ligne_remise_valide"
        ),
        Index("idx_epicerie_vligne_tenant", "tenant_id"),
        Index("idx_epicerie_vligne_vente", "vente_id"),
        Index("idx_epicerie_vligne_produit", "produit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<EpicerieVenteLigne id={self.id} vente_id={self.vente_id} "
            f"produit_id={self.produit_id} quantite={self.quantite}>"
        )
