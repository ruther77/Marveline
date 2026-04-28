"""Modele AuthScope - Permissions granulaires RBAC (CaroCorp §6.2)."""
from datetime import datetime
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class AuthScope(Base):
    """Scope (permission granulaire) RBAC.

    Format : {resource}:{action}
    Exemples : reservations:write, users:manage, audit:read

    Table de reference statique geree par migration Alembic.
    26 scopes definis dans CaroCorp §6.2.

    Attributes:
        name: Identifiant unique du scope (PK, format resource:action)
        resource: Ressource ciblee (reservations, stock, users, etc.)
        action: Action autorisee (read, write, manage, delete, etc.)
        description: Description du scope
    """

    __tablename__ = "auth_scopes"

    name: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        comment="Identifiant unique (format resource:action)"
    )

    resource: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Ressource ciblee"
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Action autorisee"
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description du scope"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date de creation"
    )

    # Relations
    role_scopes: Mapped[list["AuthRoleScope"]] = relationship(
        "AuthRoleScope",
        back_populates="scope",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AuthScope(name='{self.name}')>"
