"""Modele Category - Categories hierarchiques de produits."""
from typing import Optional
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class Category(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Categorie de produits avec hierarchie parent/enfant.

    Attributes:
        name: Nom de la categorie (ex: "Assiettes")
        slug: Slug URL-safe unique par tenant (ex: "assiettes")
        description: Description optionnelle
        parent_id: ID de la categorie parente (nullable = racine)
        image_url: URL de l'image de la categorie
        display_order: Ordre d'affichage (0 = defaut)
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Nom de la categorie"
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Slug URL-safe unique par tenant"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Description de la categorie"
    )

    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("categories.id", name="fk_category_parent"),
        nullable=True,
        index=True,
        comment="ID de la categorie parente (NULL = racine)"
    )

    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL de l'image de la categorie"
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Ordre d'affichage"
    )

    # Relations
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
    )

    # Contraintes
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_category_tenant_slug"),
        UniqueConstraint("tenant_id", "name", name="uq_category_tenant_name"),
        CheckConstraint("display_order >= 0", name="check_category_display_order"),
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, slug='{self.slug}', name='{self.name}')>"
