"""Modele AuthRole - Roles systeme RBAC (CaroCorp §6.5)."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class AuthRole(Base):
    """Role RBAC systeme.

    Table de reference statique geree par migration Alembic.
    6 roles : super_admin(0), platform_ops(1), tenant_admin(2),
    manager(3), staff(4), viewer(5).

    Attributes:
        name: Identifiant unique du role (PK)
        level: Niveau hierarchique (0=plus eleve, 5=plus bas)
        is_system: True = role cross-tenant (super_admin, platform_ops)
        mfa_required: MFA obligatoire pour ce role
        description: Description du role
    """

    __tablename__ = "auth_roles"

    name: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        comment="Identifiant unique du role"
    )

    level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Niveau hierarchique (0=super_admin, 5=viewer)"
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Role cross-tenant (super_admin, platform_ops)"
    )

    mfa_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="MFA obligatoire pour ce role"
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Description du role"
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
        back_populates="role",
        lazy="selectin"
    )

    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AuthRole(name='{self.name}', level={self.level})>"
