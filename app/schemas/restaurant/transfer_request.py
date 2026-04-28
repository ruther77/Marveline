"""Schemas Pydantic — TransferRequest (BACK-TRANSFER-RESTO-01).

DTO côté staff restaurant pour POST /restaurant/transferts/demander.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


# ── Lignes ───────────────────────────────────────────────────────────────────


class TransferRequestLineCreate(BaseSchema):
    designation: str = Field(..., min_length=1, max_length=200)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit: str = Field(default="kg", min_length=1, max_length=20)
    ingredient_restaurant_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class TransferRequestLineRead(BaseSchema):
    id: int
    request_id: int
    designation: str
    quantity: Decimal
    unit: str
    ingredient_restaurant_id: Optional[int] = None
    notes: Optional[str] = None


# ── Demandes ─────────────────────────────────────────────────────────────────


class TransferRequestCreate(BaseSchema):
    """Payload POST /restaurant/transferts/demander."""
    target_tenant_id: int = Field(..., gt=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    lignes: list[TransferRequestLineCreate] = Field(..., min_length=1, max_length=100)

    @field_validator('lignes')
    @classmethod
    def validate_no_duplicate_designation(
        cls, v: list[TransferRequestLineCreate]
    ) -> list[TransferRequestLineCreate]:
        seen = set()
        for ligne in v:
            key = ligne.designation.strip().lower()
            if key in seen:
                raise ValueError(f"Désignation dupliquée : {ligne.designation}")
            seen.add(key)
        return v


class TransferRequestCancel(BaseSchema):
    """Payload POST /restaurant/transferts/{id}/annuler."""
    raison: Optional[str] = Field(default=None, max_length=500)


class TransferRequestReject(BaseSchema):
    """Payload POST /epicerie/transfer-requests/{id}/rejeter."""
    raison: Optional[str] = Field(default=None, max_length=500)


class TransferRequestRead(BaseSchema):
    id: int
    tenant_id: int
    target_tenant_id: int
    status: str
    notes: Optional[str] = None
    created_by: int
    fulfilled_transfer_id: Optional[int] = None
    rejection_reason: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    lignes: list[TransferRequestLineRead]


class TransferRequestListResponse(BaseSchema):
    items: list[TransferRequestRead]
    total: int
    page: int
    per_page: int
