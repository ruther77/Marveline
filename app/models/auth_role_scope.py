"""Modele AuthRoleScope - Mapping role→scopes RBAC (CaroCorp §6.5)."""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class AuthRoleScope(Base):
    """Association role → scope (table de mapping).

    Table statique geree par migration Alembic.
    Definit quels scopes sont attribues a chaque role.
    Cle primaire composite (role_name, scope_name).

    Attributes:
        role_name: FK vers auth_roles.name
        scope_name: FK vers auth_scopes.name
    """

    __tablename__ = "auth_role_scopes"

    role_name: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("auth_roles.name", ondelete="CASCADE"),
        primary_key=True,
        comment="FK vers auth_roles"
    )

    scope_name: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("auth_scopes.name", ondelete="CASCADE"),
        primary_key=True,
        comment="FK vers auth_scopes"
    )

    # Relations
    role: Mapped["AuthRole"] = relationship(
        "AuthRole",
        back_populates="role_scopes"
    )

    scope: Mapped["AuthScope"] = relationship(
        "AuthScope",
        back_populates="role_scopes"
    )

    def __repr__(self) -> str:
        return f"<AuthRoleScope(role='{self.role_name}', scope='{self.scope_name}')>"
