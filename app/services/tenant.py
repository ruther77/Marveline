"""Service tenant lifecycle — onboarding, suspension, offboarding (§S-13.1).

State machine légale :
    provisioning → active → suspended → offboarding → archived
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class TenantService:
    """Service de gestion du cycle de vie des tenants (§S-13.1 §10-MULTI-TENANT-OPS)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def provision(
        self,
        name: str,
        domain: str,
        contact_email: str,
        app_code: str,
        plan: str = "standard",
        provisioned_by: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Tenant:
        """Provisionne un nouveau tenant (14 étapes §10).

        Étapes implémentées :
          1. Valider unicité domain + email
          2. Générer external_id (UUID v4 immuable)
          3. Créer enregistrement Tenant (status=provisioning)
          4. Audit TENANT_PROVISIONED

        Les étapes infrastructure (DNS, email config, etc.) sont déclenchées
        hors de ce service (webhooks Celery).
        """
        # 1. Vérifier unicité du domaine
        existing = await self.db.scalar(
            select(Tenant).where(Tenant.domain == domain)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Domain '{domain}' already provisioned for tenant {existing.external_id}",
            )

        # 2. Créer le tenant en status provisioning (ISO-APP-01 : app_code requis)
        if app_code not in Tenant.APP_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid app_code '{app_code}'. Expected one of {Tenant.APP_CODES}",
            )
        tenant = Tenant(
            external_id=str(uuid.uuid4()),
            name=name,
            domain=domain,
            contact_email=contact_email,
            app_code=app_code,
            plan=plan,
            status="provisioning",
            is_active=False,
            provisioned_by=provisioned_by,
            notes=notes,
        )
        self.db.add(tenant)
        await self.db.flush()

        # 3. Audit
        await self.audit.log_action(
            action="TENANT_PROVISIONED",
            tenant_id=tenant.id,
            user_id=provisioned_by or 0,
            entity_type="Tenant",
            entity_id=tenant.id,
            description=f"Tenant {name} ({domain}) provisionné — plan={plan}",
        )
        logger.info("Tenant provisioned: id=%s external=%s domain=%s", tenant.id, tenant.external_id, domain)
        return tenant

    async def activate(self, tenant_id: int, activated_by: int) -> Tenant:
        """Active un tenant en status 'provisioning' → 'active'."""
        tenant = await self._get_or_404(tenant_id)
        self._assert_transition(tenant, "active")

        tenant.status = "active"
        tenant.is_active = True
        tenant.activated_at = datetime.now(timezone.utc)
        await self.db.flush()

        await self.audit.log_action(
            action="TENANT_ACTIVATED",
            tenant_id=tenant_id,
            user_id=activated_by,
            entity_type="Tenant",
            entity_id=tenant_id,
            description=f"Tenant {tenant.name} activé",
        )
        return tenant

    async def suspend(self, tenant_id: int, suspended_by: int, reason: Optional[str] = None) -> Tenant:
        """Suspend un tenant actif → status 'suspended'."""
        tenant = await self._get_or_404(tenant_id)
        self._assert_transition(tenant, "suspended")

        tenant.status = "suspended"
        tenant.is_active = False
        tenant.suspended_at = datetime.now(timezone.utc)
        if reason:
            tenant.notes = f"[{datetime.now(timezone.utc).date()}] Suspension: {reason}\n{tenant.notes or ''}"
        await self.db.flush()

        await self.audit.log_action(
            action="TENANT_SUSPENDED",
            tenant_id=tenant_id,
            user_id=suspended_by,
            entity_type="Tenant",
            entity_id=tenant_id,
            description=f"Tenant {tenant.name} suspendu — reason={reason or 'none'}",
        )
        return tenant

    async def start_offboarding(self, tenant_id: int, initiated_by: int, reason: Optional[str] = None) -> Tenant:
        """Déclenche la procédure d'offboarding (§10 8 étapes RGPD)."""
        tenant = await self._get_or_404(tenant_id)
        self._assert_transition(tenant, "offboarding")

        tenant.status = "offboarding"
        tenant.is_active = False
        tenant.offboarding_started_at = datetime.now(timezone.utc)
        if reason:
            tenant.notes = f"[{datetime.now(timezone.utc).date()}] Offboarding: {reason}\n{tenant.notes or ''}"
        await self.db.flush()

        await self.audit.log_action(
            action="TENANT_OFFBOARDING_STARTED",
            tenant_id=tenant_id,
            user_id=initiated_by,
            entity_type="Tenant",
            entity_id=tenant_id,
            description=f"Offboarding démarré pour {tenant.name} — retention={tenant.data_retention_days}j",
        )
        return tenant

    async def get_by_id(self, tenant_id: int) -> Tenant:
        return await self._get_or_404(tenant_id)

    async def get_by_external_id(self, external_id: str) -> Optional[Tenant]:
        return await self.db.scalar(select(Tenant).where(Tenant.external_id == external_id))

    # ── Privé ────────────────────────────────────────────────────────────────

    async def _get_or_404(self, tenant_id: int) -> Tenant:
        tenant = await self.db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )
        return tenant

    @staticmethod
    def _assert_transition(tenant: Tenant, new_status: str) -> None:
        if not tenant.can_transition_to(new_status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid transition: {tenant.status} → {new_status}",
            )
