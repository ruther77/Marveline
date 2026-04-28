"""Modèle PasswordResetToken — tokens de réinitialisation de mot de passe (IAM v2).

Architecture (spec §04-AUTH-FLOWS §4.4) :
    - Token brut : secrets.token_bytes(32) → envoyé en clair par email
    - Stockage   : SHA-256(token_bytes) en BD (jamais le token brut)
    - TTL        : 1h (expires_at = now + 3600s)
    - Usage      : unique (used BOOLEAN DEFAULT FALSE)
    - Lié à      : accounts.id (IAM v2 — global, sans tenant)
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PasswordResetToken(Base, TimestampMixin):
    """Token de réinitialisation de mot de passe (single-use, TTL 1h).

    IAM v2 : lié à account_id (global). Plus de tenant_id ni user_id.
    Les colonnes DB user_id/tenant_id existent encore (nullable) jusqu'au DROP en Lot 8.

    Attributes:
        token_hash: SHA-256 hex du token brut (64 chars) — jamais le token en clair
        account_id: FK vers accounts.id (propriétaire global)
        email: Email destinataire (pour audit)
        expires_at: Timestamp d'expiration (now + 3600s)
        used: True une fois consommé — empêche la réutilisation
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hex du token brut (spec §04-AUTH-FLOWS §4.4)",
    )

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Compte propriétaire du token de reset (IAM v2)",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email destinataire du lien de reset (pour audit)",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiration du token (TTL 1h — spec §4.4)",
    )

    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True une fois consommé (single-use — spec §4.4)",
    )

    def __repr__(self) -> str:
        return (
            f"<PasswordResetToken(id={self.id}, account_id={self.account_id}, "
            f"used={self.used}, expires_at={self.expires_at})>"
        )
