"""Modele WebAuthn — credentials FIDO2 (M-03).

Stocke les credentials WebAuthn enregistres par les utilisateurs
comme alternative au TOTP pour l'authentification MFA.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class WebAuthnCredential(Base, TimestampMixin):
    """Credential WebAuthn/FIDO2 associe a un compte.

    Attributes:
        account_id: FK vers le compte proprietaire
        credential_id: Identifiant unique du credential (bytes, fourni par l'authenticator)
        public_key: Cle publique du credential (COSE, bytes)
        sign_count: Compteur de signatures (anti-clonage)
        device_name: Nom lisible donne par l'utilisateur (ex: "YubiKey bureau")
        aaguid: AAGUID de l'authenticator (identification du type de device)
        last_used_at: Derniere utilisation pour authentification
    """

    __tablename__ = "webauthn_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    credential_id: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        unique=True,
        comment="Credential ID (raw bytes, unique globally)",
    )

    public_key: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="Public key in COSE format (bytes)",
    )

    sign_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Signature counter for clone detection",
    )

    device_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Security Key",
        comment="Nom lisible du device (ex: YubiKey bureau)",
    )

    aaguid: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="AAGUID de l'authenticator (identification type)",
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    account = relationship("Account", backref="webauthn_credentials")

    def __repr__(self) -> str:
        return f"<WebAuthnCredential(id={self.id}, account={self.account_id}, name='{self.device_name}')>"
