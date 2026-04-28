"""Service DamageType — logique métier types de dommages."""
import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.damage_type import DamageType
from app.repositories.damage_type import AsyncDamageTypeRepository
from app.schemas.damage_type import DamageTypeCreate, DamageTypeUpdate

logger = logging.getLogger(__name__)


class DamageTypeService:
    """Service pour la gestion des types de dommages."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncDamageTypeRepository(db)

    async def list_damage_types(self, tenant_id: int) -> list[DamageType]:
        """Liste tous les types actifs du tenant."""
        return await self.repo.list_active(tenant_id)

    async def get_damage_type(self, damage_type_id: int, tenant_id: int) -> DamageType:
        """Récupère un type par ID.

        Raises:
            HTTPException 404: Si non trouvé ou autre tenant.
        """
        dt = await self.repo.get_by_id(damage_type_id, tenant_id)
        if not dt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DamageType {damage_type_id} not found",
            )
        return dt

    async def create_damage_type(
        self, data: DamageTypeCreate, tenant_id: int
    ) -> DamageType:
        """Crée un nouveau type de dommage.

        Raises:
            HTTPException 409: Si nom déjà existant pour ce tenant.
        """
        if await self.repo.name_exists(data.name, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"DamageType '{data.name}' already exists for this tenant",
            )

        dt = DamageType(
            tenant_id=tenant_id,
            name=data.name,
            default_fee_cents=data.default_fee_cents,
        )
        self.db.add(dt)
        return dt

    async def update_damage_type(
        self, damage_type_id: int, data: DamageTypeUpdate, tenant_id: int
    ) -> DamageType:
        """Met à jour un type de dommage (PATCH partiel).

        Raises:
            HTTPException 404: Si non trouvé.
            HTTPException 409: Si nouveau nom déjà pris.
        """
        dt = await self.get_damage_type(damage_type_id, tenant_id)

        update_data = data.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] != dt.name:
            if await self.repo.name_exists(
                update_data["name"], tenant_id, exclude_id=damage_type_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"DamageType '{update_data['name']}' already exists",
                )

        for field, value in update_data.items():
            setattr(dt, field, value)

        return dt

    async def delete_damage_type(self, damage_type_id: int, tenant_id: int) -> None:
        """Soft delete d'un type de dommage.

        Raises:
            HTTPException 404: Si non trouvé.
        """
        dt = await self.repo.get_by_id(damage_type_id, tenant_id)
        if not dt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DamageType {damage_type_id} not found",
            )
        await self.repo.soft_delete(dt)
