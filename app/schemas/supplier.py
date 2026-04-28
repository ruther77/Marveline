"""Schémas Pydantic pour les fournisseurs."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class SupplierCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    is_active: bool
