"""Schémas Pydantic pour les événements avancés."""
from datetime import date, datetime
from typing import Optional, List
from pydantic import Field, field_validator
from app.schemas.base import BaseSchema, EntityResponseSchema


# ---------------------------------------------------------------------------
# Incident actions
# ---------------------------------------------------------------------------

class IncidentActionCreate(BaseSchema):
    label: str = Field(..., min_length=2, max_length=255)
    assignee_id: int = Field(..., gt=0)
    deadline: date
    status: str = Field(default="todo", pattern="^(todo|in_progress|done)$")


class IncidentActionResponse(BaseSchema):
    id: int
    tenant_id: int
    incident_id: int
    label: str
    assignee_id: int
    assignee_name: Optional[str] = None
    deadline: date
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class EventIncidentCreate(BaseSchema):
    description: str = Field(..., min_length=5)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    declared_at: datetime
    affected_items: Optional[List[int]] = Field(default_factory=list)
    owner_id: Optional[int] = None


class EventIncidentResponse(BaseSchema):
    id: int
    tenant_id: int
    event_id: int
    description: str
    severity: str
    sla_hours: int
    declared_at: datetime
    declared_by: int
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    resolved_at: Optional[datetime] = None
    affected_items: Optional[List[int]] = None
    created_at: datetime
    actions: List[IncidentActionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Événements
# ---------------------------------------------------------------------------

class EvenementCreate(BaseSchema):
    name: str = Field(..., min_length=2, max_length=255)
    event_date: date
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    reservation_id: Optional[int] = Field(default=None, gt=0)


class EvenementUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    event_date: Optional[date] = None
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    reservation_id: Optional[int] = None


class EvenementList(EntityResponseSchema):
    reference: str
    name: str
    status: str
    event_date: date
    event_location: Optional[str] = Field(default=None, validation_alias="location")
    customer_name: Optional[str] = None
    reservation_id: Optional[int] = None


class EvenementResponse(EntityResponseSchema):
    reference: str
    name: str
    status: str
    event_date: date
    event_location: Optional[str] = Field(default=None, validation_alias="location")
    notes: Optional[str] = None
    reservation_id: Optional[int] = None
    customer_name: Optional[str] = None
    incidents: List[EventIncidentResponse] = Field(default_factory=list)


class FlagRiskRequest(BaseSchema):
    notes: Optional[str] = Field(default=None, max_length=1000)


class MarkReturnedRequest(BaseSchema):
    notes: Optional[str] = Field(default=None, max_length=1000)


class CloseRequest(BaseSchema):
    notes: str = Field(..., min_length=10, max_length=2000)


# ---------------------------------------------------------------------------
# Reschedule
# ---------------------------------------------------------------------------

class ConflictItem(BaseSchema):
    type: str
    severity: str  # "hard" | "soft"
    message: str
    detail: dict = Field(default_factory=dict)


class RescheduleRequest(BaseSchema):
    new_date: date
    force: bool = False


class RescheduleResponse(BaseSchema):
    evenement: "EvenementResponse"
    conflicts: List[ConflictItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Rapport de clôture
# ---------------------------------------------------------------------------

class ReportSummary(BaseSchema):
    total_incidents: int
    resolved_incidents: int
    open_incidents: int
    critical_incidents: int
    total_actions: int
    closed_actions: int


class ReservationSummary(BaseSchema):
    id: int
    reference: str
    customer_name: Optional[str]
    total_amount_cents: int
    lines_count: int


class EvenementReportIncident(BaseSchema):
    id: int
    description: str
    severity: str
    sla_hours: int
    declared_at: datetime
    resolved_at: Optional[datetime]
    actions: List[IncidentActionResponse]

    model_config = {"from_attributes": True}


class EvenementReport(BaseSchema):
    evenement: EvenementResponse
    reservation: Optional[ReservationSummary]
    summary: ReportSummary
    incidents: List[EvenementReportIncident]
    closure_notes: Optional[str]
    generated_at: datetime
