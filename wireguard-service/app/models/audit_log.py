"""Modèle WgAuditLog — journal d'audit append-only pour les actions WireGuard."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class WgAuditLog(Base, TenantMixin):
    """Journal d'audit immutable pour les opérations WireGuard.

    Append-only : aucune modification ni suppression autorisée.
    """

    __tablename__ = "wg_audit_logs"
    __table_args__ = (
        Index("ix_wg_audit_logs_tenant_id_id", "tenant_id", "id"),
        Index("ix_wg_audit_logs_peer_id", "peer_id"),
        Index("ix_wg_audit_logs_action", "action"),
        Index("ix_wg_audit_logs_created_at", "created_at"),
        {"schema": "wg"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    peer_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    actor_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
