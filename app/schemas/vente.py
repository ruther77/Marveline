"""Schemas Pydantic pour Vente, VenteLine et VentePayment."""
from datetime import date, datetime
from typing import Optional
from pydantic import Field, computed_field
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.constants import VenteStatus


class VenteLineCreate(BaseSchema):
    """Ligne de vente à créer."""
    product_id: Optional[int] = Field(default=None, gt=0)
    label: str = Field(..., max_length=255)
    quantity: int = Field(..., gt=0)
    unit_price_cents: int = Field(..., ge=0, description="Prix unitaire en centimes")


class VenteLineResponse(BaseSchema):
    """Ligne de vente en réponse (entité immutable — pas d'updated_at)."""
    id: int
    tenant_id: int
    vente_id: int
    product_id: Optional[int] = None
    label: str
    quantity: int
    unit_price_cents: int
    subtotal_cents: int
    created_at: datetime

    @computed_field
    @property
    def unit_price_euros(self) -> float:
        return self.unit_price_cents / 100

    @computed_field
    @property
    def subtotal_euros(self) -> float:
        return self.subtotal_cents / 100


class VenteCreate(BaseSchema):
    """Données pour créer une vente directe."""
    customer_id: int = Field(..., gt=0)
    deposit_pct: Optional[int] = Field(default=None, ge=0, le=100)
    payment_due_date: Optional[date] = None
    notes: Optional[str] = None
    invoice_id: Optional[int] = Field(default=None, gt=0)
    reservation_id: Optional[int] = Field(default=None, gt=0)
    lines: list[VenteLineCreate] = Field(default_factory=list)


class VenteUpdate(BaseSchema):
    """Mise à jour partielle d'une vente (PATCH)."""
    deposit_pct: Optional[int] = Field(default=None, ge=0, le=100)
    payment_due_date: Optional[date] = None
    notes: Optional[str] = None


class VentePaymentCreate(BaseSchema):
    """Enregistrer un paiement sur une vente."""
    amount_cents: int = Field(..., gt=0, description="Montant en centimes")
    payment_method: str = Field(..., max_length=30)
    payment_date: date
    is_deposit: bool = False
    notes: Optional[str] = None


class VentePaymentResponse(BaseSchema):
    """Paiement enregistré (entité immutable — pas d'updated_at)."""
    id: int
    tenant_id: int
    vente_id: int
    amount_cents: int
    payment_method: str
    payment_date: date
    is_deposit: bool
    notes: Optional[str] = None
    created_by: int
    created_at: datetime

    @computed_field
    @property
    def amount_euros(self) -> float:
        return self.amount_cents / 100


class VenteList(EntityResponseSchema):
    """Vente dans une liste."""
    reference: str
    customer_id: int
    customer_name: Optional[str] = None
    status: str
    total_cents: int
    paid_cents: int
    payment_due_date: Optional[date] = None

    @computed_field
    @property
    def total_euros(self) -> float:
        return self.total_cents / 100

    @computed_field
    @property
    def balance_cents(self) -> int:
        """Reste à payer."""
        return max(0, self.total_cents - self.paid_cents)


class VenteResponse(EntityResponseSchema):
    """Détail complet d'une vente."""
    reference: str
    customer_id: int
    status: VenteStatus
    subtotal_cents: int
    tva_cents: int
    total_cents: int
    paid_cents: int
    deposit_pct: Optional[int] = None
    payment_due_date: Optional[date] = None
    notes: Optional[str] = None
    invoice_id: Optional[int] = None
    reservation_id: Optional[int] = None
    lines: list[VenteLineResponse] = Field(default_factory=list)
    payments: list[VentePaymentResponse] = Field(default_factory=list)

    @computed_field
    @property
    def total_euros(self) -> float:
        return self.total_cents / 100

    @computed_field
    @property
    def paid_euros(self) -> float:
        return self.paid_cents / 100

    @computed_field
    @property
    def balance_cents(self) -> int:
        return max(0, self.total_cents - self.paid_cents)

    @computed_field
    @property
    def is_fully_paid(self) -> bool:
        return self.status == VenteStatus.FULLY_PAID
