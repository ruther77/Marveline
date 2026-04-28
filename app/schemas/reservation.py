"""Schemas Pydantic pour Reservation et ReservationLine."""
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from pydantic import Field, field_validator, computed_field, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.constants import ReservationStatus

# Import pour type hints seulement (évite circular imports)
if TYPE_CHECKING:
    from app.schemas.customer import CustomerList
    from app.schemas.product import ProductList


class ReservationLineBase(BaseSchema):
    """Schema de base pour une ligne de réservation."""

    product_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID du produit réservé (NULL si ligne bundle)"
    )

    bundle_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID du bundle réservé (NULL si ligne produit)"
    )

    quantity: int = Field(
        ...,
        gt=0,
        description="Quantité réservée"
    )

    unit_price_cents: int = Field(
        ...,
        ge=0,
        description="Prix unitaire par jour en centimes (snapshot)"
    )

    @computed_field
    @property
    def subtotal_cents(self) -> int:
        """Sous-total en centimes (quantity × unit_price)."""
        return self.quantity * self.unit_price_cents


class ReservationLineCreate(BaseSchema):
    """Schema pour création d'une ligne de réservation.

    Note: unit_price_cents sera automatiquement récupéré depuis le produit.

    Example:
        {
            "product_id": 1,
            "quantity": 50,
            "variant_id": 3
        }
    """

    product_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID du produit à réserver (XOR avec bundle_id)"
    )

    bundle_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID du bundle à réserver (XOR avec product_id)"
    )

    quantity: int = Field(
        ...,
        gt=0,
        description="Quantité à réserver"
    )

    variant_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la variante (obligatoire quand product_id est fourni)"
    )

    @model_validator(mode="after")
    def product_xor_bundle(self) -> "ReservationLineCreate":
        if self.product_id is None and self.bundle_id is None:
            raise ValueError("product_id ou bundle_id requis (exactement un des deux)")
        if self.product_id is not None and self.bundle_id is not None:
            raise ValueError("product_id et bundle_id sont mutuellement exclusifs")
        # variant_id optionnel — auto-résolu côté service si produit mono-variante
        return self


class ReservationLineResponse(EntityResponseSchema):
    """Schema complet pour réponse d'une ligne de réservation."""

    reservation_id: int
    product_id: Optional[int] = None
    bundle_id: Optional[int] = None
    variant_id: Optional[int] = None
    quantity: int
    unit_price_cents: int
    subtotal_cents: int

    # Relations nested optionnelles
    product: Optional["ProductList"] = None
    bundle: Optional["BundleWithItems"] = None
    variant: Optional["ProductVariantNested"] = None

    @computed_field
    @property
    def unit_price_euros(self) -> float:
        """Prix unitaire en euros pour affichage."""
        return self.unit_price_cents / 100

    @computed_field
    @property
    def subtotal_euros(self) -> float:
        """Sous-total en euros pour affichage."""
        return self.subtotal_cents / 100


class ReservationBase(BaseSchema):
    """Schema de base partagé entre Create et Update."""

    customer_id: int = Field(
        ...,
        gt=0,
        description="ID du client"
    )

    event_date: date = Field(
        ...,
        description="Date de l'événement"
    )

    delivery_date: date = Field(
        ...,
        description="Date de livraison"
    )

    return_date: date = Field(
        ...,
        description="Date de retour"
    )

    event_location: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Lieu de l'événement"
    )

    event_type: Optional[str] = Field(
        default=None,
        description="Type d'événement (mariage, anniversaire, entreprise, autre)"
    )

    event_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Nom de l'événement"
    )

    guest_count: Optional[int] = Field(
        default=None,
        gt=0,
        description="Nombre d'invités (doit être > 0)"
    )

    @model_validator(mode='after')
    def validate_dates_coherence(self):
        """Validation cohérence des dates.

        Rules:
            - delivery_date <= event_date
            - return_date >= event_date
            - return_date >= delivery_date
        """
        if self.delivery_date > self.event_date:
            raise ValueError("delivery_date must be before or equal to event_date")
        if self.return_date < self.event_date:
            raise ValueError("return_date must be after or equal to event_date")
        if self.return_date < self.delivery_date:
            raise ValueError("return_date must be after or equal to delivery_date")
        return self


