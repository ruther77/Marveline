"""Service pour la gestion des maintenances produit."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.product_maintenance import ProductMaintenance
from app.repositories.product_maintenance import AsyncProductMaintenanceRepository
from app.schemas.product_maintenance import MaintenanceCreate, MaintenanceUpdate
from app.services.product import AsyncProductService


class ProductMaintenanceService:
    """Logique métier pour les maintenances produit."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AsyncProductMaintenanceRepository(db)
        self.product_service = AsyncProductService(db)

    async def list_maintenances(
        self,
        tenant_id: int,
        product_id: int,
    ) -> list[ProductMaintenance]:
        # Vérifie que le produit existe et appartient au tenant
        await self.product_service.get_product(product_id, tenant_id)
        return await self.repo.list_by_product(tenant_id, product_id)

    async def create_maintenance(
        self,
        tenant_id: int,
        product_id: int,
        data: MaintenanceCreate,
    ) -> ProductMaintenance:
        await self.product_service.get_product(product_id, tenant_id)
        maintenance = ProductMaintenance(
            tenant_id=tenant_id,
            product_id=product_id,
            title=data.title,
            description=data.description,
            scheduled_date=data.scheduled_date,
            cost_cents=data.cost_cents,
            status="scheduled",
        )
        return await self.repo.create(maintenance)

    async def update_maintenance(
        self,
        tenant_id: int,
        maintenance_id: int,
        data: MaintenanceUpdate,
    ) -> ProductMaintenance:
        maintenance = await self.repo.get(tenant_id, maintenance_id)
        if maintenance is None:
            raise NotFound("Maintenance introuvable")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(maintenance, field, value)
        await self.db.flush()
        return maintenance

    async def delete_maintenance(
        self,
        tenant_id: int,
        maintenance_id: int,
    ) -> None:
        maintenance = await self.repo.get(tenant_id, maintenance_id)
        if maintenance is None:
            raise NotFound("Maintenance introuvable")
        await self.repo.delete(maintenance)
