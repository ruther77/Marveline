"""Modele ApiKey - Cles API pour authentification machine-to-machine."""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class ApiKey(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Cle API pour authentification M2M (machine-to-machine).

    Attributes:
        name: Nom descriptif de la cle (ex: "Caisse magasin 1")
        key_prefix: Prefixe visible pour identification (ex: "mk_live_a1b2")
        key_hash: SHA-256 du full key (jamais le key en clair en base)
        scopes: Permissions accordees (sous-ensemble de Permission enum)
        rate_limit: Limite requetes par heure (null = defaut tenant)
        expires_at: Date d'expiration (null = pas d'expiration)
        created_by: ID de l'admin qui a cree la cle
        last_used_at: Derniere utilisation
        last_used_ip: IP de la derniere utilisation
        usage_count: Compteur d'utilisations

    Security:
        - Le full key n'est visible QU'AU CREATE et ROTATE
        - key_hash = SHA-256(full_key) pour stockage securise
        - Scopes valides contre Permission enum (jamais > role admin)
        - Rate limiting independant par API key
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nom descriptif de la cle API"
    )

    key_prefix: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        comment="Prefixe visible pour identification (mk_live_xxxx)"
    )

    key_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="SHA-256 du full key"
    )

    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        comment="Permissions accordees (resource:action)"
    )

    rate_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1000,
        comment="Limite requetes par heure (null = defaut tenant)"
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date d'expiration (null = pas d'expiration)"
    )

    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id"),
        nullable=False,
        comment="ID de l'admin qui a cree la cle"
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de derniere utilisation"
    )

    last_used_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP de la derniere utilisation (IPv4 ou IPv6)"
    )

    usage_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Compteur d'utilisations"
    )

    # Relations
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="select",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "key_prefix", name="uq_api_keys_tenant_prefix"),
        UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        CheckConstraint(
            "array_length(scopes, 1) > 0",
            name="ck_api_keys_scopes_not_empty"
        ),
        CheckConstraint(
            "rate_limit IS NULL OR rate_limit > 0",
            name="ck_api_keys_rate_limit_positive"
        ),
        Index("ix_api_keys_key_hash", "key_hash"),
        Index("ix_api_keys_tenant_active", "tenant_id", "is_active",
              postgresql_where="is_active = TRUE"),
    )

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, name='{self.name}', prefix='{self.key_prefix}')>"
