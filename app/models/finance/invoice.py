"""Modèle FinanceInvoice — Factures finance multi-usage.

Couvre 5 usages via champ `type` :
  - FOURNISSEUR                : facture d'achat (supply order livré)
  - CLIENT                     : facture de vente POS (encaissement épicerie)
  - INTERNE                    : facture de transfert interne épicerie → restaurant
  - RESTAURANT_TICKET          : ticket restaurant individuel (temps réel, cloturer)
  - RESTAURANT_DAILY_AGGREGATE : agrégat journalier des tickets (job Celery 23:59)

Numérotation :
  - FAC/CLI/INT : FAC-YYYYMMDD-NNNN (séquentiel journalier, par tenant)
  - Ticket      : TICKET-YYYYMMDD-NNNN
  - Agrégat     : JOUR-YYYYMMDD

Hiérarchie : les `RESTAURANT_TICKET` référencent leur `RESTAURANT_DAILY_AGGREGATE`
via `parent_invoice_id` (FK self, ON DELETE SET NULL).

ADR-06-BIS : TVA 20% par défaut (taux_tva = 2000 centièmes de pourcent).
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin

TYPES_INVOICE = (
    'FOURNISSEUR', 'CLIENT', 'INTERNE',
    'RESTAURANT_TICKET', 'RESTAURANT_DAILY_AGGREGATE',
)
STATUTS_INVOICE = ('EN_ATTENTE', 'PAYEE', 'EN_RETARD', 'ANNULEE')


class FinanceInvoice(Base, TenantMixin, TimestampMixin):
    """Facture finance multi-usage.

    Pas de SoftDeleteMixin : les factures sont conservées pour la comptabilité.
    Les factures annulées ont statut=ANNULEE.
    """

    __tablename__ = "finance_invoices"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Type : FOURNISSEUR | CLIENT | INTERNE"
    )
    numero: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Numéro de facture (FAC-YYYYMMDD-NNNN)"
    )
    date_facture: Mapped[object] = mapped_column(
        Date, nullable=False,
        comment="Date d'émission de la facture"
    )
    date_echeance: Mapped[Optional[object]] = mapped_column(
        Date, nullable=True,
        comment="Date d'échéance de paiement (null pour factures CLIENT immédiates)"
    )
    montant_ht: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant HT en centimes"
    )
    montant_tva: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant TVA en centimes"
    )
    montant_ttc: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Montant TTC en centimes"
    )
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default="EN_ATTENTE",
        comment="Statut : EN_ATTENTE | PAYEE | EN_RETARD | ANNULEE"
    )
    # Relations contextuelles (au plus une non-null selon le type)
    vendor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        # FK dynamique — définie dans la migration
        nullable=True,
        comment="FK finance_vendors — renseigné pour type=FOURNISSEUR"
    )
    supply_order_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK epicerie_supply_orders — renseigné pour type=FOURNISSEUR"
    )
    vente_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK epicerie_ventes — renseigné pour type=CLIENT"
    )
    transfer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK internal_transfers — renseigné pour type=INTERNE"
    )
    etl_import_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK etl_imports — renseigné pour factures créées via ETL pipeline"
    )
    commande_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="FK restaurant_commandes — renseigné pour type=RESTAURANT_TICKET"
    )
    parent_invoice_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK self — RESTAURANT_TICKET référence son RESTAURANT_DAILY_AGGREGATE"
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Référence libre (bon de commande, numéro externe)"
    )
    # tenant_id hérite de TenantMixin
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"type IN {TYPES_INVOICE}",
            name="check_finance_invoice_type_valide"
        ),
        CheckConstraint(
            f"statut IN {STATUTS_INVOICE}",
            name="check_finance_invoice_statut_valide"
        ),
        CheckConstraint(
            "montant_ht >= 0",
            name="check_finance_invoice_montant_ht_positif"
        ),
        CheckConstraint(
            "montant_ttc >= 0",
            name="check_finance_invoice_montant_ttc_positif"
        ),
        Index("idx_finance_invoice_tenant", "tenant_id"),
        Index("idx_finance_invoice_tenant_numero", "tenant_id", "numero", unique=True),
        Index("idx_finance_invoice_statut", "statut"),
        Index("idx_finance_invoice_vendor", "vendor_id"),
        Index("idx_finance_invoice_supply_order", "supply_order_id"),
        Index("idx_finance_invoice_vente", "vente_id"),
        Index("idx_finance_invoice_transfer", "transfer_id"),
        Index("idx_finance_invoice_etl_import", "etl_import_id"),
        Index("idx_finance_invoice_date", "date_facture"),
        Index("idx_finance_invoice_tenant_statut", "tenant_id", "statut"),
        # Phase 5c.1 — index agrégation restaurant (partial index créé par migration)
        Index("ix_finance_invoices_parent", "parent_invoice_id"),
        Index("ix_finance_invoices_type_date", "tenant_id", "type", "date_facture"),
        Index("idx_finance_invoice_commande", "commande_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<FinanceInvoice id={self.id} numero={self.numero!r} "
            f"type={self.type!r} statut={self.statut!r}>"
        )
