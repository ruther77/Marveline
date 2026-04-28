"""Repository TenantSettings."""
from sqlalchemy.orm import Session

from app.models.tenant_settings import TenantSettings
from app.schemas.tenant_settings import TenantSettingsUpdate


class TenantSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, tenant_id: int) -> TenantSettings:
        """Retourne les paramètres du tenant, en les créant avec les valeurs par défaut si absents."""
        obj = self.db.query(TenantSettings).filter_by(tenant_id=tenant_id).first()
        if obj is None:
            obj = TenantSettings(tenant_id=tenant_id)
            self.db.add(obj)
            self.db.flush()
        return obj

    def update(self, tenant_id: int, data: TenantSettingsUpdate) -> TenantSettings:
        """Met à jour les paramètres du tenant (upsert)."""
        obj = self.get(tenant_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(obj, field, value)
        self.db.flush()
        return obj


class AsyncTenantSettingsRepository:
    """Version async de TenantSettingsRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get(self, tenant_id: int):
        from sqlalchemy import select
        from app.models.tenant_settings import TenantSettings
        result = await self.db.execute(
            select(TenantSettings).filter(TenantSettings.tenant_id == tenant_id)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            obj = TenantSettings(tenant_id=tenant_id)
            self.db.add(obj)
            await self.db.flush()
            await self.db.refresh(obj)
        return obj

    async def update(self, tenant_id: int, data) -> object:
        obj = await self.get(tenant_id)
        update_data = data.model_dump(exclude_none=True) if hasattr(data, "model_dump") else data
        for field, value in update_data.items():
            setattr(obj, field, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
