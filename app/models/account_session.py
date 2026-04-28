"""Modèle AccountSession — Sessions liées à un membership (remplace UserSession)."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AccountSession(Base):
    """Session d'un compte dans le contexte d'un membership tenant.

    Une session = un account_id + un membership_id précis.
    Changer de tenant nécessite une nouvelle session (nouveau JWT).

    Règles :
        - session_id est le claim 'sid' dans le JWT
        - membership_id est le contexte tenant actif (claim 'mid')
        - tenant_id est dénormalisé pour les requêtes admin (pas de JOIN)
        - mfa_verified = True si challenge TOTP réussi dans cette session
    """

    __tablename__ = "account_sessions"

    __table_args__ = (
        Index("idx_account_sessions_tenant_account", "tenant_id", "account_id"),
        Index(
            "idx_account_sessions_membership_active",
            "membership_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("idx_account_sessions_device", "device_id"),
        Index(
            "idx_account_sessions_account_active",
            "account_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="UUID de session (claim 'sid' dans JWT)",
    )

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        comment="Compte propriétaire (claim 'sub' dans JWT)",
    )

    membership_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenant_memberships.id", ondelete="CASCADE"),
        nullable=False,
        comment="Membership actif au moment du login (claim 'mid' dans JWT)",
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Tenant dénormalisé pour perf (claim 'tid' dans JWT)",
    )

    device_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Fingerprint device (claim 'did' dans JWT)",
    )

    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="IP au login (IPv4 ou IPv6)",
    )

    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiration de la session (refresh token TTL)",
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de révocation — NULL = active",
    )

    revoke_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    mfa_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True si challenge TOTP réussi (acr=2)",
    )

    @property
    def is_active(self) -> bool:
        """Session active (non révoquée et non expirée)."""
        if self.revoked_at is not None:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def __repr__(self) -> str:
        state = "active" if self.revoked_at is None else "revoked"
        return f"<AccountSession(sid='{self.session_id}', account={self.account_id}, {state})>"
