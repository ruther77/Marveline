"""Modèle ProductImage — galerie multi-images par produit."""
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin


class ProductImage(Base, TimestampMixin, TenantMixin):
    """Image d'un produit (galerie multi-images).

    Attributs :
        product_id : FK vers products.id
        url        : chemin/URL de l'image
        sort_order : ordre d'affichage (0 = premier)
        is_primary : image principale (affichée dans les listes)
    """

    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relations
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product", back_populates="images"
    )

    __table_args__ = (
        Index("ix_product_image_tenant_product", "tenant_id", "product_id"),
    )

    def __repr__(self) -> str:
        return f"<ProductImage(id={self.id}, product_id={self.product_id}, primary={self.is_primary})>"
