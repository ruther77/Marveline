"""Schémas Pydantic — TenantSettings."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class TenantSettingsRead(BaseModel):
    company_name: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_address: Optional[str] = None
    vat_rate: float = 0.20
    hourly_rate_weekday: float = 30.0
    hourly_rate_weekend: float = 60.0
    deposit_rate: float = 0.30
    default_currency: str = "EUR"
    origin_postal_code: Optional[str] = None

    model_config = {"from_attributes": True}


class TenantSettingsUpdate(BaseModel):
    company_name: Optional[str] = Field(None, max_length=200)
    company_email: Optional[str] = Field(None, max_length=200)
    company_phone: Optional[str] = Field(None, max_length=50)
    company_address: Optional[str] = Field(None, max_length=500)
    vat_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    hourly_rate_weekday: Optional[float] = Field(None, ge=0.0)
    hourly_rate_weekend: Optional[float] = Field(None, ge=0.0)
    deposit_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    default_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    origin_postal_code: Optional[str] = Field(None, max_length=20)
