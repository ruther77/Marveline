"""Schémas Pydantic pour SupplierOrder — Commandes fournisseurs."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

SupplierOrderStatus = Literal[
    "draft", "ordered", "partially_received", "fully_received", "cancelled"
]


# ---------------------------------------------------------------------------
# Lignes
# ---------------------------------------------------------------------------

class SupplierOrderLineCreate(BaseModel):
    product_id: int
    qty_ordered: int
    unit_cost_cents: int = 0

    @field_validator("qty_ordered")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("qty_ordered doit être > 0")
        return v

    @field_validator("unit_cost_cents")
    @classmethod
    def cost_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("unit_cost_cents doit être >= 0")
        return v


class SupplierOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: Optional[str] = None
    qty_ordered: int
    unit_cost_cents: int
    qty_received: int
    qty_remaining: int  # propriété calculée sur le modèle


# ---------------------------------------------------------------------------
# Bons de réception
# ---------------------------------------------------------------------------

class ReceiptLineInput(BaseModel):
    """Saisie d'une ligne lors d'une réception (Option B granulaire)."""
    line_id: int
    qty_received: int
    qty_damaged: int = 0
    qty_missing: int = 0
    damage_type_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("qty_received")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("qty_received doit être > 0")
        return v

    @field_validator("qty_damaged", "qty_missing")
    @classmethod
    def qty_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Les quantités ne peuvent pas être négatives")
        return v


class SupplierOrderReceiptCreate(BaseModel):
    """Corps de la requête POST /supplier-orders/{id}/receive."""
    lines: list[ReceiptLineInput]
    notes: Optional[str] = None


class SupplierOrderReceiptLineRead(BaseModel):
    """Lecture d'une ligne granulaire de bon de réception."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_id: int
    order_line_id: int
    product_id: int
    product_name: Optional[str] = None
    qty_received: int
    qty_damaged: int
    qty_missing: int
    damage_type_id: Optional[int]
    notes: Optional[str]


class SupplierOrderReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    received_at: datetime
    received_by: int
    notes: Optional[str]
    lines_json: dict
    receipt_lines: list[SupplierOrderReceiptLineRead] = []


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

class SupplierOrderCreate(BaseModel):
    supplier_id: int
    reference: str
    order_date: Optional[date] = None
    expected_date: Optional[date] = None
    notes: Optional[str] = None
    lines: list[SupplierOrderLineCreate]


class SupplierOrderUpdate(BaseModel):
    reference: Optional[str] = None
    order_date: Optional[date] = None
    expected_date: Optional[date] = None
    notes: Optional[str] = None


class SupplierOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    supplier_id: int
    reference: str
    status: SupplierOrderStatus
    order_date: Optional[date]
    expected_date: Optional[date]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    lines: list[SupplierOrderLineRead] = []
    receipts: list[SupplierOrderReceiptRead] = []


class SupplierOrderListItem(BaseModel):
    """Projection allégée pour la liste paginée."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: int
    reference: str
    status: SupplierOrderStatus
    order_date: Optional[date]
    expected_date: Optional[date]
    created_at: datetime


class SupplierOrderPage(BaseModel):
    items: list[SupplierOrderListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
