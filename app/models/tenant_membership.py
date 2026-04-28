"""Modèle TenantMembership — Appartenance d'un compte à un tenant (CaroCorp IAM v2)."""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

MEMBERSHIP_STATUSES = ("active", "suspended", "offboarding")


class TenantMembership(Base):
    """Appartenance d'un compte global à un tenant avec un rôle RBAC.

    Remplace la table user_roles et absorbe le lien tenant de users.
    Un membership représente : qui (account) peut faire quoi (role) dans quel tenant.

    Règles :
        - 1 membership actif par (account, tenant) — UNIQUE partiel sur revoked_at IS NULL
        - L'historique est conservé via revoked_at (jamais de DELETE)
        - MFA est configuré par membership (mfa_devices.membership_id)
        - Sessions attachées à un membership précis (account_sessions.membership_id)

    State machine status : active → suspended → offboarding (terminal)
    """

    __tablename__ = "tenant_memberships"

    __table_args__ = (
        CheckConstraint(
            f"status IN {MEMBERSHIP_STATUSES}",
            name="ck_membership_status_valid",
        ),
        Index(
            "uq_membership_active_per_tenant",
            "account_id", "tenant_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "idx_membership_tenant_role",
            "tenant_id", "role_name",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "idx_membership_account_active",
            "account_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("idx_membership_tenant_all", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        comment="Compte global",
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="Tenant concerné",
    )

    role_name: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("auth_roles.name", ondelete="RESTRICT"),
        nullable=False,
        comment="Rôle RBAC du membership",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
        comment="État : active | suspended | offboarding",
    )

    invited_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Compte ayant invité ce membre (null = auto-provisionné)",
    )

    invited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'invitation",
    )

    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
        comment="Date d'activation du membership",
    )

    suspended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de suspension",
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de révocation — NULL = membership actif",
    )

    revoke_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Raison de la révocation",
    )

    # Relations
    # lazy="raise" : toute tentative d'accès non préchargé lève une exception explicite
    # (évite les None silencieux de "noload"). Charger via JOIN explicite (list_users) ou
    # selectinload() dans un select() simple (pas un tuple-select).
    account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[account_id],
        lazy="raise",
    )

    role: Mapped["AuthRole"] = relationship("AuthRole", lazy="selectin")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.status == "active"

    def __repr__(self) -> str:
        state = "active" if self.revoked_at is None else "revoked"
        return (
            f"<TenantMembership(account={self.account_id}, "
            f"tenant={self.tenant_id}, role='{self.role_name}', {state})>"
        )
