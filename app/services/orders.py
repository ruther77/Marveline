"""Service agrégateur commandes unifiées (devis + réservations + ventes)."""
from __future__ import annotations
from datetime import date
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.devis import Devis
from app.models.reservation import Reservation
from app.models.vente import Vente
from app.models.customer import Customer
from app.schemas.orders import (
    OrderItem, OrderType, OrderStatus,
    OrderDetail, OrderLineItem,
)
from app.schemas.common import PaginatedResponse

# ─── Mapping des statuts vers OrderStatus ────────────────────────────────────

_DEVIS_STATUS_MAP: dict[str, OrderStatus] = {
    "draft":            OrderStatus.DRAFT,
    "sent":             OrderStatus.SENT,
    "negotiation":      OrderStatus.SENT,
    "version_pending":  OrderStatus.SENT,
    "accepted":         OrderStatus.ACCEPTED,
    "converted":        OrderStatus.CONFIRMED,
    "refused":          OrderStatus.CANCELLED,
    "expired":          OrderStatus.CANCELLED,
    "cancelled":        OrderStatus.CANCELLED,
}

_RESERVATION_STATUS_MAP: dict[str, OrderStatus] = {
    "draft":                    OrderStatus.DRAFT,
    "incomplete":               OrderStatus.DRAFT,
    "confirmed":                OrderStatus.CONFIRMED,
    "confirmed_no_deposit":     OrderStatus.CONFIRMED,
    "confirmed_with_deposit":   OrderStatus.CONFIRMED,
    "confirmed_risk":           OrderStatus.CONFIRMED,
    "pre_check":                OrderStatus.CONFIRMED,
    "delivered":                OrderStatus.IN_PROGRESS,
    "in_progress":              OrderStatus.IN_PROGRESS,
    "extended":                 OrderStatus.IN_PROGRESS,
    "returned":                 OrderStatus.RETURNING,
    "returned_dispute":         OrderStatus.RETURNING,
    "completed":                OrderStatus.CLOSED,
    "cancelled":                OrderStatus.CANCELLED,
}

_VENTE_STATUS_MAP: dict[str, OrderStatus] = {
    "draft":        OrderStatus.DRAFT,
    "pending":      OrderStatus.CONFIRMED,
    "deposit_paid": OrderStatus.CONFIRMED,
    "fully_paid":   OrderStatus.CLOSED,
    "overdue":      OrderStatus.IN_PROGRESS,
    "refunded":     OrderStatus.CANCELLED,
}

# ─── Actions disponibles par statut ──────────────────────────────────────────

_DEVIS_ACTIONS: dict[str, list[str]] = {
    "draft":        ["send", "edit", "delete"],
    "sent":         ["accept", "refuse", "edit"],
    "negotiation":  ["accept", "refuse", "edit"],
    "accepted":     ["convert"],
    "converted":    ["view_reservation"],
    "refused":      [],
    "expired":      ["renew"],
    "cancelled":    [],
}

_RESERVATION_ACTIONS: dict[str, list[str]] = {
    "draft":                    ["confirm", "edit", "delete"],
    "incomplete":               ["confirm", "edit"],
    "confirmed":                ["departure", "edit", "cancel"],
    "confirmed_no_deposit":     ["departure", "edit", "cancel"],
    "confirmed_with_deposit":   ["departure", "edit", "cancel"],
    "confirmed_risk":           ["departure", "edit", "cancel"],
    "pre_check":                ["departure"],
    "in_progress":              ["return"],
    "extended":                 ["return"],
    "returned":                 ["complete"],
    "returned_dispute":         ["complete"],
    "completed":                [],
    "cancelled":                [],
}

_VENTE_ACTIONS: dict[str, list[str]] = {
    "draft":        ["confirm", "edit", "delete"],
    "pending":      ["add_payment", "cancel"],
    "deposit_paid": ["add_payment", "cancel"],
    "fully_paid":   [],
    "overdue":      ["add_payment", "refund"],
    "refunded":     [],
}


async def _customer_name(db: AsyncSession, tenant_id: int) -> dict[int, str]:
    """Charge tous les noms clients du tenant (évite N+1)."""
    rows = (await db.execute(
        select(
            Customer.id,
            Customer.customer_type,
            Customer.first_name,
            Customer.last_name,
            Customer.company_name,
        )
        .where(Customer.tenant_id == tenant_id, Customer.is_active.is_(True))
    )).all()
    result: dict[int, str] = {}
    for row in rows:
        if row.customer_type == "company":
            result[row.id] = row.company_name or "Client sans nom"
        else:
            result[row.id] = f"{row.first_name or ''} {row.last_name or ''}".strip() or "Client sans nom"
    return result


def _map_item(obj: Devis | Reservation | Vente, order_type: OrderType,
              customer_name: str | None) -> OrderItem:
    if order_type == OrderType.DEVIS:
        d = obj  # type: ignore[assignment]
        return OrderItem(
            id=d.id, type=order_type, reference=d.reference,
            customer_id=d.customer_id, customer_name=customer_name,
            status=_DEVIS_STATUS_MAP.get(d.status, OrderStatus.DRAFT),
            event_date=d.event_date, total_cents=d.total_cents, created_at=d.created_at,
        )
    elif order_type == OrderType.RESERVATION:
        r = obj  # type: ignore[assignment]
        return OrderItem(
            id=r.id, type=order_type, reference=r.reference,
            customer_id=r.customer_id, customer_name=customer_name,
            status=_RESERVATION_STATUS_MAP.get(r.status, OrderStatus.DRAFT),
            event_date=r.delivery_date, total_cents=r.total_amount_cents, created_at=r.created_at,
        )
    else:
        v = obj  # type: ignore[assignment]
        return OrderItem(
            id=v.id, type=order_type, reference=v.reference,
            customer_id=v.customer_id, customer_name=customer_name,
            status=_VENTE_STATUS_MAP.get(v.status, OrderStatus.DRAFT),
            event_date=v.payment_due_date, total_cents=v.total_cents, created_at=v.created_at,
        )