class ReservationCreate(ReservationBase):
    """Schema pour création d'une réservation.

    Le reference sera généré automatiquement côté service (Redis INCR).
    Le status sera initialisé à 'draft'.
    Les montants seront calculés depuis les lignes.

    Example:
        {
            "customer_id": 1,
            "event_date": "2026-06-15",
            "delivery_date": "2026-06-14",
            "return_date": "2026-06-16",
            "event_location": "Château de Versailles",
            "delivery_method": "self",
            "delivery_zone_id": 1,
            "lines": [
                {"product_id": 1, "quantity": 50},
                {"product_id": 2, "quantity": 100}
            ]
        }
    """

    lines: list[ReservationLineCreate] = Field(
        ...,
        min_length=1,
        description="Lignes de réservation (au moins une)"
    )

    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Notes libres sur la réservation"
    )

    delivery_zone_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la zone de livraison"
    )

    delivery_method: Optional[str] = Field(
        default=None,
        description="Méthode : self, carrier, pickup"
    )

    delivery_fee_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Frais de livraison en centimes (saisie manuelle si carrier)"
    )

    delivery_instructions: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Instructions de livraison"
    )

    carrier_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du transporteur (si carrier)"
    )

    carrier_code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Code transporteur Boxtal (si carrier)"
    )

    delivery_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse de livraison (rue, numéro)"
    )

    delivery_city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Ville de livraison"
    )

    delivery_postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal de livraison"
    )

    @field_validator('lines')
    @classmethod
    def lines_not_empty(cls, v: list) -> list:
        """Validation qu'il y a au moins une ligne."""
        if not v:
            raise ValueError("At least one reservation line is required")
        return v


class ReservationUpdate(BaseSchema):
    """Schema pour mise à jour d'une réservation.

    Tous les champs sont optionnels (PATCH partiel).
    customer_id et reference sont immutables.
    Les lignes ne peuvent pas être modifiées via update (utiliser endpoints dédiés).

    Example:
        {
            "event_date": "2026-06-20",
            "delivery_date": "2026-06-19",
            "event_location": "Palais de Tokyo"
        }
    """

    event_date: Optional[date] = Field(
        default=None,
        description="Date de l'événement"
    )

    delivery_date: Optional[date] = Field(
        default=None,
        description="Date de livraison"
    )

    return_date: Optional[date] = Field(
        default=None,
        description="Date de retour"
    )

    event_location: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Lieu de l'événement"
    )

    deposit_paid: Optional[bool] = Field(
        default=None,
        description="Caution payée"
    )

    event_type: Optional[str] = Field(
        default=None,
        description="Type d'événement (mariage, anniversaire, entreprise, autre)"
    )

    event_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Nom de l'événement"
    )

    guest_count: Optional[int] = Field(
        default=None,
        gt=0,
        description="Nombre d'invités (doit être > 0)"
    )

    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Notes libres sur la réservation"
    )

    delivery_zone_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="ID de la zone de livraison"
    )

    delivery_method: Optional[str] = Field(
        default=None,
        description="Méthode : self, carrier, pickup"
    )

    delivery_fee_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Frais de livraison en centimes (saisie manuelle si carrier)"
    )

    delivery_instructions: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Instructions de livraison"
    )

    carrier_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Nom du transporteur (si carrier)"
    )

    carrier_code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Code transporteur Boxtal (si carrier)"
    )

    delivery_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Adresse de livraison (rue, numéro)"
    )

    delivery_city: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Ville de livraison"
    )

    delivery_postal_code: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Code postal de livraison"
    )


