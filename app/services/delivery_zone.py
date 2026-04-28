"""Service DeliveryZone — logique métier zones de livraison."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.delivery_zone import DeliveryZone
from app.repositories.delivery_zone import AsyncDeliveryZoneRepository
from app.schemas.delivery_zone import DeliveryZoneCreate, DeliveryZoneUpdate

logger = logging.getLogger(__name__)


class DeliveryZoneService:
    """Service pour la gestion des zones de livraison."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncDeliveryZoneRepository(db)

    async def list_zones(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[DeliveryZone], int]:
        """Liste les zones actives du tenant avec pagination SQL.

        Returns:
            Tuple (items, total_count).
        """
        items = await self.repo.list_active(tenant_id, skip=skip, limit=limit)
        total = await self.repo.count_active(tenant_id)
        return items, total

    async def get_zone(self, zone_id: int, tenant_id: int) -> DeliveryZone:
        """Récupère une zone par son ID.

        Raises:
            HTTPException 404: Si zone non trouvée ou autre tenant.
        """
        zone = await self.repo.get_by_id(zone_id, tenant_id)
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DeliveryZone {zone_id} not found",
            )
        return zone

    async def create_zone(
        self, data: DeliveryZoneCreate, tenant_id: int
    ) -> DeliveryZone:
        """Crée une nouvelle zone de livraison.

        Raises:
            HTTPException 409: Si code département déjà existant pour ce tenant.
        """
        if await self.repo.code_exists(data.department_code, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department '{data.department_code}' already exists for this tenant",
            )

        zone = DeliveryZone(
            tenant_id=tenant_id,
            department_code=data.department_code,
            department_name=data.department_name,
            delivery_fee_cents=data.delivery_fee_cents,
            sunday_surcharge_cents=data.sunday_surcharge_cents,
            notes=data.notes,
        )
        self.db.add(zone)
        return zone

    async def update_zone(
        self, zone_id: int, data: DeliveryZoneUpdate, tenant_id: int
    ) -> DeliveryZone:
        """Met à jour une zone (PATCH partiel).

        Raises:
            HTTPException 404: Si zone non trouvée.
        """
        zone = await self.get_zone(zone_id, tenant_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(zone, field, value)

        return zone

    async def delete_zone(self, zone_id: int, tenant_id: int) -> None:
        """Soft delete d'une zone.

        Raises:
            HTTPException 404: Si zone non trouvée.
        """
        zone = await self.get_zone(zone_id, tenant_id)
        zone.soft_delete()
