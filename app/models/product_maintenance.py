"""Modèle ProductMaintenance pour suivi des maintenances de matériel."""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Text, Date, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class ProductMaintenance(Base, TimestampMixin, SoftDeleteMixin):
    """Suivi des opérations de maintenance sur les produits.

    Statuts : scheduled → in_progress → completed | cancelled
    """

    __tablename__ = "product_maintenances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cost_cents: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")

    product = relationship("Product", back_populates="maintenances", lazy="select")

    __table_args__ = (
        Index("idx_maintenance_tenant_product", "tenant_id", "product_id"),
        Index("idx_maintenance_tenant_id", "tenant_id", "id"),
    )

    def __repr__(self) -> str:
        return f"<ProductMaintenance(id={self.id}, product_id={self.product_id}, status={self.status})>"
