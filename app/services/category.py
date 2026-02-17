"""Service metier pour les categories."""
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryTreeNode
from app.constants import ErrorMessages
from app.utils import slugify


class CategoryService:
    """Service metier pour gestion des categories hierarchiques."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = CategoryRepository(db)

    def list_categories(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100,
        parent_id: Optional[int] = None,
        include_inactive: bool = False,
    ) -> tuple[list[Category], int]:
        """Liste les categories avec filtres et pagination.

        Args:
            tenant_id: ID du tenant
            skip: Offset pagination
            limit: Limite pagination
            parent_id: Filtre par categorie parente (None = tous)
            include_inactive: Inclure categories soft-deleted

        Returns:
            Tuple (items, total) où items est la liste paginée
        """
        filters = {}
        if parent_id is not None:
            filters["parent_id"] = parent_id

        return self.repo.list(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            filters=filters if filters else None,
            include_inactive=include_inactive,
        )

    def get_category(self, category_id: int, tenant_id: int) -> Category:
        """Récupère une categorie par ID.

        Args:
            category_id: ID de la categorie
            tenant_id: ID du tenant

        Returns:
            Categorie trouvée

        Raises:
            HTTPException 404: Si categorie non trouvée
        """
        category = self.repo.get_by_id(category_id, tenant_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CATEGORY_NOT_FOUND,
            )
        return category

    def create_category(self, data: CategoryCreate, tenant_id: int) -> Category:
        """Cree une nouvelle categorie.

        Auto-genere le slug depuis le name si pas fourni.
        Valide parent_id existe et meme tenant.
        """
        # Auto-generer slug si absent
        slug = data.slug if data.slug else slugify(data.name)

        # Verifier unicite slug
        if self.repo.slug_exists(slug, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.CATEGORY_SLUG_EXISTS,
            )

        # Verifier unicite nom
        if self.repo.name_exists(data.name, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.CATEGORY_NAME_EXISTS,
            )

        # Verifier parent_id si fourni
        if data.parent_id is not None:
            parent = self.repo.get_by_id(data.parent_id, tenant_id)
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.CATEGORY_PARENT_NOT_FOUND,
                )

        category = Category(
            tenant_id=tenant_id,
            name=data.name,
            slug=slug,
            description=data.description,
            parent_id=data.parent_id,
            image_url=data.image_url,
            display_order=data.display_order,
        )
        return self.repo.create(category)

    def update_category(
        self, category_id: int, data: CategoryUpdate, tenant_id: int
    ) -> Category:
        """Met a jour une categorie (PATCH partiel)."""
        category = self.repo.get_by_id(category_id, tenant_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CATEGORY_NOT_FOUND,
            )

        update_data = data.model_dump(exclude_unset=True)

        # Verifier unicite slug si change
        if "slug" in update_data and update_data["slug"] != category.slug:
            if self.repo.slug_exists(update_data["slug"], tenant_id, exclude_id=category_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.CATEGORY_SLUG_EXISTS,
                )

        # Verifier unicite nom si change
        if "name" in update_data and update_data["name"] != category.name:
            if self.repo.name_exists(update_data["name"], tenant_id, exclude_id=category_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.CATEGORY_NAME_EXISTS,
                )

        # Verifier parent_id pas = self (cycle)
        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id is not None:
                if new_parent_id == category_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=ErrorMessages.CATEGORY_PARENT_CYCLE,
                    )
                parent = self.repo.get_by_id(new_parent_id, tenant_id)
                if not parent:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=ErrorMessages.CATEGORY_PARENT_NOT_FOUND,
                    )

        for field, value in update_data.items():
            setattr(category, field, value)

        return self.repo.update(category)

    def delete_category(
        self, category_id: int, tenant_id: int
    ) -> bool:
        """Soft delete une categorie. Bloque si enfants actifs."""
        category = self.repo.get_by_id(category_id, tenant_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.CATEGORY_NOT_FOUND,
            )

        if self.repo.has_active_children(category_id, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.CATEGORY_HAS_CHILDREN,
            )

        return self.repo.soft_delete(category_id, tenant_id)

    def get_tree(self, tenant_id: int) -> list[CategoryTreeNode]:
        """Construit l'arbre hierarchique des categories.

        Charge toutes les categories actives et construit l'arbre en memoire.
        """
        categories = self.repo.list_all_active(tenant_id)

        # Compter les produits par slug
        product_counts: dict[str, int] = {}
        for cat in categories:
            product_counts[cat.slug] = self.repo.count_products(cat.slug, tenant_id)

        # Construire dict id -> node
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

        # Assembler arbre
        roots: list[CategoryTreeNode] = []
        for node in nodes.values():
            if node.parent_id is not None and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots
