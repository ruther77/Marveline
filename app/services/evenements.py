"""Service métier pour les événements avancés."""
from datetime import date, datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evenements import Evenement, EventIncident, IncidentAction
from app.models.reservation import Reservation
from app.models.tenant_membership import TenantMembership
from app.repositories.evenements import (
    AsyncEvenementRepository,
    AsyncEventIncidentRepository,
    AsyncIncidentActionRepository,
)
from app.schemas.evenements import (
    EvenementCreate, EvenementUpdate,
    EventIncidentCreate, IncidentActionCreate,
    ConflictItem, EvenementResponse,
    EvenementReport, EvenementReportIncident,
    ReportSummary, ReservationSummary,
)
from app.core.exceptions import NotFound, BadRequest

# Machine d'état : transitions autorisées
EVENT_TRANSITIONS: dict[str, list[str]] = {
    "planned":     ["risk", "in_progress", "cancelled"],
    "risk":        ["in_progress", "cancelled"],
    "in_progress": ["incident", "returned", "cancelled"],
    "incident":    ["in_progress", "damage", "cancelled"],
    "returned":    ["damage", "closed"],
    "damage":      ["closed"],
    "cancelled":   [],
    "closed":      [],
}


async def _get_event_or_404(db: AsyncSession, tenant_id: int, event_id: int) -> Evenement:
    repo = AsyncEvenementRepository(db)
    ev = await repo.get_by_id(event_id, tenant_id)
    if not ev:
        raise NotFound(f"Événement {event_id} introuvable")
    return ev


def _transition(ev: Evenement, new_status: str) -> None:
    allowed = EVENT_TRANSITIONS.get(ev.status, [])
    if new_status not in allowed:
        raise BadRequest(
            f"Transition {ev.status} → {new_status} non autorisée. "
            f"Transitions valides : {allowed}"
        )
    ev.status = new_status


# ---------------------------------------------------------------------------
# Tenant guards
# ---------------------------------------------------------------------------

async def _validate_reservation_tenant(
    db: AsyncSession, tenant_id: int, reservation_id: int,
) -> None:
    """Vérifie que la réservation appartient au même tenant."""
    result = await db.execute(
        select(Reservation.tenant_id).where(Reservation.id == reservation_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFound(f"Réservation {reservation_id} introuvable")
    if row != tenant_id:
        raise BadRequest("Réservation n'appartient pas à ce tenant")


async def _validate_user_tenant(
    db: AsyncSession, tenant_id: int, user_id: int, label: str,
) -> None:
    """Vérifie qu'un account est membre actif du tenant (IAM v2)."""
    result = await db.execute(
        select(TenantMembership.id).where(
            TenantMembership.account_id == user_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active",
        ).limit(1)
    )
    if result.scalar_one_or_none() is None:
        raise NotFound(f"{label} {user_id} introuvable dans ce tenant")


# ---------------------------------------------------------------------------
# CRUD Evenements
# ---------------------------------------------------------------------------

async def create_evenement(db: AsyncSession, tenant_id: int, data: EvenementCreate) -> Evenement:
    if data.reservation_id is not None:
        await _validate_reservation_tenant(db, tenant_id, data.reservation_id)
    repo = AsyncEvenementRepository(db)
    ev = await repo.create(tenant_id, data.model_dump())
    await db.commit()
    return await _get_event_or_404(db, tenant_id, ev.id)


async def list_evenements(
    db: AsyncSession, tenant_id: int,
    skip: int = 0, limit: int = 50,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
) -> tuple[list[Evenement], int]:
    repo = AsyncEvenementRepository(db)
    return await repo.list(
        tenant_id, skip=skip, limit=limit, status=status,
        date_from=date_from, date_to=date_to, search=search,
    )


async def get_evenement(db: AsyncSession, tenant_id: int, event_id: int) -> Evenement:
    return await _get_event_or_404(db, tenant_id, event_id)


async def update_evenement(
    db: AsyncSession, tenant_id: int, event_id: int, data: EvenementUpdate
) -> Evenement:
    ev = await _get_event_or_404(db, tenant_id, event_id)
    repo = AsyncEvenementRepository(db)
    await repo.update(ev, data.model_dump(exclude_none=True))
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id)


# ---------------------------------------------------------------------------
# Transitions d'état
# ---------------------------------------------------------------------------

async def mark_returned(
    db: AsyncSession, tenant_id: int, event_id: int, notes: str | None = None
) -> Evenement:
    ev = await _get_event_or_404(db, tenant_id, event_id)
    _transition(ev, "returned")
    if notes:
        ev.notes = notes
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id)


async def close_evenement(
    db: AsyncSession, tenant_id: int, event_id: int, notes: str
) -> Evenement:
    ev = await _get_event_or_404(db, tenant_id, event_id)
    _transition(ev, "closed")
    ev.notes = notes
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id)


