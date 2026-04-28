"""Endpoints CRUD pour les contenants et affectations."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.container import (
    BulkContentRequest,
    ContainerAssignCreate,
    ContainerAssignmentResponse,
    ContainerContentCreate,
    ContainerContentResponse,
    ContainerContentUpdate,
    ContainerCreate,
    ContainerDetailResponse,
    ContainerMovementHistoryEntry,
    ContainerResponse,
    ContainerUpdate,
)
from app.services.container import ContainerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/containers", tags=["Containers"])


@router.get("", response_model=PaginatedResponse[ContainerResponse])
async def list_containers(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> PaginatedResponse[ContainerResponse]:
    """Liste paginée des contenants actifs du tenant."""
    service = ContainerService(db)
    items, total = await service.list_containers(
        current_user.tenant_id, pagination.skip, pagination.limit
    )
    return PaginatedResponse[ContainerResponse](
        items=[ContainerResponse.model_validate(c) for c in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{container_id}", response_model=ContainerResponse)
async def get_container(
    container_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> ContainerResponse:
    """Récupère un contenant par ID."""
    service = ContainerService(db)
    c = await service.get_container(container_id, current_user.tenant_id)
    return ContainerResponse.model_validate(c)


@router.post("", response_model=ContainerResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    data: ContainerCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> ContainerResponse:
    """Crée un nouveau contenant."""
    service = ContainerService(db)
    c = await service.create_container(data, current_user.tenant_id)
    await db.commit()
    await db.refresh(c)
    return ContainerResponse.model_validate(c)


@router.patch("/{container_id}", response_model=ContainerResponse)
async def update_container(
    container_id: int,
    data: ContainerUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> ContainerResponse:
    """Met à jour un contenant (PATCH partiel)."""
    service = ContainerService(db)
    c = await service.update_container(container_id, data, current_user.tenant_id)
    await db.commit()
    await db.refresh(c)
    return ContainerResponse.model_validate(c)


@router.delete("/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container(
    container_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> None:
    """Soft delete d'un contenant."""
    service = ContainerService(db)
    await service.delete_container(container_id, current_user.tenant_id)
    await db.commit()


# ── Assignments ──────────────────────────────────────────────


