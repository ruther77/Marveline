"""Modèle ORM ProductCollection — regroupement thématique de produits."""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.product import Product


# Table d'association many-to-many
product_collection_items = Table(
    "product_collection_items",
    Base.metadata,
    Column("collection_id", Integer, ForeignKey("product_collections.id", ondelete="CASCADE"),
           primary_key=True),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"),
           primary_key=True),
)


class ProductCollection(Base, TimestampMixin, TenantMixin):
    """Collection thématique de produits (ex: 'Mariage Champêtre', 'Pack DJ')."""

    __tablename__ = "product_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    products: Mapped[list["Product"]] = relationship(
        "Product",
        secondary="product_collection_items",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ProductCollection(id={self.id}, name='{self.name}')>"
