"""Classes de base et mixins pour les modèles SQLAlchemy du service WireGuard.

Réplique les patterns de CaroCorp (multi-tenant, timestamps, soft delete)
dans le schema PostgreSQL 'wg'.
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles WireGuard."""
    pass


class TimestampMixin:
    """Mixin pour ajouter created_at et updated_at automatiques."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Mixin pour l'isolation multi-tenant obligatoire."""

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Mixin pour la suppression logique."""

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    def soft_delete(self) -> None:
        self.is_active = False

    def restore(self) -> None:
        self.is_active = True
