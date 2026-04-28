"""Modèle Product - Catalogue de vaisselle et accessoires louables."""
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
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
    price_per_day_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Prix location par jour en centimes (250 = 2.50€)"
    )

    deposit_amount_cents: Mapped[int] = mapped_column(
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

    # Tarification complémentaire
    cleaning_fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Frais de nettoyage en centimes (0 = inclus dans le prix, règle marveline.fr)"
    )

    # Poids / Volume
    weight_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Poids unitaire en grammes (NULL = non renseigné)"
    )

    volume_cm3: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Volume unitaire en cm³ (NULL = non renseigné)"
    )

    # Fournisseur (optionnel)
    supplier_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK optionnelle vers le fournisseur principal du produit"
    )

    # Descriptions
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description longue du produit"
    )

    short_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Description courte (utilisée dans les bundles et listes)"
    )

    # TVA
    tva_rate: Mapped[float] = mapped_column(
        nullable=False,
        default=0.20,
        comment="Taux TVA appliqué à ce produit (ex: 0.20 = 20%)"
    )

    # Contraintes de réservation
    requires_advance_booking_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Délai minimum de réservation en jours (90 pour nappages, 0 sinon)"
    )

    # Relations
    reservation_lines: Mapped[list["ReservationLine"]] = relationship(
        "ReservationLine",
        back_populates="product"
    )

    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    stock_items: Mapped[list["StockItem"]] = relationship(
        "StockItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    maintenances: Mapped[list["ProductMaintenance"]] = relationship(
        "ProductMaintenance",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
    )

    images: Mapped[list["ProductImage"]] = relationship(  # type: ignore[name-defined]
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="ProductImage.sort_order",
    )

    # Contraintes
    __table_args__ = (
        # SKU unique par tenant
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
        # Nom unique par tenant
        UniqueConstraint("tenant_id", "name", name="uq_product_tenant_name"),
        # Catégorie valide (20 catégories catalogue Marveline)
        CheckConstraint(
            "category IN ("
            "'accessoires_transport', 'assiettes', 'bancs', 'candy_bar', "
            "'chaises', 'couverts', 'decorations', 'housses', 'machines', "
            "'mange_debout', 'mobilier', 'nappages', 'nappes', 'porcelaine', "
            "'serviettes', 'tables', 'vaisselle', 'vaisselle_service', "
            "'vaisselle_enfants', 'verres')",
            name="check_product_category_valid"
        ),
        # Prix positif
        CheckConstraint(
            "price_per_day_cents >= 0",
            name="check_product_price_positive"
        ),
        # Caution positive
        CheckConstraint(
            "deposit_amount_cents >= 0",
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
        # Frais nettoyage positif
        CheckConstraint(
            "cleaning_fee_cents >= 0",
            name="check_product_cleaning_fee_positive"
        ),
        # Délai réservation positif
        CheckConstraint(
            "requires_advance_booking_days >= 0",
            name="check_product_advance_booking_positive"
        ),
        # Poids positif
        CheckConstraint(
            "weight_grams IS NULL OR weight_grams >= 0",
            name="check_product_weight_grams_positive"
        ),
        # Volume positif
        CheckConstraint(
            "volume_cm3 IS NULL OR volume_cm3 >= 0",
            name="check_product_volume_cm3_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"
