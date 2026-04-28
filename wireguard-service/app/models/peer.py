"""Modèle WgPeer — un peer WireGuard (client VPN)."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin


class WgPeer(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """Un peer WireGuard (point de vente, technicien, etc.).

    La clé privée est stockée chiffrée (AES-256-GCM) pour permettre
    le re-téléchargement de la configuration client.
    """

    __tablename__ = "wg_peers"
    __table_args__ = (
        Index("ix_wg_peers_tenant_id_id", "tenant_id", "id"),
        Index("ix_wg_peers_tenant_public_key", "tenant_id", "public_key", unique=True),
        {"schema": "wg"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Clés WireGuard
    public_key: Mapped[str] = mapped_column(
        String(44),  # base64-encoded 32 bytes = 44 chars
        nullable=False,
    )

    encrypted_private_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    preshared_key: Mapped[Optional[str]] = mapped_column(
        String(44),
        nullable=True,
    )

    # Réseau
    assigned_ip: Mapped[str] = mapped_column(
        String(18),  # "xxx.xxx.xxx.xxx/32"
        nullable=False,
    )

    allowed_ips: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="0.0.0.0/0",
    )

    # Configuration
    persistent_keepalive: Mapped[int] = mapped_column(
        default=25,
        nullable=False,
    )

    dns: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # État
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Expiration (peers temporaires pour techniciens)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Métadonnées
    peer_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="permanent",  # "permanent", "temporary", "technician"
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    last_handshake_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expires_at
