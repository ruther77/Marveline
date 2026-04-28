"""Modèles SupplyOrder et SupplyOrderLine — Commandes fournisseurs épicerie.

SupplyOrder : bon de commande envoyé à un fournisseur (FinanceVendor).
SupplyOrderLine : lignes détaillées de la commande.

Transitions statut :
  en_attente → confirmee → expediee → livree (immuable)
  {en_attente, confirmee} → annulee

Invariant réception : POST /recevoir atomique — MAJ received_quantity + mouvements ENTREE
  + incrémente epicerie_stock + statut=livree + crée FinanceInvoice.

Références :
    V2_API_EPICERIE.md §Commandes fournisseurs
    FC_EPICERIE_FOURNISSEURS.md §3 (transitions, invariant réception)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STATUTS_SUPPLY_ORDER = ('en_attente', 'confirmee', 'expediee', 'livree', 'annulee')
STOCK_PRECISION = 10
STOCK_SCALE = 3


class SupplyOrder(Base, TenantMixin, TimestampMixin):
    """Commande fournisseur épicerie.

    Pas de SoftDeleteMixin : les commandes annulées ont statut=annulee.
    """

    __tablename__ = "epicerie_supply_orders"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    vendor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_vendors.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers le fournisseur"
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Référence bon de commande (optionnelle)"
    )
    date_commande: Mapped[object] = mapped_column(
        Date, nullable=False,
        comment="Date de la commande"
    )
    date_livraison_prevue: Mapped[Optional[object]] = mapped_column(
        Date, nullable=True,
        comment="Date de livraison prévue"
    )
    date_livraison_reelle: Mapped[Optional[object]] = mapped_column(
        Date, nullable=True,
        comment="Date de livraison réelle (renseignée lors de la réception)"
    )
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default="en_attente",
        comment="Statut : en_attente | confirmee | expediee | livree | annulee"
    )
    montant_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Total HT en centimes"
    )
    montant_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Total TVA en centimes"
    )
    montant_ttc: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Total TTC en centimes"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Notes internes"
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK finance_invoices — créée lors du passage en statut=livree"
    )
    # tenant_id hérite de TenantMixin (= 2 pour épicerie)
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"statut IN {STATUTS_SUPPLY_ORDER}",
            name="check_supply_order_statut_valide"
        ),
        CheckConstraint(
            "montant_ttc >= 0",
            name="check_supply_order_montant_positif"
        ),
        Index("idx_supply_order_tenant", "tenant_id"),
        Index("idx_supply_order_vendor", "vendor_id"),
        Index("idx_supply_order_statut", "statut"),
        Index("idx_supply_order_date", "date_commande"),
        Index("idx_supply_order_invoice", "invoice_id"),
        Index("idx_supply_order_tenant_statut", "tenant_id", "statut"),
    )

    def __repr__(self) -> str:
        return (
            f"<SupplyOrder id={self.id} vendor_id={self.vendor_id} "
            f"statut={self.statut!r} montant_ttc={self.montant_ttc}>"
        )


class SupplyOrderLine(Base, TimestampMixin):
    """Ligne d'une commande fournisseur.

    Pas de TenantMixin : isolation via SupplyOrder (parent).
    """

    __tablename__ = "epicerie_supply_order_lines"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_supply_orders.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers la commande parente"
    )
    produit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK produit épicerie (null si produit non encore créé)"
    )
    designation: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Désignation de l'article commandé (copie au moment de la commande)"
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Quantité commandée"
    )
    prix_unitaire: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Prix unitaire HT en centimes"
    )
    taux_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=2000,
        comment="Taux TVA en centièmes de pourcent"
    )
    received_quantity: Mapped[Optional[float]] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=True,
        comment="Quantité réellement reçue (renseignée lors de la réception)"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Notes de ligne (ex: rupture partielle)"
    )
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="check_supply_line_quantity_positive"
        ),
        CheckConstraint(
            "prix_unitaire >= 0",
            name="check_supply_line_prix_positif"
        ),
        Index("idx_supply_line_order", "order_id"),
        Index("idx_supply_line_produit", "produit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SupplyOrderLine id={self.id} order_id={self.order_id} "
            f"designation={self.designation!r} quantity={self.quantity}>"
        )