class ReservationList(EntityResponseSchema):
    """Schema simplifié pour listes de réservations."""

    customer_id: int
    customer_name: Optional[str] = None
    reference: str
    event_date: date
    delivery_date: date
    return_date: date
    status: str
    total_amount_cents: int
    deposit_amount_cents: int
    deposit_paid: bool = False
    event_type: Optional[str] = None
    event_name: Optional[str] = None
    notes: Optional[str] = None
    is_archived: bool = False

    # Livraison
    delivery_method: Optional[str] = None
    delivery_fee_cents: int = 0
    delivery_postal_code: Optional[str] = None

    # Paiement — extraits de la relation invoice ORM
    payment_status: str = "none"
    invoice_status: Optional[str] = None
    paid_amount_cents: int = 0

    @model_validator(mode='wrap')
    @classmethod
    def populate_from_orm(cls, value, handler):
        """Extrait customer_name et payment_status depuis les relations ORM."""
        instance = handler(value)
        try:
            customer = getattr(value, 'customer', None)
            if customer is not None:
                instance.customer_name = getattr(customer, 'display_name', None)
        except Exception:
            pass
        try:
            invoices = getattr(value, 'invoices', None) or []
            if invoices:
                total_all = sum(inv.total_amount_cents or 0 for inv in invoices)
                paid_all = sum(inv.paid_amount_cents or 0 for inv in invoices)
                instance.invoice_status = invoices[0].status
                instance.paid_amount_cents = paid_all
                if total_all > 0 and paid_all >= total_all:
                    instance.payment_status = "paid"
                elif paid_all > 0:
                    instance.payment_status = "partial"
                else:
                    instance.payment_status = "unpaid"
            elif instance.status == "draft":
                instance.payment_status = "none"
            else:
                instance.payment_status = "unpaid"
        except Exception:
            pass
        return instance

    @computed_field
    @property
    def total_amount_euros(self) -> float:
        """Montant total en euros pour affichage."""
        return self.total_amount_cents / 100


class ReservationResponse(EntityResponseSchema):
    """Schema complet pour réponse détaillée d'une réservation."""

    customer_id: int
    reference: str
    event_date: date
    delivery_date: date
    return_date: date
    event_location: Optional[str] = None
    status: ReservationStatus
    total_amount_cents: int
    deposit_amount_cents: int
    deposit_paid: bool
    event_type: Optional[str] = None
    event_name: Optional[str] = None
    guest_count: Optional[int] = None
    notes: Optional[str] = None
    assigned_user_id: Optional[int] = None

    # Signature
    signature_url: Optional[str] = None
    signed_at: Optional[datetime] = None

    # Acompte 40% (Option B)
    advance_payment_amount_cents: Optional[int] = None
    balance_due_date: Optional[date] = None
    advance_paid_at: Optional[datetime] = None

    # Logistique (calculés depuis les lignes)
    total_weight_grams: Optional[int] = None
    total_volume_cm3: Optional[int] = None

    # Livraison
    delivery_zone_id: Optional[int] = None
    delivery_fee_cents: int = 0
    delivery_method: Optional[str] = None
    delivery_instructions: Optional[str] = None
    carrier_name: Optional[str] = None
    carrier_code: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_postal_code: Optional[str] = None

    # Archivage
    is_archived: bool = False

    # Devis source
    devis_id: Optional[int] = None

    # Relations nested
    customer: Optional["CustomerList"] = None
    lines: list[ReservationLineResponse] = Field(default_factory=list)

    # Paiement — extraits de la relation invoice ORM
    payment_status: str = "none"
    invoice_status: Optional[str] = None
    invoice_number: Optional[str] = None
    paid_amount_cents: int = 0
    remaining_amount_cents: int = 0

    @model_validator(mode='wrap')
    @classmethod
    def populate_payment_info(cls, value, handler):
        """Extrait payment_status et calcule poids/volume depuis les relations ORM."""
        instance = handler(value)
        # Note: total_weight_grams / total_volume_cm3 are computed frontend-side
        # from lines[].variant.weight_grams / product.weight_grams to avoid
        # async lazy-load deadlocks in model_validator.
        try:
            invoices = getattr(value, 'invoices', None) or []
            if invoices:
                total_all = sum(inv.total_amount_cents or 0 for inv in invoices)
                paid_all = sum(inv.paid_amount_cents or 0 for inv in invoices)
                instance.invoice_status = invoices[0].status
                instance.invoice_number = invoices[0].invoice_number
                instance.paid_amount_cents = paid_all
                instance.remaining_amount_cents = max(0, total_all - paid_all)
                if total_all > 0 and paid_all >= total_all:
                    instance.payment_status = "paid"
                elif paid_all > 0:
                    instance.payment_status = "partial"
                else:
                    instance.payment_status = "unpaid"
            elif instance.status == ReservationStatus.DRAFT:
                instance.payment_status = "none"
            else:
                instance.payment_status = "unpaid"
        except Exception:
            pass
        return instance

    @computed_field
    @property
    def total_amount_euros(self) -> float:
        """Montant total en euros pour affichage."""
        return self.total_amount_cents / 100

    @computed_field
    @property
    def deposit_amount_euros(self) -> float:
        """Montant caution en euros pour affichage."""
        return self.deposit_amount_cents / 100

    @computed_field
    @property
    def rental_days(self) -> int:
        """Nombre de jours de location (return_date - delivery_date + 1)."""
        return (self.return_date - self.delivery_date).days + 1

    @computed_field
    @property
    def advance_payment_amount_euros(self) -> Optional[float]:
        """Montant acompte 40% en euros (None si non calculé)."""
        if self.advance_payment_amount_cents is None:
            return None
        return self.advance_payment_amount_cents / 100

    @computed_field
    @property
    def delivery_fee_euros(self) -> float:
        """Frais de livraison en euros pour affichage."""
        return self.delivery_fee_cents / 100

    @computed_field
    @property
    def total_weight_kg(self) -> Optional[float]:
        """Poids total en kg pour affichage."""
        if self.total_weight_grams is None:
            return None
        return self.total_weight_grams / 1000

    @computed_field
    @property
    def total_volume_liters(self) -> Optional[float]:
        """Volume total en litres pour affichage."""
        if self.total_volume_cm3 is None:
            return None
        return self.total_volume_cm3 / 1000

    @computed_field
    @property
    def is_confirmed(self) -> bool:
        """Indique si la réservation est confirmée."""
        return self.status == ReservationStatus.CONFIRMED

    @computed_field
    @property
    def is_cancelled(self) -> bool:
        """Indique si la réservation est annulée."""
        return self.status == ReservationStatus.CANCELLED

    model_config = EntityResponseSchema.model_config.copy()
    model_config["json_schema_extra"] = {
        "examples": [
            {
                "id": 1,
                "tenant_id": 1,
                "customer_id": 1,
                "reference": "RES-2026-0001",
                "event_date": "2026-06-15",
                "delivery_date": "2026-06-14",
                "return_date": "2026-06-16",
                "event_location": "Château de Versailles",
                "status": "confirmed",
                "total_amount_cents": 50000,
                "deposit_amount_cents": 10000,
                "deposit_paid": True,
                "is_active": True,
                "created_at": "2026-01-15T10:00:00Z",
                "updated_at": "2026-01-15T10:00:00Z"
            }
        ]
    }


