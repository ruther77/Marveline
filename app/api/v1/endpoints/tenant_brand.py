"""Endpoint public GET /tenant/brand — sert l'identite marque avant login.

Permet au frontend de recuperer la palette/logo/nom d'un tenant sans
etre authentifie. Utilise par le systeme brand dynamique (D5-B).

Securite :
- Public (no auth, no rate-limit specifique — fallback middleware rate-limit global)
- Pas de donnees sensibles (uniquement identite publique : nom, couleurs, logo)
- Lookup par brand_code (pas tenant_id direct : anti-enumeration)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.models.tenant import Tenant
from app.models.tenant_brand import TenantBrand
from app.schemas.tenant_brand import TenantBrandPublic

router = APIRouter(prefix="/tenant", tags=["tenant-brand"])


@router.get(
    "/brand",
    response_model=TenantBrandPublic,
    summary="Public brand identity by brand_code",
)
async def get_tenant_brand(
    brand_code: str = Query(..., min_length=2, max_length=30, pattern=r"^[a-z0-9_-]+$"),
    db: AsyncSession = Depends(get_async_db),
) -> TenantBrandPublic:
    """Retourne l'identite brand publique pour un brand_code donne.

    Utilise par le frontend au boot pour habiller l'UI avant login.
    """
    result = await db.execute(
        select(TenantBrand, Tenant)
        .join(Tenant, Tenant.id == TenantBrand.tenant_id)
        .where(Tenant.brand_code == brand_code, Tenant.is_active == True)  # noqa: E712
        .limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"brand not found for code={brand_code}",
        )
    brand, _ = row
    return TenantBrandPublic(
        display_name=brand.display_name,
        legal_name=brand.legal_name,
        tagline=brand.tagline,
        primary_color=brand.primary_color,
        primary_rgb=brand.primary_rgb,
        palette=brand.palette_json,
        logo_url=brand.logo_url,
        logo_square_url=brand.logo_square_url,
        favicon_url=brand.favicon_url,
        contact_email=brand.contact_email,
        contact_phone=brand.contact_phone,
    )
