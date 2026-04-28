"""Endpoints Notifications."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, UserCompat
from app.repositories.notification import AsyncNotificationRepository
from app.schemas.notification import NotificationList, NotificationRead
from app.schemas.common import PaginationParams
from app.core.exceptions import NotFound

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def list_notifications(
    pagination: PaginationParams = Depends(),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
):
    """Liste les notifications de l'utilisateur courant."""
    repo = AsyncNotificationRepository(db)
    items, total, unread_count = await repo.list(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return NotificationList(
        items=[NotificationRead.model_validate(n) for n in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
):
    """Marque une notification comme lue."""
    repo = AsyncNotificationRepository(db)
    n = await repo.mark_read(notification_id, current_user.tenant_id)
    if n is None:
        raise NotFound("Notification non trouvée")
    await db.commit()
    return NotificationRead.model_validate(n)


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
):
    """Marque toutes les notifications non lues comme lues."""
    repo = AsyncNotificationRepository(db)
    count = await repo.mark_all_read(current_user.tenant_id, current_user.id)
    await db.commit()
    return {"marked_read": count}
