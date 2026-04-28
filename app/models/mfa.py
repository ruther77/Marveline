"""Model MFADevice — TOTP MFA devices for tenant memberships.

Each membership can have at most one active MFA device (IAM v2).
The TOTP secret is stored using envelope encryption (spec §05-MFA-TOTP §5.4).

Envelope encryption v2 (4 colonnes) :
    - encrypted_secret: ciphertext + GCM tag (sans nonce)
    - totp_secret_nonce: GCM nonce 12 bytes
    - totp_encrypted_dek: DEK chiffré par KEK (nonce_12b + ct_dek_tag)
    - totp_key_version: "dev-v1" ou ARN AWS KMS version

Other security:
    - recovery_codes_hash: JSON list of bcrypt hashes
    - last_totp_window: Anti-replay (reject reuse of same TOTP window)
    - membership_id: Unique — 1 device par membership (IAM v2)
"""
from typing import Optional
from sqlalchemy import BigInteger, Boolean, Integer, LargeBinary, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MFADevice(Base, TimestampMixin):
    """TOTP MFA device for a tenant membership (IAM v2).

    Attributes:
        membership_id: FK to tenant_memberships.id (one MFA device per membership)
        encrypted_secret: AES-256-GCM encrypted TOTP secret
        is_enabled: True once setup is verified (2-step setup flow)
        recovery_codes_hash: JSON list of bcrypt-hashed recovery codes
        last_totp_window: Last accepted TOTP time window (anti-replay)
    """

    __tablename__ = "mfa_devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # IAM v2 — 1 device par membership
    membership_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("tenant_memberships.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        comment="Membership auquel appartient ce device TOTP (IAM v2 — 1 device par membership)",
    )

    encrypted_secret: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="AES-256-GCM ciphertext + tag (envelope v2 : sans nonce)",
    )

    # Envelope encryption v2 (spec §05-MFA-TOTP §5.4)
    totp_secret_nonce: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary(12),
        nullable=True,
        comment="GCM nonce 12 bytes (envelope encryption v2)",
    )

    totp_encrypted_dek: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="DEK chiffré par KEK — nonce_12b + ct_dek_tag",
    )

    totp_key_version: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Version clé KMS ('dev-v1' ou ARN AWS KMS version)",
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
        return f"<MFADevice(id={self.id}, membership_id={self.membership_id}, enabled={self.is_enabled})>"