# ---------------------------------------------------------------------------
# Schémas réservations avancées (B2)
# ---------------------------------------------------------------------------

class ReservationRiskCreate(BaseSchema):
    type: str
    severity: str  # low | medium | high
    description: str
    blocking: bool = False


class ReservationRiskUpdate(BaseSchema):
    type: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    blocking: Optional[bool] = None
    resolved_at: Optional[datetime] = None


class ReservationRiskResponse(BaseSchema):
    id: int
    tenant_id: int
    reservation_id: int
    type: str
    severity: str
    description: str
    blocking: bool
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PreCheckItemResponse(BaseSchema):
    id: int
    tenant_id: int
    reservation_id: int
    label: str
    type: str
    checked: bool
    checked_at: Optional[datetime] = None
    checked_by: Optional[int] = None
    sort_order: int

    model_config = {"from_attributes": True}


class PreCheckItemUpdate(BaseSchema):
    checked: bool


class PreCheckItemCreate(BaseSchema):
    label: str
    type: str
    sort_order: int = 0


class ReservationExtensionCreate(BaseSchema):
    new_return_date: date
    reason: str
    extra_charge_cents: int = 0


class ReservationExtensionResponse(BaseSchema):
    id: int
    tenant_id: int
    reservation_id: int
    original_return_date: date
    new_return_date: date
    reason: str
    extra_charge_cents: int
    created_at: Optional[datetime] = None
    created_by: int

    model_config = {"from_attributes": True}


class ReservationSignatureCreate(BaseSchema):
    signature_data: str  # base64 ou URL


class ReservationAssignUser(BaseSchema):
    """Schéma pour affecter (ou désaffecter) un utilisateur à une réservation."""
    user_id: Optional[int] = None  # None = désaffectation


class CloseDisputeRequest(BaseSchema):
    """Schéma pour clôturer un litige lors du retour matériel."""
    resolution_notes: str = Field(..., description="Notes de résolution du litige")


class RemindDepositRequest(BaseSchema):
    """Schéma pour déclencher un rappel d'acompte (body optionnel, extensible)."""
    pass


