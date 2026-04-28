"""Schemas Pydantic pour la tresorerie unifiee (deposits + payments)."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class TreasuryEntry(BaseModel):
    """Entree unifiee de tresorerie (deposit ou payment)."""

    entry_type: Literal["deposit", "payment"]
    source_id: int
    amount_cents: int
    entry_date: date
    method: str | None = None
    status: str | None = None
    reference: str | None = None
    customer_name: str | None = None
    notes: str | None = None


class TreasurySummary(BaseModel):
    """KPI agreges de la tresorerie du tenant."""

    total_collected_cents: int = 0
    deposits_held_cents: int = 0
    deposits_retained_cents: int = 0
    deposits_released_cents: int = 0
    payments_total_cents: int = 0
    deposits_count: int = 0
    payments_count: int = 0
    by_method: dict[str, int] = {}
