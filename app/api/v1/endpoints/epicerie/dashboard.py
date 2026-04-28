"""Endpoint Dashboard épicerie — GET /epicerie/dashboard."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope
from app.core.permissions import Scope
from app.schemas.epicerie.dashboard import EpicerieDashboard
from app.services.epicerie.dashboard import get_dashboard

router = APIRouter(prefix="/epicerie/dashboard", tags=["Épicerie — Dashboard"])


@router.get("", response_model=EpicerieDashboard)
async def epicerie_dashboard(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(require_scope(Scope.EPICERIE_READ)),
):
    """KPIs tableau de bord épicerie."""
    return await get_dashboard(db, current_user.tenant_id)
