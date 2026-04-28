"""Modèle FinanceVendor — Référentiel fournisseurs.

Sans tenant_id : référentiel global partagé entre tous les tenants (ADR-02).
Fournisseurs comme METRO, TAIYAT, etc. sont des entités globales.
"""
from typing import Optional

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FinanceVendor(Base, TimestampMixin):
    """Fournisseur dans le référentiel global.

    Pas de TenantMixin : partagé globalement (ADR-02).
    """

    __tablename__ = "finance_vendors"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Raison sociale du fournisseur (ex: METRO Cash & Carry)"
    )
    code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, unique=True,
        comment="Code court unique (ex: METRO, TAIYAT)"
    )
    adresse: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Adresse postale complète"
    )
    telephone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Numéro de téléphone"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True,
        comment="Email de contact"
    )
    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        Index("idx_finance_vendor_code", "code"),
        Index("idx_finance_vendor_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<FinanceVendor id={self.id} code={self.code!r} name={self.name!r}>"
