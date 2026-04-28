"""Repository pour Evenement, EventIncident, IncidentAction."""
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.evenements import Evenement, EventIncident, IncidentAction
from app.repositories.base import BaseRepository


def _gen_reference(db: Session, tenant_id: int) -> str:
    """Génère une référence unique EVT-YYYY-NNNN."""
    year = datetime.now().year
    count = db.execute(
        select(Evenement).filter(Evenement.tenant_id == tenant_id)
    ).scalars().all()
    seq = len(count) + 1
    return f"EVT-{year}-{seq:04d}"


class EvenementRepository(BaseRepository[Evenement]):

    def __init__(self, db: Session):
        super().__init__(db, Evenement)

    def create(self, tenant_id: int, data: dict) -> Evenement:
        reference = _gen_reference(self.db, tenant_id)
        ev = Evenement(
            tenant_id=tenant_id,
            reference=reference,
            name=data["name"],
            event_date=data["event_date"],
            location=data.get("location"),
            notes=data.get("notes"),
            reservation_id=data.get("reservation_id"),
            status="planned",
        )
        self.db.add(ev)
        self.db.flush()
        return ev

    def get_by_id(self, evenement_id: int, tenant_id: int) -> Optional[Evenement]:
        return self.db.execute(
            select(Evenement).filter(
                Evenement.id == evenement_id,
                Evenement.tenant_id == tenant_id,
                Evenement.is_active == True,
            )
        ).scalars().first()

    def list(self, tenant_id: int, skip: int = 0, limit: int = 50, status: Optional[str] = None) -> list[Evenement]:
        q = select(Evenement).filter(
            Evenement.tenant_id == tenant_id,
            Evenement.is_active == True,
        )
        if status:
            q = q.filter(Evenement.status == status)
        q = q.order_by(Evenement.event_date.desc()).offset(skip).limit(limit)
        return list(self.db.execute(q).scalars().all())

    def update(self, ev: Evenement, data: dict) -> Evenement:
        for field, value in data.items():
            if value is not None and hasattr(ev, field):
                setattr(ev, field, value)
        self.db.flush()
        return ev


class EventIncidentRepository(BaseRepository[EventIncident]):

    def __init__(self, db: Session):
        super().__init__(db, EventIncident)

    def create(self, tenant_id: int, event_id: int, declared_by: int, data: dict) -> EventIncident:
        inc = EventIncident(
            tenant_id=tenant_id,
            event_id=event_id,
            description=data["description"],
            severity=data["severity"],
            declared_at=data["declared_at"],
            declared_by=declared_by,
            affected_items=data.get("affected_items", []),
            sla_hours=data.get("sla_hours", 24),
            owner_id=data.get("owner_id"),
        )
        self.db.add(inc)
        self.db.flush()
        return inc

    def get_by_id(self, incident_id: int, tenant_id: int) -> Optional[EventIncident]:
        return self.db.execute(
            select(EventIncident).filter(
                EventIncident.id == incident_id,
                EventIncident.tenant_id == tenant_id,
            )
        ).scalars().first()

    def list_by_event(self, event_id: int, tenant_id: int) -> list[EventIncident]:
        return list(self.db.execute(
            select(EventIncident).filter(
                EventIncident.event_id == event_id,
                EventIncident.tenant_id == tenant_id,
            ).order_by(EventIncident.declared_at.desc())
        ).scalars().all())


class IncidentActionRepository(BaseRepository[IncidentAction]):

    def __init__(self, db: Session):
        super().__init__(db, IncidentAction)

    def get_by_id(self, action_id: int, tenant_id: int) -> Optional[IncidentAction]:
        return self.db.execute(
            select(IncidentAction).filter(
                IncidentAction.id == action_id,
                IncidentAction.tenant_id == tenant_id,
            )
        ).scalars().first()

    def create_many(self, tenant_id: int, incident_id: int, actions: list[dict]) -> list[IncidentAction]:
        created = []
        for a in actions:
            action = IncidentAction(
                tenant_id=tenant_id,
                incident_id=incident_id,
                label=a["label"],
                assignee_id=a["assignee_id"],
                deadline=a["deadline"],
                status=a.get("status", "todo"),
            )
            self.db.add(action)
            created.append(action)
        self.db.flush()
        return created