async def flag_risk(db: AsyncSession, tenant_id: int, event_id: int) -> Evenement:
    ev = await _get_event_or_404(db, tenant_id, event_id)
    _transition(ev, "risk")
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id)


async def cancel_evenement(db: AsyncSession, tenant_id: int, event_id: int) -> Evenement:
    ev = await _get_event_or_404(db, tenant_id, event_id)
    _transition(ev, "cancelled")
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id)


async def start_evenement(db: AsyncSession, tenant_id: int, event_id: int) -> Evenement:
    """Démarre un événement : planned/risk → in_progress."""
    ev = await _get_event_or_404(db, tenant_id, event_id)
    _transition(ev, "in_progress")
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

_SLA_HOURS_BY_SEVERITY: dict[str, int] = {
    "low": 72,
    "medium": 24,
    "high": 4,
    "critical": 1,
}


async def create_incident(
    db: AsyncSession,
    tenant_id: int,
    event_id: int,
    declared_by: int,
    data: EventIncidentCreate,
) -> EventIncident:
    ev = await _get_event_or_404(db, tenant_id, event_id)
    # Transition vers incident si en cours
    if ev.status == "in_progress":
        ev.status = "incident"

    if data.owner_id is not None:
        await _validate_user_tenant(db, tenant_id, data.owner_id, "Propriétaire")

    payload = data.model_dump()
    payload["sla_hours"] = _SLA_HOURS_BY_SEVERITY.get(data.severity, 24)

    inc_repo = AsyncEventIncidentRepository(db)
    inc = await inc_repo.create(tenant_id, event_id, declared_by, payload)
    await db.commit()
    hydrated = await inc_repo.get_by_id(inc.id, tenant_id)
    return hydrated or inc


async def list_incidents(
    db: AsyncSession, tenant_id: int, event_id: int
) -> list[EventIncident]:
    await _get_event_or_404(db, tenant_id, event_id)
    inc_repo = AsyncEventIncidentRepository(db)
    return await inc_repo.list_by_event(event_id, tenant_id)


async def close_action(
    db: AsyncSession,
    tenant_id: int,
    event_id: int,
    incident_id: int,
    action_id: int,
) -> IncidentAction:
    await _get_event_or_404(db, tenant_id, event_id)
    inc_repo = AsyncEventIncidentRepository(db)
    inc = await inc_repo.get_by_id(incident_id, tenant_id)
    if not inc or inc.event_id != event_id:
        raise NotFound(f"Incident {incident_id} introuvable sur l'événement {event_id}")
    action_repo = AsyncIncidentActionRepository(db)
    action = await action_repo.get_by_id(action_id, tenant_id)
    if not action or action.incident_id != incident_id:
        raise NotFound(f"Action {action_id} introuvable sur l'incident {incident_id}")
    action.status = "done"
    await db.commit()
    hydrated = await action_repo.get_by_id(action.id, tenant_id)
    return hydrated or action


# ---------------------------------------------------------------------------
# Reschedule
# ---------------------------------------------------------------------------

_RESCHEDULE_ALLOWED = frozenset({"planned", "risk"})
_REPORT_STATUSES = frozenset({"returned", "damage", "closed"})


async def _find_same_day_events(
    db: AsyncSession, tenant_id: int, event_date: date, exclude_id: int
) -> list[str]:
    """Retourne les noms des événements actifs du même tenant sur la même date."""
    result = await db.execute(
        select(Evenement.name).filter(
            Evenement.tenant_id == tenant_id,
            Evenement.event_date == event_date,
            Evenement.id != exclude_id,
            Evenement.is_active == True,  # noqa: E712
            Evenement.status.notin_(["cancelled", "closed"]),
        ).limit(5)
    )
    return list(result.scalars().all())


async def _build_reservation_summary(
    db: AsyncSession, reservation_id: int
) -> ReservationSummary | None:
    """Agrège les données de réservation pour le rapport."""
    from app.models.reservation import ReservationLine
    from app.models.customer import Customer

    res = (await db.execute(
        select(Reservation).where(Reservation.id == reservation_id)
    )).scalar_one_or_none()
    if res is None:
        return None

    lines_count = (await db.scalar(
        select(func.count()).where(ReservationLine.reservation_id == reservation_id)
    )) or 0

    customer_name: str | None = None
    cust_row = (await db.execute(
        select(Customer.first_name, Customer.last_name, Customer.company_name)
        .where(Customer.id == res.customer_id)
    )).one_or_none()
    if cust_row:
        customer_name = (
            cust_row.company_name
            or f"{cust_row.first_name or ''} {cust_row.last_name or ''}".strip()
            or None
        )

    return ReservationSummary(
        id=res.id,
        reference=res.reference,
        customer_name=customer_name,
        total_amount_cents=res.total_amount_cents,
        lines_count=lines_count,
    )


