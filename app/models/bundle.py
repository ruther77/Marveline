"""Modeles ProductBundle et BundleItem — Packs de produits."""
from typing import Optional
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class ProductBundle(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Pack de produits avec prix groupe.

    Attributes:
        name: Nom du bundle (ex: "Pack Mariage 100 personnes")
        slug: Slug URL-safe unique par tenant
        description: Description longue (optionnelle)
        short_description: Description courte pour les listes (500 chars max)
        bundle_price: Prix du bundle en centimes
        cleaning_fee: Frais de nettoyage en centimes
        featured: Mis en avant sur le site
        display_order: Ordre d'affichage (0 = defaut)
        image_url: URL de l'image du bundle
    """

    __tablename__ = "product_bundles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Nom du bundle"
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Slug URL-safe unique par tenant"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description longue du bundle"
    )

    short_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Description courte pour les listes"
    )

    bundle_price: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Prix du bundle en centimes (25000 = 250.00 EUR)"
    )

    cleaning_fee: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Frais de nettoyage en centimes"
    )

    featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Mis en avant sur le site"
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Ordre d'affichage"
    )

    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL de l'image du bundle"
    )

    # Relations
    items: Mapped[list["BundleItem"]] = relationship(
        "BundleItem",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="BundleItem.display_order",
    )

    # Contraintes
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_bundle_tenant_slug"),
        UniqueConstraint("tenant_id", "name", name="uq_bundle_tenant_name"),
        CheckConstraint("bundle_price >= 0", name="check_bundle_price_positive"),
        CheckConstraint("cleaning_fee >= 0", name="check_bundle_cleaning_fee_positive"),
        CheckConstraint("display_order >= 0", name="check_bundle_display_order"),
    )

    def __repr__(self) -> str:
        return f"<ProductBundle(id={self.id}, slug='{self.slug}', name='{self.name}')>"


class BundleItem(Base, TimestampMixin, TenantMixin):
    """Ligne de jointure bundle <-> produit.

    Pas de SoftDeleteMixin — suppression physique.
    Cascade "all, delete-orphan" depuis le bundle parent.

    Attributes:
        bundle_id: FK vers product_bundles.id
        product_id: FK vers products.id
        quantity: Quantite de ce produit dans le bundle
        display_order: Ordre d'affichage dans le bundle
    """

    __tablename__ = "bundle_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    bundle_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("product_bundles.id", name="fk_bundle_item_bundle"),
        nullable=False,
        index=True,
        comment="FK vers product_bundles"
    )

    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", name="fk_bundle_item_product"),
        nullable=False,
        index=True,
        comment="FK vers products"
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Quantite dans le bundle"
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Ordre d'affichage dans le bundle"
    )

    # Relations
    bundle: Mapped["ProductBundle"] = relationship(
        "ProductBundle",
        back_populates="items",
    )

    product: Mapped["Product"] = relationship("Product")

    # Contraintes
    __table_args__ = (
        UniqueConstraint("bundle_id", "product_id", name="uq_bundle_item_product"),
        CheckConstraint("quantity > 0", name="check_bundle_item_quantity_positive"),
        CheckConstraint("display_order >= 0", name="check_bundle_item_display_order"),
    )

    def __repr__(self) -> str:
        return f"<BundleItem(id={self.id}, bundle_id={self.bundle_id}, product_id={self.product_id}, qty={self.quantity})>"
