"""Modèle Account — Identité globale (remplace users, CaroCorp IAM v2)."""
import uuid
from typing import Optional
from sqlalchemy import Boolean, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class Account(Base, TimestampMixin, SoftDeleteMixin):
    """Identité globale unique dans la plateforme CaroCorp.

    Un compte représente une personne physique identifiée par email global.
    Il est indépendant du tenant : l'appartenance à un tenant est gérée
    par TenantMembership.

    Règles :
        - email unique globalement et immuable
        - hashed_password nullable (comptes OAuth-only)
        - is_active = suspension globale (tous tenants bloqués)
        - password_change_required = flag HIBP global
    """

    __tablename__ = "accounts"

    __table_args__ = (
        UniqueConstraint("email", name="uq_accounts_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    external_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID v4 immuable — jamais réutilisé",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Email unique global et immuable (clé de login)",
    )

    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Argon2id+pepper hash — null si compte OAuth-only",
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    password_change_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True si password détecté dans HIBP (flag global)",
    )

    pin_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Argon2id hash du PIN 4-6 chiffres — null si non configuré",
    )

    @property
    def full_name(self) -> str:
        """Nom complet."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, email='{self.email}')>"


@event.listens_for(Account.email, "set", retval=True)
def _normalize_email(target, value, oldvalue, initiator):
    """Normalise email en lowercase+strip avant stockage."""
    if value is not None:
        return value.lower().strip()
    return value
