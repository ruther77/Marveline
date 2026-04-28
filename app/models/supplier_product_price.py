"""Modele SupplierProductPrice — Prix d'achat de reference par fournisseur x produit."""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, UniqueConstraint, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class SupplierProductPrice(Base, TenantMixin):
    """Prix d'achat de reference pour un produit chez un fournisseur.

    Mis a jour automatiquement a chaque commande fournisseur.
    Sert de pre-remplissage pour les prochaines commandes.

    Attributes:
        supplier_id: FK fournisseur
        product_id: FK produit
        variant_id: FK variante (optionnel, NULL = produit entier)
        cost_price_cents: Dernier prix d'achat connu en centimes HT
        last_order_date: Date de la derniere commande avec ce prix
    """

    __tablename__ = "supplier_product_prices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
    )

    cost_price_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Prix d'achat HT en centimes",
    )

    last_order_date: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Date de la derniere commande",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "supplier_id", "product_id", "variant_id",
            name="uq_supplier_product_price_tenant_supplier_product_variant",
        ),
        Index("ix_spp_tenant_supplier", "tenant_id", "supplier_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SupplierProductPrice(supplier={self.supplier_id}, "
            f"product={self.product_id}, cost={self.cost_price_cents})>"
        )
