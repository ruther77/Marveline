"""Repository Notification."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Notification], int, int]:
        q = self.db.query(Notification).filter(Notification.tenant_id == tenant_id)
        if user_id is not None:
            q = q.filter(
                (Notification.user_id == user_id) | (Notification.user_id == None)
            )
        if unread_only:
            q = q.filter(Notification.is_read == False)

        total = q.count()
        unread_count = q.filter(Notification.is_read == False).count() if not unread_only else total

        items = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        return items, total, unread_count

    def mark_read(self, notification_id: int, tenant_id: int) -> Optional[Notification]:
        n = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.tenant_id == tenant_id)
            .first()
        )
        if n and not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
            self.db.flush()
        return n

    def mark_all_read(self, tenant_id: int, user_id: Optional[int] = None) -> int:
        q = self.db.query(Notification).filter(
            Notification.tenant_id == tenant_id,
            Notification.is_read == False,
        )
        if user_id is not None:
            q = q.filter(
                (Notification.user_id == user_id) | (Notification.user_id == None)
            )
        count = q.count()
        q.update(
            {"is_read": True, "read_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        return count

    def create(
        self,
        tenant_id: int,
        type: str,
        title: str,
        message: Optional[str] = None,
        link: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Notification:
        n = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            link=link,
        )
        self.db.add(n)
        self.db.flush()
        return n


class AsyncNotificationRepository:
    """Version async de NotificationRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def list(
        self, tenant_id: int, user_id: Optional[int] = None,
        unread_only: bool = False, skip: int = 0, limit: int = 50,
    ) -> tuple[list[Notification], int, int]:
        from sqlalchemy import select, func
        q = select(Notification).filter(Notification.tenant_id == tenant_id)
        if user_id is not None:
            q = q.filter((Notification.user_id == user_id) | (Notification.user_id == None))
        if unread_only:
            q = q.filter(Notification.is_read == False)  # noqa: E712

        total_result = await self.db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar() or 0

        unread_q = select(func.count()).select_from(
            select(Notification).filter(Notification.tenant_id == tenant_id, Notification.is_read == False).subquery()  # noqa: E712
        )
        if user_id is not None:
            unread_q = select(func.count()).select_from(
                select(Notification).filter(
                    Notification.tenant_id == tenant_id,
                    Notification.is_read == False,  # noqa: E712
                    (Notification.user_id == user_id) | (Notification.user_id == None)
                ).subquery()
            )
        unread_result = await self.db.execute(unread_q)
        unread_count = unread_result.scalar() or 0

        items_result = await self.db.execute(
            q.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        )
        return list(items_result.scalars().all()), total, unread_count

    async def mark_read(self, notification_id: int, tenant_id: int) -> Optional[Notification]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Notification).filter(Notification.id == notification_id, Notification.tenant_id == tenant_id)
        )
        n = result.scalar_one_or_none()
        if n and not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
            await self.db.flush()
        return n

    async def mark_all_read(self, tenant_id: int, user_id: Optional[int] = None) -> int:
        from sqlalchemy import select, update
        q_filter = [Notification.tenant_id == tenant_id, Notification.is_read == False]  # noqa: E712
        if user_id is not None:
            q_filter.append((Notification.user_id == user_id) | (Notification.user_id == None))
        # Count first
        count_result = await self.db.execute(
            select(Notification).filter(*q_filter)
        )
        items = list(count_result.scalars().all())
        for n in items:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
        await self.db.flush()
        return len(items)

    async def create(
        self, tenant_id: int, type: str, title: str,
        message: Optional[str] = None, link: Optional[str] = None, user_id: Optional[int] = None,
    ) -> Notification:
        n = Notification(tenant_id=tenant_id, user_id=user_id, type=type, title=title, message=message, link=link)
        self.db.add(n)
        await self.db.flush()
        await self.db.refresh(n)
        return n
