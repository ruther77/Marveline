"""Schémas Pydantic pour les règles de pricing."""
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class PricingTierCreate(BaseModel):
    min_qty: int
    max_qty: Optional[int] = None
    unit_price_cents: int


class PricingTierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    tenant_id: int
    min_qty: int
    max_qty: Optional[int] = None
    unit_price_cents: int


class PricingRuleCreate(BaseModel):
    name: str
    rule_type: str  # flat | per_day | tiered | volume | seasonal | custom
    applies_to: str  # product | category | all
    target_id: Optional[int] = None
    discount_pct: Optional[int] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    active: bool = True
    tiers: List[PricingTierCreate] = []


class PricingRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    applies_to: Optional[str] = None
    target_id: Optional[int] = None
    discount_pct: Optional[int] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    active: Optional[bool] = None


class PricingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    rule_type: str
    applies_to: str
    target_id: Optional[int] = None
    discount_pct: Optional[int] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    active: bool
    tiers: List[PricingTierResponse] = []


class PricingSimulateRequest(BaseModel):
    """Corps de la requête POST /pricing/simulate."""

    product_id: int
    quantity: int
    rental_days: int = 1
    simulation_date: Optional[date] = None


class PricingSimulateResponse(BaseModel):
    """Résultat de simulation de prix."""

    product_id: int
    quantity: int
    rental_days: int
    base_unit_price_cents: int
    applied_rule_id: Optional[int] = None
    applied_rule_name: Optional[str] = None
    discount_pct: Optional[int] = None
    final_unit_price_cents: int
    total_cents: int
