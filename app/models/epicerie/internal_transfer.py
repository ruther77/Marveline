"""Modeles InternalTransfer et InternalTransferLine — Transferts internes epicerie -> restaurant.

InternalTransfer : bon de transfert entre tenants (epicerie = source, restaurant = dest).
InternalTransferLine : lignes detaillant les produits transferes.

Isolation multi-tenant via TenantMixin (tenant_id = epicerie source) + dest_tenant_id.

Statuts : PENDING -> VALIDATED (immuable) | CANCELLED

Invariant validation (atomique) :
  - Decremente stock epicerie (TRANSFERT_RESTAURANT)
  - Cree mouvement restaurant (transfert_entrant) via MouvementStockService
  - Cree FinanceInvoice INTERNE
  - Enregistre mouvements dans InternalTransferLine
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

STATUTS_TRANSFER = ('PENDING', 'VALIDATED', 'CANCELLED')
STOCK_PRECISION = 10
STOCK_SCALE = 3


class InternalTransfer(Base, TenantMixin, TimestampMixin):
    """Bon de transfert interne entre tenants.

    tenant_id (TenantMixin) = tenant source (epicerie).
    dest_tenant_id = tenant destinataire (restaurant).
    Pas de SoftDeleteMixin : les transferts annules ont statut=CANCELLED.
    """

    __tablename__ = "internal_transfers"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    dest_tenant_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
        comment="Tenant destinataire (restaurant)"
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Reference libre du transfert"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="Statut : PENDING | VALIDATED | CANCELLED"
    )
    montant_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant HT total en centimes"
    )
    montant_ttc: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant TTC total en centimes"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Notes internes"
    )
    invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK finance_invoices — creee lors de VALIDATED"
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant cree le transfert"
    )
    validated_at: Mapped[Optional[object]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date/heure de validation"
    )
    validated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant valide le transfert"
    )
    cancelled_at: Mapped[Optional[object]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date/heure d'annulation"
    )
    raison_annulation: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Raison de l'annulation"
    )
    # tenant_id herite de TenantMixin (epicerie source)
    # created_at / updated_at herites de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"status IN {STATUTS_TRANSFER}",
            name="check_internal_transfer_status_valide"
        ),
        CheckConstraint(
            "tenant_id != dest_tenant_id",
            name="check_internal_transfer_source_ne_dest"
        ),
        CheckConstraint(
            "montant_ttc >= 0",
            name="check_internal_transfer_montant_positif"
        ),
        Index("idx_transfer_tenant_status", "tenant_id", "status"),
        Index("idx_transfer_dest_tenant", "dest_tenant_id"),
        Index("idx_internal_transfer_status", "status"),
        Index("idx_internal_transfer_invoice", "invoice_id"),
        Index("idx_internal_transfer_created_by", "created_by"),
    )

    def __repr__(self) -> str:
        return (
            f"<InternalTransfer id={self.id} "
            f"tenant={self.tenant_id}->dest={self.dest_tenant_id} "
            f"status={self.status!r}>"
        )


class InternalTransferLine(Base, TimestampMixin):
    """Ligne d'un transfert interne — produit epicerie transfere."""

    __tablename__ = "internal_transfer_lines"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    transfer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("internal_transfers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK vers le transfert parent"
    )
    produit_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_produits.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK produit epicerie transfere (toujours requis)"
    )
    designation: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Snapshot designation produit au moment du transfert"
    )
    ingredient_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK ingredient restaurant (mapping optionnel)"
    )
    quantite: Mapped[float] = mapped_column(
        Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
        comment="Quantite transferee"
    )
    unite: Mapped[str] = mapped_column(
        String(10), nullable=False, default="U",
        comment="Unite de la quantite (U, KG, L, etc.)"
    )
    prix_unitaire: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Prix unitaire HT en centimes"
    )
    montant_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant HT ligne en centimes"
    )
    tva_pct: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=2000,
        comment="Taux TVA en centiemes de pourcent"
    )
    montant_ttc: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant TTC ligne en centimes"
    )
    mouvement_epicerie_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("epicerie_stock_movements.id", ondelete="SET NULL"),
        nullable=True,
        comment="Mouvement stock epicerie cree lors de VALIDATED"
    )
    mouvement_restaurant_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_mouvements_stock.id", ondelete="SET NULL"),
        nullable=True,
        comment="Mouvement stock restaurant cree lors de VALIDATED"
    )
    # created_at / updated_at herites de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            "quantite > 0",
            name="check_transfer_line_quantite_positive"
        ),
        CheckConstraint(
            "prix_unitaire >= 0",
            name="check_transfer_line_prix_positif"
        ),
        Index("idx_transfer_line_transfer", "transfer_id"),
        Index("idx_transfer_line_produit", "produit_id"),
        Index("idx_transfer_line_ingredient", "ingredient_id"),
        Index("idx_transfer_line_mvt_epicerie", "mouvement_epicerie_id"),
        Index("idx_transfer_line_mvt_resto", "mouvement_restaurant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<InternalTransferLine id={self.id} transfer_id={self.transfer_id} "
            f"produit_id={self.produit_id} quantite={self.quantite}>"
        )
