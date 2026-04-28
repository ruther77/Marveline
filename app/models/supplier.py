"""Modèle Supplier — Fournisseurs de produits."""
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class Supplier(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Fournisseur de matériel.

    Attributes:
        name: Raison sociale du fournisseur
        contact_name: Nom du contact principal
        email: Email de contact
        phone: Téléphone
        address: Adresse postale
        notes: Notes libres
    """

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Raison sociale du fournisseur",
    )

    contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Nom du contact principal",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email de contact",
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Téléphone",
    )

    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Adresse postale",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes libres",
    )

    def __repr__(self) -> str:
        return f"<Supplier(id={self.id}, name='{self.name}')>"
