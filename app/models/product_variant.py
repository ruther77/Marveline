"""Modèle ProductVariant — variantes multi-dimensions de produits Marveline."""
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class ProductVariant(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Variante multi-dimensions d'un produit (couleur, taille, gamme).

    Chaque variante appartient à un produit parent et possède son propre stock.
    Le label est obligatoire et constitue la clé d'unicité par produit.
    Au moins une dimension (color, size, gamme) doit être renseignée.

    Attributes:
        product_id: ID du produit parent
        color: Couleur optionnelle (ex: "ivoire", "blanc")
        size: Taille/format optionnel (ex: "21cm", "240cm")
        gamme: Gamme/finition optionnelle (ex: "classique", "elegance")
        label: Label affiché obligatoire — clé d'unicité par produit
        price_per_day: Override prix en centimes (NULL = hérite du produit parent)
        sku: SKU unique de la variante
        stock_quantity: Stock total de cette variante
        available_quantity: Quantité disponible à la location
    """

    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Produit parent",
    )

    color: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Couleur de la variante (ex: ivoire, bordeaux)",
    )

    size: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Taille/format (ex: 21cm, 240cm)",
    )

    gamme: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Gamme/finition (ex: classique, elegance)",
    )

    label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Label affiché — clé d'unicité par produit",
    )

    price_per_day_cents: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Override prix parent en centimes (NULL = hérite parent)",
    )

    sku: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="SKU unique de la variante par tenant",
    )

    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Quantité totale en stock",
    )

    available_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Quantité disponible à la location",
    )

    deposit_amount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Montant caution par unité en centimes (500 = 5€)",
    )

    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Override image URL de la variante (NULL = hérite parent)",
    )

    weight_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Override poids unitaire en grammes (NULL = hérite parent)",
    )

    volume_cm3: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Override volume unitaire en cm³ (NULL = hérite parent)",
    )

    # Relation vers le produit parent
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="variants",
    )

    __table_args__ = (
        # SKU unique par tenant
        UniqueConstraint("tenant_id", "sku", name="uq_product_variant_tenant_sku"),
        # Un seul label par produit par tenant
        Index(
            "uq_product_variant_tenant_product_label",
            "tenant_id", "product_id", "label",
            unique=True,
        ),
        # Stock cohérent
        CheckConstraint(
            "available_quantity <= stock_quantity",
            name="check_variant_available_lte_stock",
        ),
        # Stock positif
        CheckConstraint(
            "stock_quantity >= 0",
            name="check_variant_stock_positive",
        ),
        # Prix override positif si fourni
        CheckConstraint(
            "price_per_day_cents IS NULL OR price_per_day_cents >= 0",
            name="check_variant_price_per_day_positive",
        ),
        # Poids override positif si fourni
        CheckConstraint(
            "weight_grams IS NULL OR weight_grams >= 0",
            name="check_variant_weight_grams_positive",
        ),
        # Volume override positif si fourni
        CheckConstraint(
            "volume_cm3 IS NULL OR volume_cm3 >= 0",
            name="check_variant_volume_cm3_positive",
        ),
    )
