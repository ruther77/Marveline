"""Modèle MovementItemUnit — lien entre MovementItem et StockItem individuel."""
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.inventory_movement import MovementItem
    from app.models.movement_damage import InventoryMovementDamage
    from app.models.stock_item import StockItem


class MovementItemUnit(Base, TimestampMixin, TenantMixin):
    """Unité physique (StockItem) affectée à une ligne de mouvement.

    Permet le tracking individuel de chaque unité physique (par serial_number)
    tout au long du cycle départ / retour.

    Attributes:
        movement_item_id: FK vers movement_items.id
        stock_item_id: FK vers stock_items.id
        condition: État de cette unité au retour (nullable pendant le départ)
        condition_notes: Remarque libre sur cette unité
    """

    __tablename__ = "movement_item_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    movement_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("movement_items.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK ligne de mouvement parente",
    )

    stock_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("stock_items.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK unité de stock physique",
    )

    status_before: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Statut StockItem avant la transition: available, reserved, on_location…",
    )

    status_after: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Statut StockItem après la transition: reserved, on_location, available, damaged…",
    )

    condition: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="État au retour: perfect, good, damaged, missing",
    )

    condition_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes sur l'état de cette unité",
    )

    damage_type_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("damage_types.id", ondelete="SET NULL"),
        nullable=True,
        comment="Type de dommage constaté au retour (FK damage_types)",
    )

    # Relations
    movement_item: Mapped["MovementItem"] = relationship(
        "MovementItem",
        back_populates="units",
    )

    stock_item: Mapped["StockItem"] = relationship(
        "StockItem",
        back_populates="movement_units",
    )

    damages: Mapped[list["InventoryMovementDamage"]] = relationship(
        "InventoryMovementDamage",
        back_populates="movement_item_unit",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_movement_item_unit_tenant_item", "tenant_id", "movement_item_id"),
        Index("ix_movement_item_unit_stock_item", "stock_item_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MovementItemUnit(id={self.id}, movement_item_id={self.movement_item_id}, "
            f"stock_item_id={self.stock_item_id}, condition={self.condition!r})>"
        )
