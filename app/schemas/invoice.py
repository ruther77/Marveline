"""Schemas Pydantic pour l'entité Invoice (factures)."""
from datetime import date
from typing import Optional, Literal, TYPE_CHECKING
from pydantic import Field, field_validator, computed_field, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema

# Import pour type hints seulement (évite circular imports)
if TYPE_CHECKING:
    from app.schemas.reservation import ReservationList


class InvoiceBase(BaseSchema):
    """Schema de base partagé entre Create et Update."""

    issue_date: date = Field(
        ...,
        description="Date d'émission de la facture"
    )

    due_date: date = Field(
        ...,
        description="Date d'échéance de paiement"
    )

    @model_validator(mode='after')
    def validate_dates_coherence(self):
        """Validation: due_date >= issue_date."""
        if self.due_date < self.issue_date:
            raise ValueError("due_date must be after or equal to issue_date")
        return self


class InvoiceCreate(InvoiceBase):
    """Schema pour création d'une facture.

    Le invoice_number sera généré automatiquement (Redis INCR).
    Le total_amount sera copié depuis la réservation.
    Le status sera initialisé à 'draft'.

    Example:
        {
            "reservation_id": 1,
            "issue_date": "2026-01-15",
            "due_date": "2026-01-30"
        }
    """

    reservation_id: int = Field(
        ...,
        gt=0,
        description="ID de la réservation à facturer (one-to-one)"
    )


class InvoiceUpdate(BaseSchema):
    """Schema pour mise à jour d'une facture.

    Tous les champs sont optionnels (PATCH partiel).
    reservation_id et invoice_number sont immutables.

    Example:
        {
            "status": "sent",
            "due_date": "2026-02-15"
        }
    """

    issue_date: Optional[date] = Field(
        default=None,
        description="Date d'émission"
    )

    due_date: Optional[date] = Field(
        default=None,
        description="Date d'échéance"
    )

    status: Optional[Literal["draft", "sent", "paid", "overdue", "cancelled"]] = Field(
        default=None,
        description="Statut de la facture"
    )


class AddPaymentRequest(BaseSchema):
    """Schema pour ajouter un paiement à une facture.

    Utilisé par l'endpoint POST /invoices/{id}/add-payment.

    Example:
        {
            "amount_cents": 50000,
            "payment_method": "card",
            "payment_date": "2026-01-20"
        }
    """

    amount_cents: int = Field(
        ...,
        gt=0,
        description="Montant du paiement en centimes"
    )

    payment_method: Literal["cash", "card", "transfer", "check"] = Field(
        ...,
        description="Moyen de paiement"
    )

    payment_date: date = Field(
        ...,
        description="Date du paiement"
    )


class InvoiceList(EntityResponseSchema):
    """Schema simplifié pour listes de factures."""

    reservation_id: int
    invoice_number: str
    issue_date: date
    due_date: date
    status: str
    total_amount_cents: int = Field(alias="total_amount")
    paid_amount_cents: int = Field(alias="paid_amount")

    @computed_field
    @property
    def total_amount_euros(self) -> float:
        """Montant total en euros."""
        return self.total_amount_cents / 100

    @computed_field
    @property
    def paid_amount_euros(self) -> float:
        """Montant payé en euros."""
        return self.paid_amount_cents / 100

    @computed_field
    @property
    def is_paid(self) -> bool:
        """Facture entièrement payée."""
        return self.paid_amount_cents >= self.total_amount_cents

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Facture en retard de paiement."""
        from datetime import date as date_type
        return (
            not self.is_paid
            and self.status not in ["paid", "cancelled"]
            and self.due_date < date_type.today()
        )


class InvoiceResponse(EntityResponseSchema):
    """Schema complet pour réponse détaillée d'une facture."""

    reservation_id: int
    invoice_number: str
    issue_date: date
    due_date: date
    total_amount_cents: int = Field(alias="total_amount")
    paid_amount_cents: int = Field(alias="paid_amount")
    status: Literal["draft", "sent", "paid", "overdue", "cancelled"]
    payment_method: Optional[str] = None
    payment_date: Optional[date] = None

    # Relation nested optionnelle
    reservation: Optional["ReservationList"] = None

    @computed_field
    @property
    def total_amount_euros(self) -> float:
        """Montant total en euros pour affichage."""
        return self.total_amount_cents / 100

    @computed_field
    @property
    def paid_amount_euros(self) -> float:
        """Montant payé en euros pour affichage."""
        return self.paid_amount_cents / 100

    @computed_field
    @property
    def remaining_amount_cents(self) -> int:
        """Montant restant à payer en centimes."""
        return max(0, self.total_amount_cents - self.paid_amount_cents)

    @computed_field
    @property
    def remaining_amount_euros(self) -> float:
        """Montant restant à payer en euros."""
        return self.remaining_amount_cents / 100

    @computed_field
    @property
    def is_paid(self) -> bool:
        """Facture entièrement payée."""
        return self.paid_amount_cents >= self.total_amount_cents

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """Facture en retard de paiement."""
        from datetime import date as date_type
        return (
            not self.is_paid
            and self.status not in ["paid", "cancelled"]
            and self.due_date < date_type.today()
        )

    @computed_field
    @property
    def payment_completion_percentage(self) -> float:
        """Pourcentage de paiement (0-100)."""
        if self.total_amount_cents == 0:
            return 100.0
        return min(100.0, (self.paid_amount_cents / self.total_amount_cents) * 100)

    model_config = EntityResponseSchema.model_config.copy()
    model_config["json_schema_extra"] = {
        "examples": [
            {
                "id": 1,
                "tenant_id": 1,
                "reservation_id": 1,
                "invoice_number": "INV-2026-0001",
                "issue_date": "2026-01-15",
                "due_date": "2026-01-30",
                "total_amount_cents": 50000,
                "paid_amount_cents": 50000,
                "status": "paid",
                "payment_method": "card",
                "payment_date": "2026-01-20",
                "is_active": True,
                "created_at": "2026-01-15T10:00:00Z",
                "updated_at": "2026-01-20T15:30:00Z"
            }
        ]
    }


# Résolution des forward references
from app.schemas.reservation import ReservationList
InvoiceResponse.model_rebuild()