async def reschedule_evenement(
    db: AsyncSession,
    tenant_id: int,
    event_id: int,
    new_date: date,
    force: bool = False,
) -> tuple[Evenement, list[ConflictItem]]:
    """Reprogramme un événement avec détection de conflits.

    Retourne (evenement, conflicts) :
    - conflicts vide → reprogrammation appliquée
    - conflicts non vide + force=False → reprogrammation non appliquée, frontend confirme
    - conflict hard → BadRequest 400 (non contournable)
    """
    ev = await _get_event_or_404(db, tenant_id, event_id)

    if ev.status not in _RESCHEDULE_ALLOWED:
        raise BadRequest(
            f"Reprogrammation impossible depuis le statut '{ev.status}'. "
            f"Statuts autorisés : {sorted(_RESCHEDULE_ALLOWED)}"
        )

    conflicts: list[ConflictItem] = []

    # Conflit HARD : réservation liée incompatible
    if ev.reservation_id is not None:
        res_row = (await db.execute(
            select(
                Reservation.id, Reservation.reference,
                Reservation.delivery_date, Reservation.return_date,
            ).where(Reservation.id == ev.reservation_id)
        )).one_or_none()
        if res_row and not (res_row.delivery_date <= new_date <= res_row.return_date):
            conflicts.append(ConflictItem(
                type="reservation_incompatible",
                severity="hard",
                message=(
                    f"La date {new_date} est hors de la plage de livraison/retour "
                    f"[{res_row.delivery_date} → {res_row.return_date}]"
                ),
                detail={
                    "reservation_id": res_row.id,
                    "reservation_reference": res_row.reference,
                    "delivery_date": str(res_row.delivery_date),
                    "return_date": str(res_row.return_date),
                },
            ))

    # Conflit SOFT : autres événements actifs même date
    same_day = await _find_same_day_events(db, tenant_id, new_date, event_id)
    if same_day:
        conflicts.append(ConflictItem(
            type="other_event_same_date",
            severity="soft",
            message=f"{len(same_day)} autre(s) événement(s) planifié(s) le {new_date}",
            detail={"count": len(same_day), "event_names": same_day},
        ))

    hard_conflicts = [c for c in conflicts if c.severity == "hard"]
    if hard_conflicts:
        raise BadRequest(
            "Reprogrammation bloquée : " + hard_conflicts[0].message,
            details={"conflicts": [c.model_dump() for c in hard_conflicts]},
        )

    # Soft conflicts présents et pas de force → retourner sans modifier
    if conflicts and not force:
        return ev, conflicts

    ev.event_date = new_date
    await db.commit()
    return await _get_event_or_404(db, tenant_id, event_id), []


async def get_event_report(
    db: AsyncSession, tenant_id: int, event_id: int
) -> EvenementReport:
    """Génère le rapport de clôture d'un événement."""
    ev = await _get_event_or_404(db, tenant_id, event_id)

    if ev.status not in _REPORT_STATUSES:
        raise BadRequest(
            f"Rapport disponible uniquement depuis les statuts : {sorted(_REPORT_STATUSES)}"
        )

    all_actions = [a for inc in ev.incidents for a in inc.actions]

    res_summary = None
    if ev.reservation_id is not None:
        res_summary = await _build_reservation_summary(db, ev.reservation_id)

    return EvenementReport(
        evenement=EvenementResponse.model_validate(ev),
        reservation=res_summary,
        summary=ReportSummary(
            total_incidents=len(ev.incidents),
            resolved_incidents=sum(1 for i in ev.incidents if i.resolved_at is not None),
            open_incidents=sum(1 for i in ev.incidents if i.resolved_at is None),
            critical_incidents=sum(1 for i in ev.incidents if i.severity == "critical"),
            total_actions=len(all_actions),
            closed_actions=sum(1 for a in all_actions if a.status == "done"),
        ),
        incidents=[EvenementReportIncident.model_validate(i) for i in ev.incidents],
        closure_notes=ev.notes,
        generated_at=datetime.utcnow(),
    )


async def create_action_plan(
    db: AsyncSession,
    tenant_id: int,
    event_id: int,
    incident_id: int,
    actions: list[IncidentActionCreate],
) -> list[IncidentAction]:
    await _get_event_or_404(db, tenant_id, event_id)
    inc_repo = AsyncEventIncidentRepository(db)
    inc = await inc_repo.get_by_id(incident_id, tenant_id)
    if not inc or inc.event_id != event_id:
        raise NotFound(f"Incident {incident_id} introuvable sur l'événement {event_id}")

    for a in actions:
        if a.assignee_id is not None:
            await _validate_user_tenant(db, tenant_id, a.assignee_id, "Assigné")

    action_repo = AsyncIncidentActionRepository(db)
    created = await action_repo.create_many(
        tenant_id, incident_id, [a.model_dump() for a in actions]
    )
    await db.commit()
    hydrated: list[IncidentAction] = []
    for a in created:
        loaded = await action_repo.get_by_id(a.id, tenant_id)
        if loaded:
            hydrated.append(loaded)
    return hydrated