async def list_orders(
    db: AsyncSession,
    tenant_id: int,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    order_type: str | None = None,
) -> PaginatedResponse[OrderItem]:
    """Agrège devis + réservations + ventes en liste unifiée triée par created_at desc."""
    customers = await _customer_name(db, tenant_id)
    items: list[OrderItem] = []

    if order_type in (None, "devis"):
        q = select(Devis).where(Devis.tenant_id == tenant_id)
        if status:
            src = [k for k, v in _DEVIS_STATUS_MAP.items() if v.value == status]
            if src:
                q = q.where(Devis.status.in_(src))
        for d in (await db.execute(q)).scalars().all():
            items.append(_map_item(d, OrderType.DEVIS, customers.get(d.customer_id)))

    if order_type in (None, "reservation"):
        q = select(Reservation).where(Reservation.tenant_id == tenant_id)
        if status:
            src = [k for k, v in _RESERVATION_STATUS_MAP.items() if v.value == status]
            if src:
                q = q.where(Reservation.status.in_(src))
        for r in (await db.execute(q)).scalars().all():
            items.append(_map_item(r, OrderType.RESERVATION, customers.get(r.customer_id)))

    if order_type in (None, "vente"):
        q = select(Vente).where(Vente.tenant_id == tenant_id)
        if status:
            src = [k for k, v in _VENTE_STATUS_MAP.items() if v.value == status]
            if src:
                q = q.where(Vente.status.in_(src))
        for v in (await db.execute(q)).scalars().all():
            items.append(_map_item(v, OrderType.VENTE, customers.get(v.customer_id)))

    items.sort(key=lambda x: x.created_at, reverse=True)
    total = len(items)
    return PaginatedResponse[OrderItem](items=items[skip: skip + limit], total=total, skip=skip, limit=limit)


async def get_order_detail(
    db: AsyncSession,
    tenant_id: int,
    order_type: str,
    order_id: int,
) -> OrderDetail:
    """Charge le détail complet d'une commande (devis / réservation / vente)."""
    customers = await _customer_name(db, tenant_id)

    if order_type == "devis":
        d = (await db.execute(
            select(Devis)
            .where(Devis.id == order_id, Devis.tenant_id == tenant_id)
            .options(joinedload(Devis.lines))
        )).unique().scalar_one_or_none()
        if d is None:
            raise NotFound("Devis introuvable")
        lines = [
            OrderLineItem(
                label=ln.label, quantity=ln.quantity,
                unit_price_cents=ln.unit_price_cents, subtotal_cents=ln.subtotal_cents,
            )
            for ln in (d.lines or [])
        ]
        return OrderDetail(
            id=d.id, type=OrderType.DEVIS, reference=d.reference,
            customer_id=d.customer_id, customer_name=customers.get(d.customer_id),
            status=_DEVIS_STATUS_MAP.get(d.status, OrderStatus.DRAFT),
            native_status=d.status,
            event_date=d.event_date, total_cents=d.total_cents, created_at=d.created_at,
            notes=d.notes, event_location=d.event_location,
            lines=lines, actions=_DEVIS_ACTIONS.get(d.status, []),
        )

    elif order_type == "reservation":
        r = (await db.execute(
            select(Reservation)
            .where(Reservation.id == order_id, Reservation.tenant_id == tenant_id)
            .options(joinedload(Reservation.lines))
        )).unique().scalar_one_or_none()
        if r is None:
            raise NotFound("Réservation introuvable")
        lines = [
            OrderLineItem(
                label=getattr(ln, "label", None) or (
                    ln.product.name if ln.product else f"Produit #{ln.product_id}"
                ),
                quantity=ln.quantity,
                unit_price_cents=ln.unit_price_cents,
                subtotal_cents=ln.subtotal_cents,
            )
            for ln in (r.lines or [])
        ]
        return OrderDetail(
            id=r.id, type=OrderType.RESERVATION, reference=r.reference,
            customer_id=r.customer_id, customer_name=customers.get(r.customer_id),
            status=_RESERVATION_STATUS_MAP.get(r.status, OrderStatus.DRAFT),
            native_status=r.status,
            event_date=r.delivery_date, total_cents=r.total_amount_cents, created_at=r.created_at,
            notes=None, event_location=r.event_location,
            lines=lines, actions=_RESERVATION_ACTIONS.get(r.status, []),
        )

    elif order_type == "vente":
        v = (await db.execute(
            select(Vente)
            .where(Vente.id == order_id, Vente.tenant_id == tenant_id)
            .options(joinedload(Vente.lines))
        )).unique().scalar_one_or_none()
        if v is None:
            raise NotFound("Vente introuvable")
        lines = [
            OrderLineItem(
                label=ln.label, quantity=ln.quantity,
                unit_price_cents=ln.unit_price_cents, subtotal_cents=ln.subtotal_cents,
            )
            for ln in (v.lines or [])
        ]
        return OrderDetail(
            id=v.id, type=OrderType.VENTE, reference=v.reference,
            customer_id=v.customer_id, customer_name=customers.get(v.customer_id),
            status=_VENTE_STATUS_MAP.get(v.status, OrderStatus.DRAFT),
            native_status=v.status,
            event_date=v.payment_due_date, total_cents=v.total_cents, created_at=v.created_at,
            notes=v.notes, event_location=None,
            lines=lines, actions=_VENTE_ACTIONS.get(v.status, []),
        )
    else:
        raise NotFound("Type de commande invalide")
