"""Service Container — logique metier contenants, affectations et contenu."""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.container import (
    Container,
    ContainerAssignment,
    ContainerContent,
    ContainerItem,
)
from app.repositories.container import AsyncContainerRepository
from app.schemas.container import (
    BulkContentRequest,
    ContainerAssignCreate,
    ContainerContentCreate,
    ContainerContentUpdate,
    ContainerCreate,
    ContainerUpdate,
)

logger = logging.getLogger(__name__)

VALID_CONTAINER_TYPES = {"bac", "carton", "palette", "housse", "caisse"}


class ContainerService:
    """Service pour la gestion des contenants et affectations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncContainerRepository(db)

    async def list_containers(
        self, tenant_id: int, skip: int = 0, limit: int = 50
    ) -> tuple[list[Container], int]:
        return await self.repo.list_active(tenant_id, skip, limit)

    async def get_container(self, container_id: int, tenant_id: int) -> Container:
        c = await self.repo.get_by_id(container_id, tenant_id)
        if not c or not c.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} not found",
            )
        return c

    async def create_container(
        self, data: ContainerCreate, tenant_id: int
    ) -> Container:
        if data.container_type not in VALID_CONTAINER_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid container_type '{data.container_type}'. "
                       f"Valid: {', '.join(sorted(VALID_CONTAINER_TYPES))}",
            )
        if data.serial_number and await self.repo.serial_exists(
            data.serial_number, tenant_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Serial number '{data.serial_number}' already exists",
            )
        obj = Container(
            tenant_id=tenant_id,
            **data.model_dump(),
        )
        return await self.repo.create(obj)

    async def update_container(
        self, container_id: int, data: ContainerUpdate, tenant_id: int
    ) -> Container:
        c = await self.get_container(container_id, tenant_id)
        update_data = data.model_dump(exclude_unset=True)

        if "container_type" in update_data:
            if update_data["container_type"] not in VALID_CONTAINER_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid container_type '{update_data['container_type']}'",
                )

        if "serial_number" in update_data and update_data["serial_number"] != c.serial_number:
            if update_data["serial_number"] and await self.repo.serial_exists(
                update_data["serial_number"], tenant_id, exclude_id=container_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Serial number '{update_data['serial_number']}' already exists",
                )

        for field, value in update_data.items():
            setattr(c, field, value)
        await self.db.flush()
        return c

    async def delete_container(self, container_id: int, tenant_id: int) -> None:
        c = await self.get_container(container_id, tenant_id)
        await self.repo.soft_delete(c)

    # ── Assignments ──────────────────────────────────────────────

    async def assign_to_movement(
        self, data: ContainerAssignCreate, tenant_id: int
    ) -> ContainerAssignment:
        """Affecte un contenant à un mouvement avec ses articles."""
        container = await self.get_container(data.container_id, tenant_id)
        if not container.is_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Container {data.container_id} is not available",
            )

        assignment = ContainerAssignment(
            tenant_id=tenant_id,
            container_id=data.container_id,
            movement_id=data.movement_id,
            notes=data.notes,
        )
        assignment = await self.repo.create_assignment(assignment)

        for item_data in data.items:
            item = ContainerItem(
                tenant_id=tenant_id,
                container_assignment_id=assignment.id,
                movement_item_id=item_data.movement_item_id,
                quantity=item_data.quantity,
            )
            await self.repo.create_item(item)

        container.is_available = False
        await self.db.flush()

        return await self.repo.get_assignment(assignment.id, tenant_id)

    async def list_by_movement(
        self, movement_id: int, tenant_id: int
    ) -> list[ContainerAssignment]:
        return await self.repo.list_by_movement(movement_id, tenant_id)

    async def remove_assignment(
        self, assignment_id: int, tenant_id: int
    ) -> None:
        assignment = await self.repo.get_assignment(assignment_id, tenant_id)
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assignment {assignment_id} not found",
            )
        container = await self.repo.get_by_id(assignment.container_id, tenant_id)
        if container:
            container.is_available = True
        await self.repo.delete_assignment(assignment)

    # ── Contents (contenu persistant) ────────────────────────

    async def list_contents(
        self, container_id: int, tenant_id: int
    ) -> list[ContainerContent]:
        await self.get_container(container_id, tenant_id)
        return await self.repo.list_contents(container_id, tenant_id)

    async def add_content(
        self, container_id: int, data: ContainerContentCreate, tenant_id: int
    ) -> ContainerContent:
        await self.get_container(container_id, tenant_id)
        existing = await self.repo.get_content_by_product(
            container_id, data.product_id, data.variant_id, tenant_id
        )
        if existing:
            existing.quantity += data.quantity
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        obj = ContainerContent(
            tenant_id=tenant_id,
            container_id=container_id,
            product_id=data.product_id,
            variant_id=data.variant_id,
            quantity=data.quantity,
        )
        return await self.repo.create_content(obj)

    async def update_content(
        self,
        container_id: int,
        content_id: int,
        data: ContainerContentUpdate,
        tenant_id: int,
    ) -> ContainerContent:
        await self.get_container(container_id, tenant_id)
        content = await self.repo.get_content(content_id, tenant_id)
        if not content or content.container_id != container_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Content {content_id} not found in container {container_id}",
            )
        content.quantity = data.quantity
        await self.db.flush()
        await self.db.refresh(content)
        return content

    async def remove_content(
        self, container_id: int, content_id: int, tenant_id: int
    ) -> None:
        await self.get_container(container_id, tenant_id)
        content = await self.repo.get_content(content_id, tenant_id)
        if not content or content.container_id != container_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Content {content_id} not found in container {container_id}",
            )
        await self.repo.delete_content(content)

    async def get_container_detail(
        self, container_id: int, tenant_id: int
    ) -> Container:
        c = await self.repo.get_container_with_contents(container_id, tenant_id)
        if not c:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} not found",
            )
        return c

    async def get_container_history(
        self, container_id: int, tenant_id: int
    ) -> list[ContainerAssignment]:
        await self.get_container(container_id, tenant_id)
        return await self.repo.get_container_assignments_history(
            container_id, tenant_id
        )

    async def bulk_set_contents(
        self,
        container_id: int,
        data: BulkContentRequest,
        tenant_id: int,
    ) -> list[ContainerContent]:
        await self.get_container(container_id, tenant_id)
        await self.repo.delete_all_contents(container_id, tenant_id)
        results: list[ContainerContent] = []
        for entry in data.entries:
            obj = ContainerContent(
                tenant_id=tenant_id,
                container_id=container_id,
                product_id=entry.product_id,
                variant_id=entry.variant_id,
                quantity=entry.quantity,
            )
            results.append(await self.repo.create_content(obj))
        return results
