"""Modèles SupplierOrder — Commandes fournisseurs avec suivi de réception."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, Integer, JSON, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class SupplierOrder(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Commande fournisseur.

    Cycle de vie :
        draft → ordered → partially_received → fully_received | cancelled

    Attributes:
        supplier_id: FK vers suppliers
        reference: Numéro de commande (ex: CMD-2026-001)
        status: État courant de la commande
        order_date: Date de passage de commande
        expected_date: Date de livraison prévue
        notes: Notes libres
    """

    __tablename__ = "supplier_orders"

    __table_args__ = (
        # ix_supplier_orders_tenant_id est généré par TenantMixin (index=True sur tenant_id)
        Index("ix_supplier_orders_tenant_supplier", "tenant_id", "supplier_id"),
        Index("ix_supplier_orders_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK fournisseur",
    )

    reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Numéro de commande (ex: CMD-2026-001)",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="draft",
        comment="draft | ordered | partially_received | fully_received | cancelled",
    )

    order_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date de passage de commande",
    )

    expected_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date de livraison prévue",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes libres",
    )

    # Relations
    lines: Mapped[list["SupplierOrderLine"]] = relationship(
        "SupplierOrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )

    receipts: Mapped[list["SupplierOrderReceipt"]] = relationship(
        "SupplierOrderReceipt",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<SupplierOrder(id={self.id}, ref='{self.reference}', status='{self.status}')>"


class SupplierOrderLine(Base, TenantMixin):
    """Ligne d'une commande fournisseur.

    Attributes:
        order_id: FK vers supplier_orders
        product_id: FK vers products
        qty_ordered: Quantité commandée
        unit_cost_cents: Prix unitaire en centimes
        qty_received: Quantité déjà reçue (cumulée toutes réceptions)
    """

    __tablename__ = "supplier_order_lines"

    __table_args__ = (
        # ix_supplier_order_lines_tenant_id est généré par TenantMixin (index=True sur tenant_id)
        Index("ix_supplier_order_lines_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_orders.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK commande parente",
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK produit commandé",
    )

    qty_ordered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Quantité commandée",
    )

    unit_cost_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Prix unitaire HT en centimes",
    )

    qty_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Quantité reçue cumulée",
    )

    # Relations
    order: Mapped["SupplierOrder"] = relationship(
        "SupplierOrder",
        back_populates="lines",
    )
    product: Mapped[Optional["Product"]] = relationship("Product", lazy="joined")

    @property
    def product_name(self) -> Optional[str]:
        return self.product.name if self.product else None

    def __repr__(self) -> str:
        return (
            f"<SupplierOrderLine(id={self.id}, product_id={self.product_id}, "
            f"ordered={self.qty_ordered}, received={self.qty_received})>"
        )

    @property
    def qty_remaining(self) -> int:
        """Reliquat : quantité non encore reçue."""
        return self.qty_ordered - self.qty_received


class SupplierOrderReceipt(Base, TenantMixin):
    """Bon de réception partielle ou totale.

    Chaque réception déclenche des StockAdjustment pour chaque ligne reçue.

    Attributes:
        order_id: FK vers supplier_orders
        received_at: Horodatage de la réception
        received_by: Utilisateur qui a saisi la réception
        notes: Notes (ex: "emballage abîmé")
        lines_json: { line_id: qty_received } — snapshot des qtés reçues
    """

    __tablename__ = "supplier_order_receipts"

    __table_args__ = (
        # ix_supplier_order_receipts_tenant_id est généré par TenantMixin (index=True sur tenant_id)
        Index("ix_supplier_order_receipts_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_orders.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK commande parente",
    )

    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment="Horodatage de la réception",
    )

    received_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Utilisateur ayant saisi la réception",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes sur cette réception",
    )

    lines_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Snapshot { line_id: qty_received }",
    )

    # Relations
    order: Mapped["SupplierOrder"] = relationship(
        "SupplierOrder",
        back_populates="receipts",
    )

    receipt_lines: Mapped[list["SupplierOrderReceiptLine"]] = relationship(
        "SupplierOrderReceiptLine",
        back_populates="receipt",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<SupplierOrderReceipt(id={self.id}, order_id={self.order_id})>"


class SupplierOrderReceiptLine(Base, TimestampMixin, TenantMixin):
    """Ligne granulaire d'un bon de réception (Option B).

    Chaque ligne enregistre le détail de réception pour une ligne de commande :
    quantité reçue conforme, endommagée, manquante.

    Attributes:
        receipt_id: FK vers supplier_order_receipts
        order_line_id: FK vers supplier_order_lines
        product_id: Dénormalisation pour requêtes rapides
        qty_received: Quantité reçue conforme
        qty_damaged: Quantité reçue endommagée
        qty_missing: Quantité manquante
        damage_type_id: Type de dommage (nullable)
        notes: Note spécifique à cette ligne
    """

    __tablename__ = "supplier_order_receipt_lines"

    __table_args__ = (
        Index("ix_supplier_order_receipt_lines_receipt_id", "receipt_id"),
        Index("ix_supplier_order_receipt_lines_tenant_order", "tenant_id", "order_line_id"),
        CheckConstraint("qty_received >= 0", name="ck_receipt_line_qty_received_nn"),
        CheckConstraint("qty_damaged >= 0", name="ck_receipt_line_qty_damaged_nn"),
        CheckConstraint("qty_missing >= 0", name="ck_receipt_line_qty_missing_nn"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    receipt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_order_receipts.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK bon de réception parent",
    )

    order_line_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supplier_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK ligne de commande",
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK produit (dénormalisation pour requêtes directes)",
    )

    qty_received: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Quantité reçue conforme",
    )

    qty_damaged: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Quantité reçue endommagée",
    )

    qty_missing: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Quantité manquante / non livrée",
    )

    damage_type_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("damage_types.id", ondelete="SET NULL"),
        nullable=True,
        comment="Type de dommage (nullable)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Note spécifique à cette ligne de réception",
    )

    # Relations
    receipt: Mapped["SupplierOrderReceipt"] = relationship(
        "SupplierOrderReceipt",
        back_populates="receipt_lines",
    )
    product: Mapped[Optional["Product"]] = relationship("Product", lazy="joined")

    @property
    def product_name(self) -> Optional[str]:
        return self.product.name if self.product else None

    def __repr__(self) -> str:
        return (
            f"<SupplierOrderReceiptLine(id={self.id}, receipt_id={self.receipt_id}, "
            f"product_id={self.product_id}, rcvd={self.qty_received}, "
            f"dmg={self.qty_damaged}, miss={self.qty_missing})>"
        )
