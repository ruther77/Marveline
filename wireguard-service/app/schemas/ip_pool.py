"""Schemas Pydantic pour les pools IP WireGuard."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IpPoolCreate(BaseModel):
    """Schema de creation d'un pool IP."""

    subnet: str = Field(..., min_length=7, max_length=18, pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")
    gateway_ip: str = Field(..., min_length=7, max_length=15)
    description: Optional[str] = Field(default=None, max_length=255)


class IpPoolResponse(BaseModel):
    """Schema de reponse pour un pool IP."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    subnet: str
    gateway_ip: str
    next_ip: str
    subnet_mask: int
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IpPoolListResponse(BaseModel):
    """Schema de reponse pour la liste des pools IP."""

    items: list[IpPoolResponse]
    total: int
