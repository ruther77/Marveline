"""Modèle Product - Catalogue de vaisselle et accessoires louables."""
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin
from app.constants import ProductCondition


class Product(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Produit louable (vaisselle, accessoires).

    Attributes:
        name: Nom du produit (ex: "Assiette plate blanche 28cm")
        sku: Code produit unique (ex: "ASS-PLATE-28-WHI")
        category: Catégorie (assiette, verre, couvert, nappe, deco, autre)
        price_per_day: Prix location par jour en CENTIMES (250 = 2.50€/jour)
        deposit_amount: Montant caution par unité en CENTIMES (500 = 5€)
        stock_quantity: Quantité totale en stock
        available_quantity: Quantité disponible à la location (≤ stock_quantity)
        condition: État (neuf, bon, use, hors_service)
        image_url: URL de l'image du produit (optionnel)
    """

    __tablename__ = "products"

    # Clé primaire
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification produit
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Nom du produit"
    )

    sku: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Code produit unique (Stock Keeping Unit)"
    )

    # Catégorie
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Catégorie du produit"
    )

    # Tarification (en centimes)
    price_per_day: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Prix location par jour en centimes (250 = 2.50€)"
    )

    deposit_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant caution par unité en centimes (500 = 5€)"
    )

    # Gestion stock
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Quantité totale en stock"
    )

    available_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Quantité disponible à la location"
    )

    # État
    condition: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProductCondition.BON,
        comment="État du produit (neuf, bon, use, hors_service)"
    )

    # Média
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL de l'image du produit"
    )

    # Relations
    reservation_lines: Mapped[list["ReservationLine"]] = relationship(
        "ReservationLine",
        back_populates="product"
    )

    # Contraintes
    __table_args__ = (
        # SKU unique par tenant
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
        # Nom unique par tenant
        UniqueConstraint("tenant_id", "name", name="uq_product_tenant_name"),
        # Catégorie valide
        CheckConstraint(
            "category IN ('assiette', 'verre', 'couvert', 'nappe', 'deco', 'autre')",
            name="check_product_category_valid"
        ),
        # Prix positif
        CheckConstraint(
            "price_per_day >= 0",
            name="check_product_price_positive"
        ),
        # Caution positive
        CheckConstraint(
            "deposit_amount >= 0",
            name="check_product_deposit_positive"
        ),
        # Stock cohérent
        CheckConstraint(
            "available_quantity <= stock_quantity",
            name="check_product_available_lte_stock"
        ),
        # État valide
        CheckConstraint(
            "condition IN ('neuf', 'bon', 'use', 'hors_service')",
            name="check_product_condition_valid"
        ),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"
