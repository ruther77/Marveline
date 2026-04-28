"""Service metier pour les categories."""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.category import Category
from app.repositories.category import AsyncCategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryTreeNode
from app.constants import ErrorMessages
from app.utils import slugify


class CategoryService:
    """Service metier pour gestion des categories hierarchiques."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AsyncCategoryRepository(db)

    async def list_categories(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        parent_id: Optional[int] = None,
        include_inactive: bool = False,
    ) -> tuple[list[Category], int]:
        """Liste les categories avec filtres et pagination."""
        q = select(Category).filter(Category.tenant_id == tenant_id)
        if not include_inactive:
            q = q.filter(Category.is_active == True)  # noqa: E712
        if parent_id is not None:
            q = q.filter(Category.parent_id == parent_id)

        count_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = count_result.scalar() or 0

        q = q.order_by(Category.display_order, Category.name).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def get_category(self, category_id: int, tenant_id: int) -> Category:
        """Récupère une categorie par ID.

        Raises:
            HTTPException 404: Si categorie non trouvée.
        """
        category = await self.repo.get_by_id(category_id, tenant_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CATEGORY_NOT_FOUND,
            )
        return category

    async def create_category(self, data: CategoryCreate, tenant_id: int) -> Category:
        """Cree une nouvelle categorie.

        Auto-genere le slug depuis le name si pas fourni.
        Valide parent_id existe et meme tenant.
        """
        slug = data.slug if data.slug else slugify(data.name)

        if await self.repo.slug_exists(slug, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.CATEGORY_SLUG_EXISTS,
            )

        if await self.repo.name_exists(data.name, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.CATEGORY_NAME_EXISTS,
            )

        if data.parent_id is not None:
            parent = await self.repo.get_by_id(data.parent_id, tenant_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.CATEGORY_PARENT_NOT_FOUND,
                )

        return await self.repo.create({
            "tenant_id": tenant_id,
            "name": data.name,
            "slug": slug,
            "description": data.description,
            "parent_id": data.parent_id,
            "image_url": data.image_url,
            "display_order": data.display_order,
        })

    async def update_category(
        self, category_id: int, data: CategoryUpdate, tenant_id: int
    ) -> Category:
        """Met a jour une categorie (PATCH partiel)."""
        category = await self.repo.get_by_id(category_id, tenant_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CATEGORY_NOT_FOUND,
            )

        update_data = data.model_dump(exclude_unset=True)

        if "slug" in update_data and update_data["slug"] != category.slug:
            if await self.repo.slug_exists(update_data["slug"], tenant_id, exclude_id=category_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=ErrorMessages.CATEGORY_SLUG_EXISTS,
                )

        if "name" in update_data and update_data["name"] != category.name:
            if await self.repo.name_exists(update_data["name"], tenant_id, exclude_id=category_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=ErrorMessages.CATEGORY_NAME_EXISTS,
                )

        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id is not None:
                if new_parent_id == category_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=ErrorMessages.CATEGORY_PARENT_CYCLE,
                    )
                parent = await self.repo.get_by_id(new_parent_id, tenant_id)
                if not parent:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=ErrorMessages.CATEGORY_PARENT_NOT_FOUND,
                    )

        return await self.repo.update(category, update_data)

    async def delete_category(self, category_id: int, tenant_id: int) -> bool:
        """Soft delete une categorie. Bloque si enfants actifs."""
        category = await self.repo.get_by_id(category_id, tenant_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CATEGORY_NOT_FOUND,
            )

        if await self.repo.has_active_children(category_id, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.CATEGORY_HAS_CHILDREN,
            )

        await self.repo.soft_delete(category)
        return True

    async def get_tree(self, tenant_id: int) -> list[CategoryTreeNode]:
        """Construit l'arbre hierarchique des categories.

        Charge toutes les categories actives et construit l'arbre en memoire.
        """
        categories = await self.repo.list_all_active(tenant_id)

        product_counts: dict[str, int] = {}
        for cat in categories:
            product_counts[cat.slug] = await self.repo.count_products(cat.slug, tenant_id)

        nodes: dict[int, CategoryTreeNode] = {}
        for cat in categories:
            nodes[cat.id] = CategoryTreeNode(
                id=cat.id,
                tenant_id=cat.tenant_id,
                name=cat.name,
                slug=cat.slug,
                description=cat.description,
                parent_id=cat.parent_id,
                image_url=cat.image_url,
                display_order=cat.display_order,
                is_active=cat.is_active,
                created_at=cat.created_at,
                updated_at=cat.updated_at,
                children=[],
                product_count=product_counts.get(cat.slug, 0),
            )

        roots: list[CategoryTreeNode] = []
        for node in nodes.values():
            if node.parent_id is not None and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots
