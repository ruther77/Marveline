"""Repository async pour Container, ContainerAssignment et ContainerContent."""
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.container import (
    Container,
    ContainerAssignment,
    ContainerContent,
    ContainerItem,
)


class AsyncContainerRepository:
    """Repository contenants avec isolation multi-tenant."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_active(
        self, tenant_id: int, skip: int = 0, limit: int = 50
    ) -> tuple[list[Container], int]:
        """Liste paginée des contenants actifs."""
        base = select(Container).filter(
            Container.tenant_id == tenant_id,
            Container.is_active == True,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(Container.id).filter(
                Container.tenant_id == tenant_id,
                Container.is_active == True,  # noqa: E712
            )
        )
        total = len(count_result.all())
        result = await self.db.execute(
            base.order_by(Container.name).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, container_id: int, tenant_id: int) -> Optional[Container]:
        result = await self.db.execute(
            select(Container).filter(
                Container.id == container_id,
                Container.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_available(self, tenant_id: int) -> list[Container]:
        """Liste les contenants disponibles (non affectés)."""
        result = await self.db.execute(
            select(Container).filter(
                Container.tenant_id == tenant_id,
                Container.is_active == True,  # noqa: E712
                Container.is_available == True,  # noqa: E712
            ).order_by(Container.name)
        )
        return list(result.scalars().all())

    async def serial_exists(
        self, serial: str, tenant_id: int, exclude_id: Optional[int] = None
    ) -> bool:
        q = select(Container).filter(
            Container.serial_number == serial,
            Container.tenant_id == tenant_id,
        )
        if exclude_id:
            q = q.filter(Container.id != exclude_id)
        result = await self.db.execute(q)
        return result.scalar_one_or_none() is not None

    async def create(self, obj: Container) -> Container:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def soft_delete(self, obj: Container) -> Container:
        obj.is_active = False
        await self.db.flush()
        return obj

    # ── Assignments ──────────────────────────────────────────────

    async def get_assignment(
        self, assignment_id: int, tenant_id: int
    ) -> Optional[ContainerAssignment]:
        result = await self.db.execute(
            select(ContainerAssignment)
            .options(selectinload(ContainerAssignment.container), selectinload(ContainerAssignment.items))
            .filter(
                ContainerAssignment.id == assignment_id,
                ContainerAssignment.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_movement(
        self, movement_id: int, tenant_id: int
    ) -> list[ContainerAssignment]:
        result = await self.db.execute(
            select(ContainerAssignment)
            .options(selectinload(ContainerAssignment.container), selectinload(ContainerAssignment.items))
            .filter(
                ContainerAssignment.movement_id == movement_id,
                ContainerAssignment.tenant_id == tenant_id,
            )
        )
        return list(result.scalars().all())

    async def create_assignment(self, obj: ContainerAssignment) -> ContainerAssignment:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete_assignment(self, obj: ContainerAssignment) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def create_item(self, obj: ContainerItem) -> ContainerItem:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    # ── Contents (contenu persistant) ────────────────────────

    async def list_contents(
        self, container_id: int, tenant_id: int
    ) -> list[ContainerContent]:
        result = await self.db.execute(
            select(ContainerContent)
            .filter(
                ContainerContent.container_id == container_id,
                ContainerContent.tenant_id == tenant_id,
            )
            .order_by(ContainerContent.id)
        )
        return list(result.scalars().all())

    async def get_content(
        self, content_id: int, tenant_id: int
    ) -> Optional[ContainerContent]:
        result = await self.db.execute(
            select(ContainerContent).filter(
                ContainerContent.id == content_id,
                ContainerContent.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_content_by_product(
        self,
        container_id: int,
        product_id: int,
        variant_id: Optional[int],
        tenant_id: int,
    ) -> Optional[ContainerContent]:
        q = select(ContainerContent).filter(
            ContainerContent.container_id == container_id,
            ContainerContent.product_id == product_id,
            ContainerContent.tenant_id == tenant_id,
        )
        if variant_id is not None:
            q = q.filter(ContainerContent.variant_id == variant_id)
        else:
            q = q.filter(ContainerContent.variant_id.is_(None))
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def create_content(self, obj: ContainerContent) -> ContainerContent:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete_content(self, obj: ContainerContent) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def delete_all_contents(
        self, container_id: int, tenant_id: int
    ) -> None:
        await self.db.execute(
            delete(ContainerContent).filter(
                ContainerContent.container_id == container_id,
                ContainerContent.tenant_id == tenant_id,
            )
        )
        await self.db.flush()

    async def get_container_with_contents(
        self, container_id: int, tenant_id: int
    ) -> Optional[Container]:
        result = await self.db.execute(
            select(Container)
            .options(selectinload(Container.contents))
            .filter(
                Container.id == container_id,
                Container.tenant_id == tenant_id,
                Container.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_container_assignments_history(
        self, container_id: int, tenant_id: int
    ) -> list[ContainerAssignment]:
        result = await self.db.execute(
            select(ContainerAssignment)
            .options(
                selectinload(ContainerAssignment.items),
            )
            .filter(
                ContainerAssignment.container_id == container_id,
                ContainerAssignment.tenant_id == tenant_id,
            )
            .order_by(ContainerAssignment.created_at.desc())
        )
        return list(result.scalars().all())
