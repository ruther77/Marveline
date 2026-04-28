"""Modèles ORM pour les événements avancés : Evenement, EventIncident, IncidentAction."""
from sqlalchemy import Column, Date, ForeignKey, Integer, JSON, String, Text, TIMESTAMP
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin


class Evenement(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Événement métier (distinct d'une réservation — peut en agréger plusieurs)."""

    __tablename__ = "evenements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reference: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    reservation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True
    )
    event_date: Mapped[Date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relations
    reservation = relationship("Reservation", backref="evenements", lazy="select")
    incidents: Mapped[list["EventIncident"]] = relationship(
        "EventIncident", back_populates="evenement", cascade="all, delete-orphan", lazy="select"
    )


class EventIncident(Base, TenantMixin):
    """Incident déclaré sur un événement."""

    __tablename__ = "event_incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("evenements.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    declared_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    declared_by: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    affected_items: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="24")
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )

    # Relations
    evenement: Mapped["Evenement"] = relationship("Evenement", back_populates="incidents")
    actions: Mapped[list["IncidentAction"]] = relationship(
        "IncidentAction", back_populates="incident", cascade="all, delete-orphan", lazy="select"
    )
    declarer = relationship("Account", foreign_keys=[declared_by], lazy="select")
    owner = relationship("Account", foreign_keys=[owner_id], lazy="select")

    @property
    def owner_name(self) -> str | None:
        if self.owner is None:
            return None
        u = self.owner
        full = f"{u.first_name or ''} {u.last_name or ''}".strip()
        return full or u.email


class IncidentAction(Base, TenantMixin):
    """Action corrective liée à un incident."""

    __tablename__ = "incident_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("event_incidents.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    assignee_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    deadline: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="todo")
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")
    updated_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default="NOW()")

    # Relations
    incident: Mapped["EventIncident"] = relationship("EventIncident", back_populates="actions")
    assignee = relationship("Account", foreign_keys=[assignee_id], lazy="select")

    @property
    def assignee_name(self) -> str | None:
        if self.assignee is None:
            return None
        u = self.assignee
        full = f"{u.first_name or ''} {u.last_name or ''}".strip()
        return full or u.email
