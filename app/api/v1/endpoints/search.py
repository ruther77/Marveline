"""Endpoint recherche globale multi-module."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import get_current_user, UserCompat
from app.models.customer import Customer
from app.models.devis import Devis
from app.models.invoice import Invoice
from app.models.product import Product
from app.models.reservation import Reservation
from app.schemas.search import NavigationTarget, SearchResponse, SearchResult

router = APIRouter(prefix="/search", tags=["search"])

_VALID_TYPES = {"customer", "product", "reservation", "invoice", "devis"}


@router.get("", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    types: list[str] = Query(default=list(_VALID_TYPES)),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserCompat = Depends(get_current_user),
):
    """Recherche globale dans les clients, produits, réservations, factures et devis."""
    tenant_id = current_user.tenant_id
    pattern = f"%{q}%"
    requested = set(types) & _VALID_TYPES
    results: list[SearchResult] = []

    # Clients
    if "customer" in requested:
        rows = (await db.execute(
            select(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.is_active.is_(True),
                or_(
                    func.lower(Customer.first_name).like(func.lower(pattern)),
                    func.lower(Customer.last_name).like(func.lower(pattern)),
                    func.lower(Customer.company_name).like(func.lower(pattern)),
                    func.lower(Customer.email).like(func.lower(pattern)),
                ),
            )
            .limit(limit)
        )).scalars().all()
        for c in rows:
            results.append(SearchResult(
                type="customer",
                id=c.id,
                title=f"{c.first_name or ''} {c.last_name or ''}".strip(),
                subtitle=c.email,
                url=f"/customers/{c.id}",
                target=NavigationTarget(
                    domain="customer",
                    route_name="/_app/customers/$id/",
                    params={"id": c.id},
                ),
            ))

    # Produits
    if "product" in requested:
        rows = (await db.execute(
            select(Product)
            .where(
                Product.tenant_id == tenant_id,
                Product.is_active.is_(True),
                or_(
                    func.lower(Product.name).like(func.lower(pattern)),
                    func.lower(Product.description).like(func.lower(pattern)),
                ),
            )
            .limit(limit)
        )).scalars().all()
        for p in rows:
            results.append(SearchResult(
                type="product",
                id=p.id,
                title=p.name,
                subtitle=p.description,
                url=f"/catalogue/products/{p.id}",
                target=NavigationTarget(
                    domain="product",
                    route_name="/_app/catalogue/products/$id/",
                    params={"id": p.id},
                ),
            ))

    # Réservations
    if "reservation" in requested:
        rows = (await db.execute(
            select(Reservation)
            .where(
                Reservation.tenant_id == tenant_id,
                or_(
                    func.lower(Reservation.reference).like(func.lower(pattern)),
                    func.lower(Reservation.event_name).like(func.lower(pattern)),
                ),
            )
            .limit(limit)
        )).scalars().all()
        for r in rows:
            results.append(SearchResult(
                type="reservation",
                id=r.id,
                title=r.reference,
                subtitle=r.event_name,
                url=f"/reservations/{r.id}",
                target=NavigationTarget(
                    domain="reservation",
                    route_name="/_app/reservations/$id/",
                    params={"id": r.id},
                ),
            ))

    # Factures
    if "invoice" in requested:
        rows = (await db.execute(
            select(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                func.lower(Invoice.invoice_number).like(func.lower(pattern)),
            )
            .limit(limit)
        )).scalars().all()
        for inv in rows:
            results.append(SearchResult(
                type="invoice",
                id=inv.id,
                title=inv.invoice_number,
                subtitle=inv.status,
                url=f"/finance/invoices/{inv.id}",
                target=NavigationTarget(
                    domain="invoice",
                    route_name="/_app/finance/invoices/$id/",
                    params={"id": inv.id},
                ),
            ))

    # Devis
    if "devis" in requested:
        rows = (await db.execute(
            select(Devis)
            .where(
                Devis.tenant_id == tenant_id,
                Devis.is_active.is_(True),
                func.lower(Devis.reference).like(func.lower(pattern)),
            )
            .limit(limit)
        )).scalars().all()
        for d in rows:
            results.append(SearchResult(
                type="devis",
                id=d.id,
                title=d.reference,
                subtitle=d.status,
                url=f"/devis/{d.id}",
                target=NavigationTarget(
                    domain="devis",
                    route_name="/_app/devis/$id/",
                    params={"id": d.id},
                ),
            ))

    return SearchResponse(results=results[:limit], total=len(results), query=q)
