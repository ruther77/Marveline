"""Schemas pour le flux commandes unifié (devis + réservations + ventes)."""
from __future__ import annotations
from enum import Enum
from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel


class OrderStatus(str, Enum):
    """Statut normalisé commun aux 3 types de commandes."""
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    RETURNING = "returning"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class OrderType(str, Enum):
    DEVIS = "devis"
    RESERVATION = "reservation"
    VENTE = "vente"


class OrderItem(BaseModel):
    """Ligne normalisée dans la liste unifiée des commandes."""
    id: int
    type: OrderType
    reference: str
    customer_id: int
    customer_name: Optional[str] = None
    status: OrderStatus
    event_date: Optional[date] = None
    total_cents: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrdersListResponse(BaseModel):
    items: list[OrderItem]
    total: int
    skip: int
    limit: int


class OrderLineItem(BaseModel):
    """Ligne d'article normalisée pour le drawer de détail."""
    label: str
    quantity: int
    unit_price_cents: int
    subtotal_cents: int


class OrderDetail(BaseModel):
    """Détail complet d'une commande (devis / réservation / vente)."""
    id: int
    type: OrderType
    reference: str
    customer_id: int
    customer_name: Optional[str] = None
    status: OrderStatus
    native_status: str          # statut brut du modèle source
    event_date: Optional[date] = None
    total_cents: Optional[int] = None
    created_at: datetime
    notes: Optional[str] = None
    event_location: Optional[str] = None
    lines: list[OrderLineItem] = []
    actions: list[str] = []     # actions disponibles selon statut
