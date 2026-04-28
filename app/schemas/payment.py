"""Schémas Pydantic pour les paiements."""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    """Données pour créer un paiement."""
    amount_cents: int = Field(..., gt=0, description="Montant en centimes (> 0)")
    payment_method: str = Field(..., pattern="^(cash|card|transfer|check)$")
    payment_date: date
    notes: str | None = Field(default=None, max_length=500)


class PaymentRead(BaseModel):
    """Représentation complète d'un paiement."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    invoice_id: int
    amount_cents: int
    payment_method: str
    payment_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime
