"""Endpoints tresorerie unifiee — deposits + payments."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.schemas.common import PaginatedResponse
from app.schemas.treasury import TreasuryEntry, TreasurySummary
from app.services.treasury import TreasuryService

router = APIRouter(prefix="/treasury", tags=["treasury"])


@router.get("/entries", response_model=PaginatedResponse[TreasuryEntry])
async def list_treasury_entries(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_READ)),
    entry_type: str | None = Query(
        default=None, description="Filtrer par type (deposit/payment)"
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    method: str | None = Query(
        default=None, description="Filtrer par moyen de paiement (cash/card/transfer/check)"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[TreasuryEntry]:
    """Liste unifiee des mouvements de tresorerie (deposits + payments)."""
    service = TreasuryService(db)
    items, total = await service.get_entries(
        tenant_id=current_user.tenant_id,
        entry_type=entry_type,
        date_from=date_from,
        date_to=date_to,
        method=method,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/summary", response_model=TreasurySummary)
async def get_treasury_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_READ)),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> TreasurySummary:
    """KPI agreges de la tresorerie du tenant (deposits + payments)."""
    service = TreasuryService(db)
    return await service.get_summary(
        tenant_id=current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/export-csv")
async def export_treasury_csv(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(require_scope(Scope.INVOICES_READ)),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> StreamingResponse:
    """Export CSV de toutes les entrees de tresorerie (deposits + payments)."""
    service = TreasuryService(db)
    entries, _ = await service.get_entries(
        tenant_id=current_user.tenant_id,
        date_from=date_from,
        date_to=date_to,
        skip=0,
        limit=5000,
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Date", "Type", "Reference", "Client", "Methode",
        "Statut", "Montant (cents)", "Montant (EUR)", "Notes",
    ])
    for e in entries:
        writer.writerow([
            e.entry_date.isoformat() if e.entry_date else "",
            e.entry_type,
            e.reference or "",
            e.customer_name or "",
            e.method or "",
            e.status or "",
            e.amount_cents,
            f"{e.amount_cents / 100:.2f}",
            (e.notes or "").replace("\n", " "),
        ])

    output.seek(0)
    filename = f"tresorerie_{date_from or 'all'}_{date_to or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