class ReservationAmendRequest(BaseSchema):
    """Avenant à une réservation issue d'un devis.

    Crée une nouvelle version du devis source (snapshot pre-amend) puis
    applique les modifications périmétriques (dates, lignes) en bypassant
    le verrou ``RESERVATION_LOCKED_BY_DEVIS``.

    Tous les champs sont optionnels mais au moins un doit être renseigné.
    La raison est obligatoire (audit + notes résa).
    """
    reason: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Raison de l'avenant (apparaîtra dans les notes de la résa)",
    )
    event_date: Optional[date] = Field(
        default=None, description="Nouvelle date événement"
    )
    delivery_date: Optional[date] = Field(
        default=None, description="Nouvelle date de livraison"
    )
    return_date: Optional[date] = Field(
        default=None, description="Nouvelle date de retour"
    )
    add_lines: Optional[list[ReservationLineCreate]] = Field(
        default=None, description="Nouvelles lignes à ajouter"
    )
    remove_line_ids: Optional[list[int]] = Field(
        default=None, description="IDs de lignes à supprimer"
    )

    @model_validator(mode="after")
    def at_least_one_change(self) -> "ReservationAmendRequest":
        if not any([
            self.event_date,
            self.delivery_date,
            self.return_date,
            self.add_lines,
            self.remove_line_ids,
        ]):
            raise ValueError(
                "Avenant vide : fournir au moins un changement "
                "(dates, add_lines ou remove_line_ids)"
            )
        return self


class ReturnInspectionItemCreate(BaseSchema):
    """Constat d'inspection d'un item retourné."""
    reservation_line_id: Optional[int] = None
    label: str = Field(..., min_length=1, max_length=255)
    quantity_expected: int = Field(default=0, ge=0)
    quantity_returned: int = Field(default=0, ge=0)
    quantity_damaged: int = Field(default=0, ge=0)
    quantity_missing: int = Field(default=0, ge=0)
    condition: str = Field(default="good")
    damage_description: Optional[str] = None
    photo_url: Optional[str] = None
    charge_cents: int = Field(default=0, ge=0)

    @field_validator("condition")
    @classmethod
    def _check_condition(cls, v: str) -> str:
        if v not in ("good", "damaged", "missing", "partial"):
            raise ValueError("condition doit être good|damaged|missing|partial")
        return v


class ReturnInspectionBulkCreate(BaseSchema):
    """Bulk création des items d'inspection à la fin du retour."""
    items: list[ReturnInspectionItemCreate] = Field(..., min_length=1)


class ReturnInspectionItemResponse(BaseSchema):
    id: int
    tenant_id: int
    reservation_id: int
    reservation_line_id: Optional[int] = None
    label: str
    quantity_expected: int
    quantity_returned: int
    quantity_damaged: int
    quantity_missing: int
    condition: str
    damage_description: Optional[str] = None
    photo_url: Optional[str] = None
    charge_cents: int
    inspected_by: Optional[int] = None
    inspected_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DisputeLogCreate(BaseSchema):
    """Ajout d'une entrée d'audit dans le journal d'un litige."""
    action: str = Field(..., description="opened|note_added|charge_applied|resolved")
    description: str = Field(..., min_length=1)
    charge_cents: int = Field(default=0, ge=0)

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in ("opened", "note_added", "charge_applied", "resolved"):
            raise ValueError(
                "action doit être opened|note_added|charge_applied|resolved"
            )
        return v


class DisputeLogResponse(BaseSchema):
    id: int
    tenant_id: int
    reservation_id: int
    action: str
    description: str
    charge_cents: int
    created_by: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReservationFull(ReservationResponse):
    """Détail complet d'une réservation avec toutes les données associées.

    Hérite de ReservationResponse pour bénéficier des champs paiement
    (paid_amount_cents, remaining_amount_cents, payment_status) et du validator
    populate_payment_info qui agrège les paiements des invoices.
    Ajoute en plus les relations risks / pre_check_items / extensions.
    """
    risks: list[ReservationRiskResponse] = Field(default_factory=list)
    pre_check_items: list[PreCheckItemResponse] = Field(default_factory=list)
    extensions: list[ReservationExtensionResponse] = Field(default_factory=list)


# Résolution des forward references
from app.schemas.customer import CustomerList
from app.schemas.product import ProductList
from app.schemas.bundle import BundleWithItems
from app.schemas.product_variant import ProductVariantNested
ReservationLineResponse.model_rebuild()
ReservationResponse.model_rebuild()
