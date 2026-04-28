"""Schémas Pydantic pour les relances planifiées."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.constants import RelanceStatus


class RelanceSchedule(BaseModel):
    """Payload pour planifier une relance."""

    invoice_id: int = Field(..., gt=0, description="ID de la facture à relancer")
    scheduled_at: datetime = Field(..., description="Date/heure d'envoi planifiée")
    channel: Literal["email", "sms", "push"] = Field(
        default="email",
        description="Canal d'envoi"
    )
    message: Optional[str] = Field(
        default=None,
        description="Message personnalisé (optionnel, sinon template par défaut)"
    )


class RelanceResponse(BaseModel):
    """Réponse complète d'une relance."""

    id: int
    tenant_id: int
    invoice_id: int
    scheduled_at: datetime
    sent_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    status: str
    channel: str
    message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
