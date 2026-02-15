"""Model MFADevice — TOTP MFA devices for users.

Each user can have at most one active MFA device per tenant.
The TOTP secret is stored encrypted (AES-256-GCM).
Recovery codes are stored as bcrypt hashes (single-use).

Security:
    - encrypted_secret: AES-256-GCM ciphertext (never plaintext in DB)
    - recovery_codes_hash: JSON list of bcrypt hashes
    - last_totp_window: Anti-replay (reject reuse of same TOTP window)
    - tenant_id: Multi-tenant isolation (TenantMixin)
"""
from typing import Optional
from sqlalchemy import BigInteger, Boolean, Integer, LargeBinary, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin


class MFADevice(Base, TimestampMixin, TenantMixin):
    """TOTP MFA device for a user.

    Attributes:
        user_id: FK to users.id (one MFA device per user)
        encrypted_secret: AES-256-GCM encrypted TOTP secret
        is_enabled: True once setup is verified (2-step setup flow)
        recovery_codes_hash: JSON list of bcrypt-hashed recovery codes
        last_totp_window: Last accepted TOTP time window (anti-replay)
    """

    __tablename__ = "mfa_devices"

    __table_args__ = (
        UniqueConstraint(
            'tenant_id',
            'user_id',
            name='uq_mfa_device_tenant_user'
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this MFA device",
    )

    encrypted_secret: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM encrypted TOTP secret",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True once initial TOTP verification succeeds",
    )

    recovery_codes_hash: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON list of bcrypt-hashed recovery codes",
    )

    last_totp_window: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Last accepted TOTP time window (anti-replay)",
    )

    def __repr__(self) -> str:
        return f"<MFADevice(id={self.id}, user_id={self.user_id}, enabled={self.is_enabled})>"
