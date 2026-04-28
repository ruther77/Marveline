"""Modèles InventoryMovement et MovementItem — Mouvements de stock."""
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import (
    DeliveryMethod,
    InspectionStatus,
    ItemCondition,
    MovementStatus,
    MovementType,
)
from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.reservation import Reservation
    from app.models.product_variant import ProductVariant
    from app.models.product import Product
    from app.models.movement_item_unit import MovementItemUnit


class InventoryMovement(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Mouvement de stock (départ ou retour de matériel).

    Attributes:
        event_id: Référence événement (nullable, pas de FK — table events inexistante)
        movement_type: departure ou return
        scheduled_date: Date planifiée du mouvement
        actual_date: Date effective (remplie à la complétion)
        status: scheduled, in_transit, completed, late, cancelled
        delivery_method: delivery, pickup, shipping (nullable)
        delivery_address: Adresse de livraison (nullable)
        delivery_notes: Notes livraison (nullable)
        handled_by_user_id: Utilisateur responsable (FK users.id, nullable)
        inspection_status: Statut inspection retour (nullable)
        inspection_notes: Notes inspection (nullable)
        damage_fee: Frais de dommage en centimes (0 par défaut)
    """

    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    event_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Référence événement (pas de FK)",
    )

    reservation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK réservation liée (nullable)",
    )

    movement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type: departure ou return",
    )

    scheduled_date: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Date planifiée du mouvement",
    )

    actual_date: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date effective du mouvement",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MovementStatus.SCHEDULED.value,
        comment="Statut: scheduled, in_transit, completed, late, cancelled",
    )

    delivery_method: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Méthode: delivery, pickup, shipping",
    )

    delivery_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Adresse de livraison",
    )

    delivery_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes de livraison",
    )

    handled_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("accounts.id"),
        nullable=True,
        comment="Utilisateur responsable du mouvement",
    )

    inspection_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Statut inspection: pending, ok, damaged, missing",
    )

    inspection_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes d'inspection",
    )

    damage_fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Frais de dommage en centimes (0 = aucun)",
    )

    # Relations
    items: Mapped[list["MovementItem"]] = relationship(
        "MovementItem",
        back_populates="movement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reservation: Mapped[Optional["Reservation"]] = relationship(
        "Reservation",
        back_populates="movements",
        foreign_keys=[reservation_id],
    )

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('departure', 'return')",
            name="check_movement_type_valid",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'in_transit', 'completed', 'late', 'cancelled')",
            name="check_movement_status_valid",
        ),
        CheckConstraint(
            "delivery_method IS NULL OR delivery_method IN ('delivery', 'pickup', 'shipping')",
            name="check_delivery_method_valid",
        ),
        CheckConstraint(
            "inspection_status IS NULL OR inspection_status IN ('pending', 'ok', 'damaged', 'missing')",
            name="check_inspection_status_valid",
        ),
        CheckConstraint(
            "damage_fee_cents >= 0",
            name="check_damage_fee_positive",
        ),
        Index("ix_inventory_movement_tenant_status", "tenant_id", "status"),
        Index("ix_inventory_movement_tenant_event", "tenant_id", "event_id"),
        Index("ix_inventory_movement_scheduled_date", "tenant_id", "scheduled_date"),
        Index("ix_inventory_movement_reservation", "tenant_id", "reservation_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryMovement(id={self.id}, type='{self.movement_type}', "
            f"status='{self.status}')>"
        )


class MovementItem(Base, TimestampMixin, TenantMixin):
    """Article dans un mouvement de stock.

    Attributes:
        movement_id: FK vers inventory_movements.id
        event_item_id: Référence ligne événement (nullable, pas de FK)
        product_id: FK vers products.id (nullable)
        variant_id: FK vers product_variants.id (nullable si produit sans variantes)
        quantity_expected: Quantité prévue
        quantity_actual: Quantité effective (remplie au retour/complétion)
        condition: État de l'article (nullable)
        condition_notes: Notes sur l'état (nullable)
    """

    __tablename__ = "movement_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    movement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("inventory_movements.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK mouvement parent",
    )

    event_item_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Référence ligne événement (pas de FK)",
    )

    product_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("products.id"),
        nullable=True,
        comment="FK produit",
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        comment="FK variante couleur du produit",
    )

    quantity_expected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Quantité prévue",
    )

    quantity_actual: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Quantité effective (remplie à la complétion)",
    )

    condition: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="État: perfect, good, damaged, missing",
    )

    condition_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes sur l'état de l'article",
    )

    # Relations
    movement: Mapped["InventoryMovement"] = relationship(
        "InventoryMovement",
        back_populates="items",
    )

    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant",
        foreign_keys=[variant_id],
    )

    product: Mapped[Optional["Product"]] = relationship(
        "Product",
        foreign_keys=[product_id],
    )

    units: Mapped[List["MovementItemUnit"]] = relationship(
        "MovementItemUnit",
        back_populates="movement_item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity_expected > 0",
            name="check_item_quantity_expected_positive",
        ),
        CheckConstraint(
            "quantity_actual IS NULL OR quantity_actual >= 0",
            name="check_item_quantity_actual_valid",
        ),
        CheckConstraint(
            "condition IS NULL OR condition IN ('perfect', 'good', 'damaged', 'missing')",
            name="check_item_condition_valid",
        ),
        Index("ix_movement_item_tenant_movement", "tenant_id", "movement_id"),
        Index("ix_movement_item_product", "product_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MovementItem(id={self.id}, movement_id={self.movement_id}, "
            f"product_id={self.product_id}, qty={self.quantity_expected})>"
        )
