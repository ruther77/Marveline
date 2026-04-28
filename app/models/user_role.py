"""Modele UserRole - Assignation user→role par tenant (CaroCorp §6.5)."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Index, String,
    func, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class UserRole(Base):
    """Assignation d'un role a un utilisateur pour un tenant.

    Regle : 1 role actif par user par tenant (UNIQUE partiel sur revoked_at IS NULL).
    Historique conserve via soft-delete (revoked_at).

    Attributes:
        id: Cle primaire auto-increment
        user_id: FK vers users.id
        tenant_id: Tenant concerne (BigInteger, coherent avec TenantMixin)
        role_name: FK vers auth_roles.name
        assigned_by: FK vers users.id (qui a attribue le role)
        assigned_at: Date d'attribution
        revoked_at: Date de revocation (NULL = actif)
        revoke_reason: Raison de la revocation
    """

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Cle primaire"
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        comment="Account concerne (IAM v2)"
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Tenant concerne"
    )

    role_name: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("auth_roles.name", ondelete="RESTRICT"),
        nullable=False,
        comment="Role attribue"
    )

    assigned_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=False,
        comment="Account ayant attribue le role (IAM v2)"
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Date d'attribution"
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de revocation (NULL = actif)"
    )

    revoke_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Raison de la revocation"
    )

    # Relations
    role: Mapped["AuthRole"] = relationship(
        "AuthRole",
        back_populates="user_roles"
    )

    user: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[user_id],
        lazy="noload"
    )

    assigner: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[assigned_by],
        lazy="noload"
    )

    __table_args__ = (
        # 1 role actif par user par tenant (contrainte partielle)
        # UniqueConstraint postgresql_where non supporté SQLAlchemy 2.0 → Index unique=True
        Index(
            "uq_user_roles_active_per_tenant",
            "user_id", "tenant_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL")
        ),
        # Index pour requetes par tenant + role actif
        Index(
            "idx_user_roles_tenant_active",
            "tenant_id", "role_name",
            postgresql_where=text("revoked_at IS NULL")
        ),
        # Index pour requetes par user actif
        Index(
            "idx_user_roles_user_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL")
        ),
    )

    def __repr__(self) -> str:
        status = "active" if self.revoked_at is None else "revoked"
        return f"<UserRole(user_id={self.user_id}, role='{self.role_name}', {status})>"
