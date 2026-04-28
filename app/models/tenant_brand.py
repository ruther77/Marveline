"""Modele ORM TenantBrand - identite marque par tenant (logo, couleurs, nom affiche).

Separe des `tenant_settings` (config metier) pour clarifier les concerns :
- tenant_settings : CGV, taux TVA, tarifs, imprimante
- tenant_brand   : nom affiche, legal, logo, palette, tagline

1:1 avec tenants (tenant_id PK + FK).
"""
from typing import Optional
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class TenantBrand(Base):
    __tablename__ = "tenant_brands"

    tenant_id: int = Column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )

    display_name: str = Column(String(200), nullable=False)
    legal_name: str = Column(String(200), nullable=False)
    tagline: Optional[str] = Column(String(300), nullable=True)

    primary_color: str = Column(String(16), nullable=False, default="#b96cc4")
    primary_rgb: str = Column(String(32), nullable=False, default="185 108 196")
    palette_json: Optional[dict] = Column(JSONB, nullable=True)

    logo_url: Optional[str] = Column(String(500), nullable=True)
    logo_square_url: Optional[str] = Column(String(500), nullable=True)
    favicon_url: Optional[str] = Column(String(500), nullable=True)

    contact_email: Optional[str] = Column(String(200), nullable=True)
    contact_phone: Optional[str] = Column(String(50), nullable=True)
    address: Optional[str] = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
