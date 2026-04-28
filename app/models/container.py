"""Modèles Container — contenants physiques et leur contenu persistant."""
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class Container(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Contenant physique (bac, carton, palette, housse, caisse).

    Chaque contenant a un type, des dimensions optionnelles,
    un numéro de série unique par tenant, et un statut de disponibilité.
    """

    __tablename__ = "containers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="Nom du contenant"
    )

    container_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Type : bac, carton, palette, housse, caisse"
    )

    length_cm: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Longueur en cm"
    )

    width_cm: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Largeur en cm"
    )

    height_cm: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Hauteur en cm"
    )

    max_weight_grams: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Poids max en grammes"
    )

    serial_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Numéro de série unique par tenant"
    )

    is_available: Mapped[bool] = mapped_column(
        default=True, comment="Disponible pour affectation"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Notes libres"
    )

    # Relations
    assignments: Mapped[list["ContainerAssignment"]] = relationship(
        "ContainerAssignment",
        back_populates="container",
        cascade="all, delete-orphan",
    )

    contents: Mapped[list["ContainerContent"]] = relationship(
        "ContainerContent",
        back_populates="container",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "serial_number", name="uq_container_tenant_serial"),
        CheckConstraint(
            "container_type IN ('bac', 'carton', 'palette', 'housse', 'caisse')",
            name="check_container_type_valid",
        ),
        CheckConstraint("length_cm IS NULL OR length_cm > 0", name="check_container_length_positive"),
        CheckConstraint("width_cm IS NULL OR width_cm > 0", name="check_container_width_positive"),
        CheckConstraint("height_cm IS NULL OR height_cm > 0", name="check_container_height_positive"),
        CheckConstraint("max_weight_grams IS NULL OR max_weight_grams > 0", name="check_container_max_weight_positive"),
    )

    def __repr__(self) -> str:
        return f"<Container(id={self.id}, name='{self.name}', type='{self.container_type}')>"


class ContainerAssignment(Base, TimestampMixin, TenantMixin):
    """Affectation d'un contenant à un mouvement de stock."""

    __tablename__ = "container_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    container_id: Mapped[int] = mapped_column(
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    movement_id: Mapped[int] = mapped_column(
        ForeignKey("inventory_movements.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Notes sur l'affectation"
    )

    # Relations
    container: Mapped["Container"] = relationship(
        "Container", back_populates="assignments"
    )

    items: Mapped[list["ContainerItem"]] = relationship(
        "ContainerItem",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "container_id", "movement_id",
            name="uq_assignment_container_movement",
        ),
    )

    def __repr__(self) -> str:
        return f"<ContainerAssignment(id={self.id}, container={self.container_id}, movement={self.movement_id})>"


class ContainerItem(Base, TimestampMixin, TenantMixin):
    """Article placé dans un contenant affecté à un mouvement."""

    __tablename__ = "container_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    container_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("container_assignments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    movement_item_id: Mapped[int] = mapped_column(
        ForeignKey("movement_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Quantité placée dans ce contenant"
    )

    # Relations
    assignment: Mapped["ContainerAssignment"] = relationship(
        "ContainerAssignment", back_populates="items"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_container_item_quantity_positive"),
    )


class ContainerContent(Base, TimestampMixin, TenantMixin):
    """Contenu persistant d'un contenant — produits physiquement stockes dedans.

    Chaque ligne = un produit (+ variante optionnelle) avec sa quantite.
    Hard-delete quand un produit est retire (l'audit trail vit dans
    les ContainerAssignment/mouvements).
    """

    __tablename__ = "container_contents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    container_id: Mapped[int] = mapped_column(
        ForeignKey("containers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Quantite stockee dans ce contenant"
    )

    # Relations
    container: Mapped["Container"] = relationship(
        "Container", back_populates="contents"
    )

    product: Mapped["Product"] = relationship("Product", lazy="joined")

    variant: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", lazy="joined"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "container_id", "product_id", "variant_id",
            name="uq_container_content_product",
        ),
        CheckConstraint("quantity > 0", name="check_container_content_qty_positive"),
        Index("ix_container_contents_tenant_id_composite", "tenant_id", "id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ContainerContent(id={self.id}, container={self.container_id}, "
            f"product={self.product_id}, variant={self.variant_id}, qty={self.quantity})>"
        )
