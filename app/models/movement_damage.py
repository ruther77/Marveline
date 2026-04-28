"""Modèle InventoryMovementDamage — dommage constaté lors du retour d'un article."""
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.damage_type import DamageType
    from app.models.invoice_charge import InvoiceCharge
    from app.models.movement_item_unit import MovementItemUnit


class InventoryMovementDamage(Base, TimestampMixin, TenantMixin):
    """Dommage constaté sur une unité physique lors du retour.

    Lié à une MovementItemUnit (unité de stock physique) et optionnellement
    à une InvoiceCharge auto-créée si fee_cents > 0.

    Attributes:
        movement_item_unit_id: FK vers movement_item_units.id
        damage_type_id: FK vers damage_types.id (nullable)
        description: Description textuelle du dommage
        fee_cents: Coût estimé en centimes
        photo_urls: Liste d'URLs photos (JSON array)
        invoice_charge_id: FK vers invoice_charges.id (nullable — auto-créé si fee > 0)
    """

    __tablename__ = "inventory_movement_damages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    movement_item_unit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("movement_item_units.id", ondelete="CASCADE"),
        nullable=False,
        comment="Unité de stock physique concernée",
    )

    damage_type_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("damage_types.id", ondelete="SET NULL"),
        nullable=True,
        comment="Type de dommage (FK damage_types)",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description du dommage constaté",
    )

    fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Coût estimé en centimes (0 = à évaluer)",
    )

    photo_urls: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="URLs des photos du dommage (JSON array)",
    )

    invoice_charge_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("invoice_charges.id", ondelete="SET NULL"),
        nullable=True,
        comment="InvoiceCharge auto-créée pour facturation (nullable)",
    )

    # Relations
    movement_item_unit: Mapped["MovementItemUnit"] = relationship(
        "MovementItemUnit",
        back_populates="damages",
    )

    damage_type: Mapped[Optional["DamageType"]] = relationship(
        "DamageType",
    )

    invoice_charge: Mapped[Optional["InvoiceCharge"]] = relationship(
        "InvoiceCharge",
    )

    __table_args__ = (
        Index("ix_inv_movement_damage_tenant_unit", "tenant_id", "movement_item_unit_id"),
        CheckConstraint("fee_cents >= 0", name="check_inv_movement_damage_fee_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryMovementDamage(id={self.id}, unit_id={self.movement_item_unit_id}, "
            f"fee_cents={self.fee_cents})>"
        )