@router.post("/assign", response_model=ContainerAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_container(
    data: ContainerAssignCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> ContainerAssignmentResponse:
    """Affecte un contenant à un mouvement de stock."""
    service = ContainerService(db)
    assignment = await service.assign_to_movement(data, current_user.tenant_id)
    await db.commit()
    return ContainerAssignmentResponse.model_validate(assignment)


@router.get("/movement/{movement_id}", response_model=list[ContainerAssignmentResponse])
async def list_movement_containers(
    movement_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> list[ContainerAssignmentResponse]:
    """Liste les contenants affectés à un mouvement."""
    service = ContainerService(db)
    assignments = await service.list_by_movement(movement_id, current_user.tenant_id)
    return [ContainerAssignmentResponse.model_validate(a) for a in assignments]


@router.delete("/assignment/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> None:
    """Retire l'affectation d'un contenant (le rend disponible)."""
    service = ContainerService(db)
    await service.remove_assignment(assignment_id, current_user.tenant_id)
    await db.commit()


# ── Contents (contenu persistant) ────────────────────────────


@router.get("/{container_id}/detail", response_model=ContainerDetailResponse)
async def get_container_detail(
    container_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> ContainerDetailResponse:
    """Retourne un contenant avec son contenu complet."""
    service = ContainerService(db)
    c = await service.get_container_detail(container_id, current_user.tenant_id)
    contents_data = []
    total_items = 0
    for cc in c.contents:
        total_items += cc.quantity
        contents_data.append(ContainerContentResponse(
            id=cc.id,
            tenant_id=cc.tenant_id,
            container_id=cc.container_id,
            product_id=cc.product_id,
            variant_id=cc.variant_id,
            quantity=cc.quantity,
            created_at=cc.created_at,
            updated_at=cc.updated_at,
            product_name=cc.product.name if cc.product else None,
            variant_label=cc.variant.label if cc.variant else None,
        ))
    return ContainerDetailResponse(
        **ContainerResponse.model_validate(c).model_dump(),
        contents=contents_data,
        contents_count=len(contents_data),
        total_items=total_items,
    )


@router.get(
    "/{container_id}/contents",
    response_model=list[ContainerContentResponse],
)
async def list_container_contents(
    container_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> list[ContainerContentResponse]:
    """Liste le contenu persistant d'un contenant."""
    service = ContainerService(db)
    items = await service.list_contents(container_id, current_user.tenant_id)
    return [
        ContainerContentResponse(
            id=cc.id,
            tenant_id=cc.tenant_id,
            container_id=cc.container_id,
            product_id=cc.product_id,
            variant_id=cc.variant_id,
            quantity=cc.quantity,
            created_at=cc.created_at,
            updated_at=cc.updated_at,
            product_name=cc.product.name if cc.product else None,
            variant_label=cc.variant.label if cc.variant else None,
        )
        for cc in items
    ]


@router.post(
    "/{container_id}/contents",
    response_model=ContainerContentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_container_content(
    container_id: int,
    data: ContainerContentCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> ContainerContentResponse:
    """Ajoute un produit dans un contenant (upsert quantite si deja present)."""
    service = ContainerService(db)
    cc = await service.add_content(container_id, data, current_user.tenant_id)
    await db.commit()
    await db.refresh(cc)
    return ContainerContentResponse(
        id=cc.id,
        tenant_id=cc.tenant_id,
        container_id=cc.container_id,
        product_id=cc.product_id,
        variant_id=cc.variant_id,
        quantity=cc.quantity,
        created_at=cc.created_at,
        updated_at=cc.updated_at,
        product_name=cc.product.name if cc.product else None,
        variant_label=cc.variant.label if cc.variant else None,
    )


@router.patch(
    "/{container_id}/contents/{content_id}",
    response_model=ContainerContentResponse,
)
async def update_container_content(
    container_id: int,
    content_id: int,
    data: ContainerContentUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> ContainerContentResponse:
    """Met a jour la quantite d'un produit dans un contenant."""
    service = ContainerService(db)
    cc = await service.update_content(
        container_id, content_id, data, current_user.tenant_id
    )
    await db.commit()
    await db.refresh(cc)
    return ContainerContentResponse(
        id=cc.id,
        tenant_id=cc.tenant_id,
        container_id=cc.container_id,
        product_id=cc.product_id,
        variant_id=cc.variant_id,
        quantity=cc.quantity,
        created_at=cc.created_at,
        updated_at=cc.updated_at,
        product_name=cc.product.name if cc.product else None,
        variant_label=cc.variant.label if cc.variant else None,
    )


@router.delete(
    "/{container_id}/contents/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_container_content(
    container_id: int,
    content_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> None:
    """Retire un produit d'un contenant (hard delete)."""
    service = ContainerService(db)
    await service.remove_content(
        container_id, content_id, current_user.tenant_id
    )
    await db.commit()


@router.get(
    "/{container_id}/history",
    response_model=list[ContainerMovementHistoryEntry],
)
async def get_container_history(
    container_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_READ)),
) -> list[ContainerMovementHistoryEntry]:
    """Historique des mouvements impliquant ce contenant."""
    service = ContainerService(db)
    assignments = await service.get_container_history(
        container_id, current_user.tenant_id
    )
    entries = []
    for a in assignments:
        entries.append(ContainerMovementHistoryEntry(
            movement_id=a.movement_id,
            movement_type="",
            status="",
            items_summary=[
                {"quantity": item.quantity}
                for item in a.items
            ],
        ))
    return entries


@router.put(
    "/{container_id}/contents/bulk",
    response_model=list[ContainerContentResponse],
)
async def bulk_set_container_contents(
    container_id: int,
    data: BulkContentRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.STOCK_WRITE)),
) -> list[ContainerContentResponse]:
    """Remplace entierement le contenu d'un contenant (inventaire)."""
    service = ContainerService(db)
    items = await service.bulk_set_contents(
        container_id, data, current_user.tenant_id
    )
    await db.commit()
    return [
        ContainerContentResponse(
            id=cc.id,
            tenant_id=cc.tenant_id,
            container_id=cc.container_id,
            product_id=cc.product_id,
            variant_id=cc.variant_id,
            quantity=cc.quantity,
            created_at=cc.created_at,
            updated_at=cc.updated_at,
            product_name=cc.product.name if cc.product else None,
            variant_label=cc.variant.label if cc.variant else None,
        )
        for cc in items
    ]
