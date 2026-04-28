"""Modèle TrustedDevice — devices enregistrés pour login PIN.

Un trusted device est une tablette/PC enregistré via un premier login
email+password. Une fois enregistré, les serveurs peuvent se connecter
avec leur PIN 4-6 chiffres sur ce device uniquement.

Workflow :
    1. Premier login email+password sur la tablette → register_device()
    2. Backend stocke device_id + account_id
    3. Login suivants : PIN + device_id → JWT (sans email+password)
    4. Admin peut révoquer un device (revoked_at != null)
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrustedDevice(Base, TimestampMixin):
    """Device de confiance pour login PIN restaurant."""

    __tablename__ = "trusted_devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    device_id: Mapped[str] = mapped_column(
        String(256), nullable=False,
        comment="Fingerprint unique du device",
    )
    device_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Nom lisible (ex: Tablette salle 1)",
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Non null = device révoqué",
    )

    __table_args__ = (
        Index("idx_trusted_devices_account", "account_id"),
        Index("idx_trusted_devices_tenant", "tenant_id"),
        Index("idx_trusted_devices_device_id", "device_id"),
        UniqueConstraint("account_id", "device_id", name="uq_trusted_devices_account_device"),
    )

    def __repr__(self) -> str:
        return f"<TrustedDevice id={self.id} account={self.account_id} device={self.device_id!r}>"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
