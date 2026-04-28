"""Modèle StockItem - Tracking individuel des unités physiques en stock."""
from typing import TYPE_CHECKING, Optional
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.movement_item_unit import MovementItemUnit
    from app.models.product_variant import ProductVariant


class StockItem(Base, TimestampMixin, TenantMixin):
    """Unité physique individuelle d'un produit louable.

    Attributes:
        product_id: Produit auquel appartient cette unité
        serial_number: Numéro de série optionnel (ex: "TABLE-042")
        status: État courant de l'unité
            - 'available'   : disponible à la location
            - 'reserved'    : réservé (réservation confirmée, pas encore livré)
            - 'on_location' : actuellement chez le client
            - 'damaged'     : endommagé, hors service temporairement
            - 'in_repair'   : en réparation
            - 'retired'     : mis au rebut définitif
        current_reservation_id: Réservation en cours (si reserved/on_location)
        notes: Notes libres sur l'unité

    Transitions valides :
        available   → reserved      (reservation.confirm())
        reserved    → on_location   (InventoryMovement DELIVERY complété)
        on_location → available     (InventoryMovement RETURN — article OK)
        on_location → damaged       (InventoryMovement RETURN — article cassé)
        damaged     → in_repair     (action manuelle)
        in_repair   → available     (action manuelle)
        any         → retired       (mise au rebut)
    """

    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Produit auquel appartient cette unité",
    )

    serial_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Numéro de série optionnel",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="available",
        comment="État courant : available|reserved|on_location|damaged|in_repair|retired",
    )

    current_reservation_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Réservation en cours (nullable)",
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Variante physique trackée (NULL = non encore assignée)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes libres sur l'unité",
    )

    # Relations
    product: Mapped["Product"] = relationship("Product", back_populates="stock_items")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")

    movement_units: Mapped[list["MovementItemUnit"]] = relationship(
        "MovementItemUnit",
        back_populates="stock_item",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('available','reserved','on_location','damaged','in_repair','retired')",
            name="check_stock_item_status_valid",
        ),
        # Index FK obligatoires
        Index("idx_stock_items_product_id", "product_id"),
        Index("idx_stock_items_reservation_id", "current_reservation_id"),
        Index("idx_stock_items_variant_id", "variant_id"),
    )

    def __repr__(self) -> str:
        return f"<StockItem(id={self.id}, product_id={self.product_id}, status='{self.status}')>"