class AsyncEvenementRepository:
    """Version async de EvenementRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def _gen_reference(self, tenant_id: int) -> str:
        from datetime import datetime
        from sqlalchemy import select, func
        from app.models.evenements import Evenement
        year = datetime.now().year
        result = await self.db.execute(
            select(func.count(Evenement.id)).filter(Evenement.tenant_id == tenant_id)
        )
        seq = (result.scalar() or 0) + 1
        return f"EVT-{year}-{seq:04d}"

    async def create(self, tenant_id: int, data: dict):
        from app.models.evenements import Evenement
        reference = await self._gen_reference(tenant_id)
        ev = Evenement(
            tenant_id=tenant_id,
            reference=reference,
            name=data["name"],
            event_date=data["event_date"],
            location=data.get("location"),
            notes=data.get("notes"),
            reservation_id=data.get("reservation_id"),
            status="planned",
        )
        self.db.add(ev)
        await self.db.flush()
        await self.db.refresh(ev)
        return ev

    async def get_by_id(self, evenement_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.evenements import Evenement, EventIncident, IncidentAction
        result = await self.db.execute(
            select(Evenement)
            .options(
                selectinload(Evenement.incidents).joinedload(EventIncident.owner),
                selectinload(Evenement.incidents).joinedload(EventIncident.declarer),
                selectinload(Evenement.incidents).selectinload(EventIncident.actions).joinedload(IncidentAction.assignee),
            )
            .filter(
                Evenement.id == evenement_id,
                Evenement.tenant_id == tenant_id,
                Evenement.is_active == True,  # noqa: E712
            )
        )
        return result.unique().scalar_one_or_none()

    async def list(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        date_from: "date | None" = None,
        date_to: "date | None" = None,
        search: str | None = None,
    ) -> tuple[list, int]:
        from sqlalchemy import select, or_, func
        from app.models.evenements import Evenement
        q = select(Evenement).filter(
            Evenement.tenant_id == tenant_id,
            Evenement.is_active == True,  # noqa: E712
        )
        if status:
            q = q.filter(Evenement.status == status)
        if date_from:
            q = q.filter(Evenement.event_date >= date_from)
        if date_to:
            q = q.filter(Evenement.event_date <= date_to)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                or_(
                    Evenement.name.ilike(pattern),
                    Evenement.reference.ilike(pattern),
                    Evenement.location.ilike(pattern),
                )
            )
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.scalar(count_q)) or 0
        q = q.order_by(Evenement.event_date.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def update(self, ev, data: dict):
        for field, value in data.items():
            if value is not None and hasattr(ev, field):
                setattr(ev, field, value)
        await self.db.flush()
        return ev


class AsyncEventIncidentRepository:
    """Version async de EventIncidentRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def create(self, tenant_id: int, event_id: int, declared_by: int, data: dict):
        from app.models.evenements import EventIncident
        inc = EventIncident(
            tenant_id=tenant_id,
            event_id=event_id,
            description=data["description"],
            severity=data["severity"],
            declared_at=data["declared_at"],
            declared_by=declared_by,
            affected_items=data.get("affected_items", []),
            sla_hours=data.get("sla_hours", 24),
            owner_id=data.get("owner_id"),
        )
        self.db.add(inc)
        await self.db.flush()
        await self.db.refresh(inc)
        return inc

    async def get_by_id(self, incident_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.evenements import EventIncident, IncidentAction
        result = await self.db.execute(
            select(EventIncident)
            .options(
                joinedload(EventIncident.owner),
                joinedload(EventIncident.declarer),
                selectinload(EventIncident.actions).joinedload(IncidentAction.assignee),
            )
            .filter(
                EventIncident.id == incident_id,
                EventIncident.tenant_id == tenant_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def list_by_event(self, event_id: int, tenant_id: int) -> list:
        from sqlalchemy import select
        from app.models.evenements import EventIncident, IncidentAction
        result = await self.db.execute(
            select(EventIncident)
            .options(
                joinedload(EventIncident.owner),
                joinedload(EventIncident.declarer),
                selectinload(EventIncident.actions).joinedload(IncidentAction.assignee),
            )
            .filter(EventIncident.event_id == event_id, EventIncident.tenant_id == tenant_id)
            .order_by(EventIncident.declared_at.desc())
        )
        return list(result.unique().scalars().all())


class AsyncIncidentActionRepository:
    """Version async de IncidentActionRepository pour FastAPI."""

    def __init__(self, db):
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def get_by_id(self, action_id: int, tenant_id: int):
        from sqlalchemy import select
        from app.models.evenements import IncidentAction
        result = await self.db.execute(
            select(IncidentAction)
            .options(joinedload(IncidentAction.assignee))
            .filter(
                IncidentAction.id == action_id,
                IncidentAction.tenant_id == tenant_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def create_many(self, tenant_id: int, incident_id: int, actions: list[dict]) -> list:
        from app.models.evenements import IncidentAction
        created = []
        for a in actions:
            action = IncidentAction(
                tenant_id=tenant_id,
                incident_id=incident_id,
                label=a["label"],
                assignee_id=a["assignee_id"],
                deadline=a["deadline"],
                status=a.get("status", "todo"),
            )
            self.db.add(action)
            created.append(action)
        await self.db.flush()
        return created
