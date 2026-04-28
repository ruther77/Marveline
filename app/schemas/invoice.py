"""Schemas Pydantic pour l'entité Invoice (factures)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from pydantic import Field, field_validator, computed_field, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.constants import InvoiceStatus, PaymentMethod
from app.schemas.payment import PaymentRead

# Import pour type hints seulement (évite circular imports)
if TYPE_CHECKING:
    from app.schemas.reservation import ReservationList, ReservationResponse


class InvoiceChargeCreate(BaseSchema):
    """Schema pour créer une charge additionnelle sur une facture.

    DAMAGE : fournir amount_cents directement.
    LABOR  : fournir hours + day_type, le montant est calculé côté service.

    Example DAMAGE:
        {"charge_type": "DAMAGE", "amount_cents": 5000, "description": "Assiette cassée"}
    Example LABOR:
        {"charge_type": "LABOR", "hours": 2.5, "day_type": "weekday", "description": "Nettoyage"}
    """

    charge_type: str = Field(
        ...,
        pattern="^(DAMAGE|LABOR)$",
        description="Type de charge : DAMAGE ou LABOR"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Description de la charge"
    )
    amount_cents: Optional[int] = Field(
        default=None,
        gt=0,
        description="Montant en centimes (DAMAGE uniquement)"
    )
    hours: Optional[Decimal] = Field(
        default=None,
        gt=0,
        description="Nombre d'heures (LABOR uniquement)"
    )
    day_type: Optional[str] = Field(
        default=None,
        pattern="^(weekday|weekend|night)$",
        description="Type de jour : weekday, weekend, night (LABOR uniquement)"
    )
    damage_type_id: Optional[int] = Field(
        default=None,
        description="ID du type de dommage (optionnel)"
    )


class InvoiceChargeRead(EntityResponseSchema):
    """Schema de réponse pour une charge additionnelle."""

    invoice_id: int
    charge_type: str
    amount_cents: int
    description: str
    hours: Optional[Decimal] = None
    day_type: Optional[str] = None
    damage_type_id: Optional[int] = None

    @computed_field
    @property
    def amount_euros(self) -> float:
        """Montant en euros."""
        return self.amount_cents / 100


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
            "due_date": "2026-01-30",
            "invoice_type": "full"
        }
    """

    reservation_id: int = Field(
        ...,
        gt=0,
        description="ID de la réservation à facturer (one-to-one)"
    )

    invoice_type: Optional[str] = Field(
        default="full",
        pattern="^(full|advance|balance)$",
        description="Type de facture : full (100%), advance (40%), balance (60%)"
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

    status: Optional[InvoiceStatus] = Field(
        default=None,
        description="Statut de la facture"
    )

    total_amount: Optional[int] = Field(
        default=None,
        gt=0,
        description="Montant total en centimes (recalcul après modification des lignes)"
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

    payment_method: PaymentMethod = Field(
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
    invoice_type: str = "full"
    issue_date: date
    due_date: date
    status: str
    total_amount_cents: int
    paid_amount_cents: int
    customer_name: Optional[str] = None
    advance_rate: float = Field(default=0.4, description="Taux acompte CGV (0.4 = 40%)")
    advance_due_date: Optional[date] = Field(default=None, description="Date d'échéance de l'acompte")

    @model_validator(mode='wrap')
    @classmethod
    def populate_customer_name(cls, value, handler):
        """Extrait le nom du client et calcule advance_due_date depuis la relation ORM."""
        instance = handler(value)
        try:
            reservation = getattr(value, 'reservation', None)
            if reservation is not None:
                customer = getattr(reservation, 'customer', None)
                if customer is not None:
                    instance.customer_name = getattr(customer, 'display_name', None)
        except Exception:
            pass
        if instance.advance_due_date is None and instance.issue_date is not None:
            from datetime import timedelta
            instance.advance_due_date = instance.issue_date + timedelta(days=7)
        return instance

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
            and self.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]
            and self.due_date < date_type.today()
        )


class InvoiceResponse(EntityResponseSchema):
    """Schema complet pour réponse détaillée d'une facture."""

    reservation_id: int
    invoice_number: str
    invoice_type: str = "full"
    issue_date: date
    due_date: date
    total_amount_cents: int
    paid_amount_cents: int
    status: InvoiceStatus
    payment_method: Optional[str] = None
    payment_date: Optional[date] = None
    advance_rate: float = Field(default=0.4, description="Taux acompte CGV (0.4 = 40%)")
    advance_due_date: Optional[date] = Field(default=None, description="Date d'échéance de l'acompte")

    # Relation nested optionnelle (avec lignes incluses)
    reservation: Optional["ReservationResponse"] = None

    # Charges additionnelles
    charges: list[InvoiceChargeRead] = Field(default_factory=list)

    # Paiements enregistrés
    payments: list[PaymentRead] = Field(default_factory=list)

    # Timeline audit
    sent_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    first_reminder_sent_at: Optional[datetime] = None
    last_reminder_sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # TVA (taux capturé à la création + breakdown multi-taux)
    tva_rate: Optional[float] = None
    tva_amount_cents: Optional[int] = None
    total_ttc_cents: Optional[int] = None
    tva_breakdown: Optional[list[dict[str, Any]]] = None

    @computed_field
    @property
    def tva_amount_euros(self) -> Optional[float]:
        """Montant TVA en euros."""
        if self.tva_amount_cents is None:
            return None
        return self.tva_amount_cents / 100

    @computed_field
    @property
    def total_ttc_euros(self) -> Optional[float]:
        """Total TTC en euros."""
        if self.total_ttc_cents is None:
            return None
        return self.total_ttc_cents / 100

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
            and self.status not in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]
            and self.due_date < date_type.today()
        )

    @computed_field
    @property
    def payment_completion_percentage(self) -> float:
        """Pourcentage de paiement (0-100)."""
        if self.total_amount_cents == 0:
            return 100.0
        return min(100.0, (self.paid_amount_cents / self.total_amount_cents) * 100)

    @model_validator(mode='after')
    def _populate_advance_due_date(self):
        """Calcule advance_due_date = issue_date + 7j si absent."""
        if self.advance_due_date is None and self.issue_date is not None:
            from datetime import timedelta
            self.advance_due_date = self.issue_date + timedelta(days=7)
        return self

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
from app.schemas.reservation import ReservationList, ReservationResponse
InvoiceResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Credit Note schemas
# ---------------------------------------------------------------------------

