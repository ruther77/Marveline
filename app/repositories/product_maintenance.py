"""Repository pour ProductMaintenance."""
from sqlalchemy.orm import Session

from app.models.product_maintenance import ProductMaintenance


class ProductMaintenanceRepository:
    """CRUD pour les maintenances produit avec isolation tenant."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_product(
        self,
        tenant_id: int,
        product_id: int,
        include_inactive: bool = False,
    ) -> list[ProductMaintenance]:
        q = self.db.query(ProductMaintenance).filter(
            ProductMaintenance.tenant_id == tenant_id,
            ProductMaintenance.product_id == product_id,
        )
        if not include_inactive:
            q = q.filter(ProductMaintenance.is_active.is_(True))
        return q.order_by(ProductMaintenance.scheduled_date.desc().nullslast(), ProductMaintenance.id.desc()).all()

    def get(self, tenant_id: int, maintenance_id: int) -> ProductMaintenance | None:
        return (
            self.db.query(ProductMaintenance)
            .filter(
                ProductMaintenance.tenant_id == tenant_id,
                ProductMaintenance.id == maintenance_id,
                ProductMaintenance.is_active.is_(True),
            )
            .first()
        )

    def create(self, maintenance: ProductMaintenance) -> ProductMaintenance:
        self.db.add(maintenance)
        self.db.flush()
        return maintenance

    def delete(self, maintenance: ProductMaintenance) -> None:
        maintenance.is_active = False
        self.db.flush()


class AsyncProductMaintenanceRepository:
    """Version async de ProductMaintenanceRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def list_by_product(self, tenant_id: int, product_id: int, include_inactive=False) -> list:
        from sqlalchemy import select
        from app.models.product_maintenance import ProductMaintenance
        q = select(ProductMaintenance).filter(
            ProductMaintenance.tenant_id == tenant_id,
            ProductMaintenance.product_id == product_id,
        )
        if not include_inactive:
            q = q.filter(ProductMaintenance.is_active.is_(True))
        q = q.order_by(ProductMaintenance.scheduled_date.desc().nullslast(), ProductMaintenance.id.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get(self, tenant_id: int, maintenance_id: int):
        from sqlalchemy import select
        from app.models.product_maintenance import ProductMaintenance
        result = await self.db.execute(
            select(ProductMaintenance).filter(
                ProductMaintenance.tenant_id == tenant_id,
                ProductMaintenance.id == maintenance_id,
                ProductMaintenance.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, maintenance):
        self.db.add(maintenance)
        await self.db.flush()
        await self.db.refresh(maintenance)
        return maintenance

    async def delete(self, maintenance) -> None:
        maintenance.is_active = False
        await self.db.flush()
