"""Endpoints admin de provisioning tenant (§S-13.2 §10-MULTI-TENANT-OPS).

Protégés par scope 'config:write' + step-up MFA obligatoire.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_stepup, UserManagerScope
from app.services.tenant import TenantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/provision", tags=["Provisioning Admin"])


class TenantProvisionRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    domain: str = Field(..., min_length=3, max_length=200)
    contact_email: EmailStr
    app_code: str = Field(..., pattern="^(marveline|epicerie|restaurant)$")
    plan: str = Field(default="standard", pattern="^(standard|premium|enterprise)$")
    notes: Optional[str] = None


class TenantProvisionResponse(BaseModel):
    id: int
    external_id: str
    name: str
    domain: str
    status: str
    plan: str
    message: str


class TenantActionRequest(BaseModel):
    reason: Optional[str] = None


@router.post("", response_model=TenantProvisionResponse, status_code=status.HTTP_201_CREATED)
async def provision_tenant(
    body: TenantProvisionRequest,
    current_user: UserManagerScope,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
) -> TenantProvisionResponse:
    """Provisionne un nouveau tenant (super_admin/tenant_admin + step-up §S-13.2).

    Crée un tenant en status 'provisioning'. Appeler ensuite
    POST /admin/provision/{id}/activate pour le rendre opérationnel.
    """
    service = TenantService(db)
    tenant = await service.provision(
        name=body.name,
        domain=body.domain,
        contact_email=body.contact_email,
        app_code=body.app_code,
        plan=body.plan,
        provisioned_by=current_user.id,
        notes=body.notes,
    )
    await db.commit()

    return TenantProvisionResponse(
        id=tenant.id,
        external_id=tenant.external_id,
        name=tenant.name,
        domain=tenant.domain,
        status=tenant.status,
        plan=tenant.plan,
        message=f"Tenant '{tenant.name}' provisionné. external_id={tenant.external_id}",
    )


@router.post("/{tenant_id}/activate", status_code=status.HTTP_200_OK)
async def activate_tenant(
    tenant_id: int,
    current_user: UserManagerScope,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
):
    """Active un tenant en status 'provisioning' → 'active'."""
    service = TenantService(db)
    tenant = await service.activate(tenant_id=tenant_id, activated_by=current_user.id)
    await db.commit()
    return {"tenant_id": tenant_id, "status": tenant.status, "activated_at": tenant.activated_at.isoformat()}


@router.post("/{tenant_id}/suspend", status_code=status.HTTP_200_OK)
async def suspend_tenant(
    tenant_id: int,
    current_user: UserManagerScope,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
    body: TenantActionRequest = Body(default=TenantActionRequest()),
):
    """Suspend un tenant actif (mutations client bloquées)."""
    service = TenantService(db)
    tenant = await service.suspend(
        tenant_id=tenant_id,
        suspended_by=current_user.id,
        reason=body.reason,
    )
    await db.commit()
    return {"tenant_id": tenant_id, "status": tenant.status, "suspended_at": tenant.suspended_at.isoformat()}


@router.post("/{tenant_id}/offboard", status_code=status.HTTP_200_OK)
async def offboard_tenant(
    tenant_id: int,
    current_user: UserManagerScope,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_stepup),
    body: TenantActionRequest = Body(default=TenantActionRequest()),
):
    """Déclenche la procédure d'offboarding RGPD (§S-13.1 §10)."""
    service = TenantService(db)
    tenant = await service.start_offboarding(
        tenant_id=tenant_id,
        initiated_by=current_user.id,
        reason=body.reason,
    )
    await db.commit()
    return {
        "tenant_id": tenant_id,
        "status": tenant.status,
        "offboarding_started_at": tenant.offboarding_started_at.isoformat(),
        "data_retention_days": tenant.data_retention_days,
    }


@router.get("/degraded/status", status_code=status.HTTP_200_OK)
async def get_degradation_status(current_user: UserManagerScope):
    """Retourne le niveau de dégradation actuel (§S-08.4)."""
    from app.core.redis import redis_sec
    return {"degradation_level": redis_sec.get_degradation_level()}


@router.post("/degraded/enable", status_code=status.HTTP_200_OK)
async def enable_degraded_mode(
    current_user: UserManagerScope,
    _: None = Depends(require_stepup),
    level: str = Body(..., pattern="^(READ_ONLY|AUTH_DOWN|EMERGENCY_BYPASS)$"),
    ttl_seconds: int = Body(default=3600, ge=60, le=86400),
):
    """Active un niveau de dégradation (§S-08.4). TTL auto-expiration."""
    from app.core.redis import redis_sec
    from app.constants import RedisKeys

    flag_map = {
        "READ_ONLY": RedisKeys.DEGRADED_READ_ONLY,
        "AUTH_DOWN": RedisKeys.DEGRADED_AUTH_DOWN,
        "EMERGENCY_BYPASS": RedisKeys.DEGRADED_EMERGENCY_BYPASS,
    }
    redis_sec.set_degraded_flag(flag_map[level], ttl_seconds=ttl_seconds)
    logger.critical("Degraded mode ENABLED: level=%s ttl=%ss by user=%s", level, ttl_seconds, current_user.id)
    return {"degradation_level": level, "ttl_seconds": ttl_seconds, "activated": True}


@router.post("/degraded/disable", status_code=status.HTTP_200_OK)
async def disable_degraded_mode(
    current_user: UserManagerScope,
    _: None = Depends(require_stepup),
    level: str = Body(..., pattern="^(READ_ONLY|AUTH_DOWN|EMERGENCY_BYPASS)$"),
):
    """Désactive un niveau de dégradation (retour NOMINAL si aucun autre flag actif)."""
    from app.core.redis import redis_sec
    from app.constants import RedisKeys

    flag_map = {
        "READ_ONLY": RedisKeys.DEGRADED_READ_ONLY,
        "AUTH_DOWN": RedisKeys.DEGRADED_AUTH_DOWN,
        "EMERGENCY_BYPASS": RedisKeys.DEGRADED_EMERGENCY_BYPASS,
    }
    redis_sec.clear_degraded_flag(flag_map[level])
    new_level = redis_sec.get_degradation_level()
    logger.info("Degraded mode DISABLED: level=%s → now=%s by user=%s", level, new_level, current_user.id)
    return {"degradation_level_disabled": level, "current_level": new_level}