from datetime import datetime as _datetime


class CreditNoteCreate(BaseSchema):
    """Données pour créer un avoir sur une facture."""
    amount_cents: int = Field(..., gt=0, description="Montant de l'avoir en centimes")
    reason: str = Field(..., min_length=5, max_length=1000, description="Motif de l'avoir")
    issue_date: date = Field(default_factory=date.today)


class CreditNoteResponse(BaseSchema):
    """Avoir en réponse (entité immutable — pas d'updated_at)."""
    id: int
    tenant_id: int
    original_invoice_id: int
    invoice_number: str
    amount_cents: int
    reason: str
    issue_date: date
    status: str
    created_at: _datetime

    @computed_field
    @property
    def amount_euros(self) -> float:
        return self.amount_cents / 100


class MarkSentRequest(BaseSchema):
    """Requête pour marquer une facture comme envoyée manuellement."""
    sent_at: Optional[date] = Field(default=None, description="Date d'envoi (défaut: aujourd'hui)")
    notes: Optional[str] = Field(default=None, max_length=500)


class RemindRequest(BaseSchema):
    """Requête de relance facture."""
    notes: Optional[str] = Field(default=None, max_length=500, description="Notes internes")


class DamageInvoiceCreate(BaseSchema):
    """Créer une facture de dommages liée à une réservation."""
    reservation_id: int = Field(..., gt=0)
    charges: list["InvoiceChargeCreate"] = Field(
        default_factory=list, description="Charges/dommages à facturer"
    )
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# TVA Report schemas
# ---------------------------------------------------------------------------

class TvaBreakdownItem(BaseSchema):
    """Ligne de détail TVA pour un taux donné."""
    rate: float = Field(..., description="Taux TVA (ex: 0.20 = 20%)")
    base_ht_cents: int = Field(..., description="Base HT en centimes")
    tva_cents: int = Field(..., description="Montant TVA en centimes")
    ttc_cents: int = Field(..., description="Total TTC en centimes")

    @computed_field
    @property
    def base_ht_euros(self) -> float:
        return self.base_ht_cents / 100

    @computed_field
    @property
    def tva_euros(self) -> float:
        return self.tva_cents / 100

    @computed_field
    @property
    def ttc_euros(self) -> float:
        return self.ttc_cents / 100


class TvaReportResponse(BaseSchema):
    """Rapport TVA mensuel pour déclaration."""
    month: str = Field(..., description="Mois concerné (YYYY-MM)")
    invoice_count: int = Field(..., description="Nombre de factures incluses")
    total_base_ht_cents: int = Field(..., description="Total base HT en centimes")
    total_tva_cents: int = Field(..., description="Total TVA collectée en centimes")
    total_ttc_cents: int = Field(..., description="Total TTC en centimes")
    breakdown_by_rate: list[TvaBreakdownItem] = Field(
        default_factory=list,
        description="Détail par taux de TVA"
    )

    @computed_field
    @property
    def total_base_ht_euros(self) -> float:
        return self.total_base_ht_cents / 100

    @computed_field
    @property
    def total_tva_euros(self) -> float:
        return self.total_tva_cents / 100

    @computed_field
    @property
    def total_ttc_euros(self) -> float:
        return self.total_ttc_cents / 100


class SequenceGapsResponse(BaseSchema):
    """Trous dans la séquence de numérotation des factures."""
    year: int
    gaps: list[int] = Field(default_factory=list)
    count: int
