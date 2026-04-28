"""Modèle WgIpPool — pool d'adresses IP pour allocation aux peers."""

from typing import Optional

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin


class WgIpPool(Base, TimestampMixin, TenantMixin):
    """Pool d'adresses IP WireGuard par tenant.

    Chaque tenant a un ou plusieurs subnets. L'allocation se fait
    de manière atomique avec SELECT ... FOR UPDATE sur next_ip.
    """

    __tablename__ = "wg_ip_pools"
    __table_args__ = (
        Index("ix_wg_ip_pools_tenant_id_id", "tenant_id", "id"),
        Index("ix_wg_ip_pools_tenant_subnet", "tenant_id", "subnet", unique=True),
        {"schema": "wg"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    subnet: Mapped[str] = mapped_column(
        String(18),  # "10.10.0.0/24"
        nullable=False,
    )

    gateway_ip: Mapped[str] = mapped_column(
        String(15),  # "10.10.0.1"
        nullable=False,
    )

    next_ip: Mapped[str] = mapped_column(
        String(15),  # "10.10.0.2" — prochaine IP à allouer
        nullable=False,
    )

    subnet_mask: Mapped[int] = mapped_column(
        default=24,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
