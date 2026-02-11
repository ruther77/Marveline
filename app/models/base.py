"""Modèles de base SQLAlchemy avec mixins pour timestamps et multi-tenant."""
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""
    pass


class TimestampMixin:
    """Mixin pour ajouter created_at et updated_at à tous les modèles."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de création de l'enregistrement"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Date de dernière modification"
    )


class TenantMixin:
    """Mixin pour multi-tenant - toutes les tables métier doivent l'inclure."""

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="ID du tenant (organisation cliente)"
    )


class SoftDeleteMixin:
    """Mixin pour suppression logique (soft delete)."""

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Actif (False = supprimé logiquement)"
    )

    def soft_delete(self) -> None:
        """Suppression logique."""
        self.is_active = False

    def restore(self) -> None:
        """Restaurer après suppression logique."""
        self.is_active = True
