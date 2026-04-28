"""Schémas Pydantic pour le module Devis."""
from datetime import date, datetime
from typing import Optional
from pydantic import Field, field_validator, computed_field, model_validator
from app.schemas.base import BaseSchema, EntityResponseSchema
from app.constants import DevisStatus

# Mapping statut → actions UI autorisées (source unique de vérité pour le frontend)
STATUS_ALLOWED_ACTIONS: dict[str, list[str]] = {
    DevisStatus.DRAFT:           ["send", "cancel"],
    DevisStatus.SENT:            ["start_negotiation", "accept", "refuse", "expire"],
    DevisStatus.NEGOTIATION:     ["accept", "refuse", "new_version", "expire"],
    DevisStatus.VERSION_PENDING: ["send", "back_to_negotiation", "accept", "refuse", "cancel"],
    DevisStatus.ACCEPTED:        ["convert", "cancel"],
    DevisStatus.REFUSED:         ["duplicate"],
    DevisStatus.EXPIRED:         ["renew"],
    DevisStatus.CONVERTED:       [],
    DevisStatus.CANCELLED:       [],
}


# ── Bundle preview ────────────────────────────────────────────────────────────


class BundleItemPreview(BaseSchema):
    """Apercu d'un item d'un bundle (pour affichage avant ajout au devis)."""
    product_id: int
    product_name: str
    product_image_url: Optional[str] = None
    variant_id: Optional[int] = None
    variant_label: Optional[str] = None
    quantity: int
    display_order: int


class BundlePreviewResponse(BaseSchema):
    """Apercu complet d'un bundle avec ses items."""
    bundle_id: int
    bundle_name: str
    bundle_image_url: Optional[str] = None
    bundle_price_cents: int
    items: list[BundleItemPreview]


# ── Lignes ───────────────────────────────────────────────────────────────────

class DevisLineCreate(BaseSchema):
    product_id: Optional[int] = None
    bundle_id: Optional[int] = None
    variant_id: Optional[int] = Field(
        default=None, gt=0,
        description="ID de la variante (auto-resolu si produit mono-variante)"
    )
    label: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., ge=1)
    unit_price_cents: int = Field(..., ge=0, description="Prix unitaire en centimes")
    discount_pct: int = Field(default=0, ge=0, description="Remise en centièmes de %")
    sort_order: int = Field(default=0, ge=0)


class DevisLineResponse(BaseSchema):
    id: int
    devis_id: int
    product_id: Optional[int] = None
    bundle_id: Optional[int] = None
    variant_id: Optional[int] = None
    label: str
    quantity: int
    unit_price_cents: int
    discount_pct: int
    subtotal_cents: int
    sort_order: int
    variant_label: Optional[str] = None
    bundle_name: Optional[str] = None
    bundle_items: Optional[list[BundleItemPreview]] = Field(
        None, description="Items du bundle (charge si bundle_id est renseigne)"
    )
    weight_grams: Optional[int] = Field(None, description="Poids unitaire produit (g)")
    volume_cm3: Optional[int] = Field(None, description="Volume unitaire produit (cm³)")
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def unit_price_euros(self) -> float:
        return self.unit_price_cents / 100

    @computed_field
    @property
    def subtotal_euros(self) -> float:
        return self.subtotal_cents / 100


# ── Historique lignes (G28) ────────────────────────────────────────────────────


class DevisLineHistoryResponse(BaseSchema):
    """Entree d'historique de modification d'une ligne de devis."""
    id: int
    devis_id: int
    devis_line_id: Optional[int] = None
    action: str
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    changed_by: Optional[int] = None
    created_at: datetime


# ── Pieces jointes (G7) ───────────────────────────────────────────────────────


class DevisAttachmentResponse(BaseSchema):
    """Reponse piece jointe devis."""
    id: int
    devis_id: int
    filename: str
    mime_type: str
    file_size: int
    uploaded_by: Optional[int] = None
    sort_order: int
    created_at: datetime


# ── Modules ──────────────────────────────────────────────────────────────────

class DevisModuleCreate(BaseSchema):
    module_type: str = Field(..., pattern="^(socle|stock|facturation|securite|services)$")
    label: str = Field(..., min_length=1, max_length=255)
    content_json: dict = Field(default_factory=dict)


class DevisModuleUpdate(BaseSchema):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    content_json: Optional[dict] = None
    delivery_status: Optional[str] = Field(None, pattern="^(a_cadrer|en_cours|livre)$")


class DevisModuleResponse(BaseSchema):
    id: int
    devis_id: int
    module_type: str
    label: str
    content_json: dict
    delivery_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Phases ───────────────────────────────────────────────────────────────────

class DevisPhaseCreate(BaseSchema):
    label: str = Field(..., min_length=1, max_length=255)
    date_start: date
    date_end: date
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_dates(self) -> "DevisPhaseCreate":
        if self.date_end < self.date_start:
            raise ValueError("date_end doit être >= date_start")
        return self


class DevisPhaseUpdate(BaseSchema):
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    sort_order: Optional[int] = Field(None, ge=0)


class DevisPhaseResponse(BaseSchema):
    id: int
    devis_id: int
    label: str
    date_start: date
    date_end: date
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Versions (snapshots immuables) ───────────────────────────────────────────

class DevisVersionResponse(BaseSchema):
    id: int
    devis_id: int
    version_number: int
    snapshot_json: dict
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime


# ── Négociations ─────────────────────────────────────────────────────────────

class DevisNegotiationCreate(BaseSchema):
    message: str = Field(..., min_length=1)
    proposed_amount_cents: Optional[int] = Field(None, ge=0)


class DevisNegotiationResponse(BaseSchema):
    id: int
    devis_id: int
    author_id: int
    message: str
    proposed_amount_cents: Optional[int] = None
    created_at: datetime


# ── Demandes de modification ──────────────────────────────────────────────────

class DevisChangeRequestCreate(BaseSchema):
    description: str = Field(..., min_length=1)


class DevisChangeRequestUpdate(BaseSchema):
    status: str = Field(..., pattern="^(pending|accepted|refused)$")


class DevisChangeRequestResponse(BaseSchema):
    id: int
    devis_id: int
    author_id: int
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


# ── Items couverture fonctionnelle ────────────────────────────────────────────

class DevisCoverageItemCreate(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="a_cadrer", pattern="^(a_cadrer|en_cours|livre)$")
    sort_order: int = Field(default=0, ge=0)


class DevisCoverageItemUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(a_cadrer|en_cours|livre)$")
    sort_order: Optional[int] = Field(None, ge=0)


class DevisCoverageItemResponse(BaseSchema):
    id: int
    devis_id: int
    tenant_id: int
    title: str
    description: Optional[str] = None
    status: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


# ── Devis principal ───────────────────────────────────────────────────────────

class DevisCreate(BaseSchema):
    customer_id: int = Field(..., gt=0)
    event_date: Optional[date] = None
    event_location: Optional[str] = Field(None, max_length=255)
    delivery_date: Optional[date] = None
    return_date: Optional[date] = None
    valid_until: date
    tva_rate: int = Field(default=2000, ge=0, description="Taux TVA en centièmes de %")
    discount_pct: Optional[int] = Field(None, ge=0)
    caution_required: bool = False
    caution_amount_cents: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    conditions_paiement: Optional[str] = Field(
        None,
        description="30_acompte | 50_50 | comptant | fin_evenement"
    )
    message_accompagnement: Optional[str] = None
    lines: list[DevisLineCreate] = Field(default_factory=list)
    # Livraison
    delivery_method: Optional[str] = Field(None, pattern="^(self|carrier|pickup)$")
    delivery_fee_cents: int = Field(default=0, ge=0)
    carrier_name: Optional[str] = Field(None, max_length=100)
    carrier_code: Optional[str] = Field(None, max_length=20)
    delivery_address: Optional[str] = Field(None, max_length=500)
    delivery_city: Optional[str] = Field(None, max_length=100)
    delivery_postal_code: Optional[str] = Field(None, max_length=10)
    delivery_zone_id: Optional[int] = Field(None, gt=0)
    delivery_instructions: Optional[str] = None

    @field_validator("valid_until")
    @classmethod
    def valid_until_future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("valid_until doit être une date future")
        return v


class DevisUpdate(BaseSchema):
    event_date: Optional[date] = None
    event_location: Optional[str] = Field(None, max_length=255)
    delivery_date: Optional[date] = None
    return_date: Optional[date] = None
    valid_until: Optional[date] = None
    tva_rate: Optional[int] = Field(None, ge=0)
    discount_pct: Optional[int] = Field(None, ge=0)
    caution_required: Optional[bool] = None
    caution_amount_cents: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    conditions_paiement: Optional[str] = None
    message_accompagnement: Optional[str] = None
    lines: Optional[list[DevisLineCreate]] = None
    # Livraison
    delivery_method: Optional[str] = Field(None, pattern="^(self|carrier|pickup)$")
    delivery_fee_cents: Optional[int] = Field(None, ge=0)
    carrier_name: Optional[str] = Field(None, max_length=100)
    carrier_code: Optional[str] = Field(None, max_length=20)
    delivery_address: Optional[str] = Field(None, max_length=500)
    delivery_city: Optional[str] = Field(None, max_length=100)
    delivery_postal_code: Optional[str] = Field(None, max_length=10)
    delivery_zone_id: Optional[int] = Field(None, gt=0)
    delivery_instructions: Optional[str] = None


class DevisConvert(BaseSchema):
    """Données requises pour convertir un devis en réservation.

    delivery_date et return_date sont optionnels si déjà renseignés dans le devis.
    event_location est optionnel si déjà renseigné dans le devis.
    Les champs livraison sont propagés depuis le devis si non fournis.
    """
    event_date: Optional[date] = None
    delivery_date: Optional[date] = None
    return_date: Optional[date] = None
    event_location: Optional[str] = Field(None, min_length=1)
    # Livraison (override du devis si fourni)
    delivery_method: Optional[str] = Field(None, pattern="^(self|carrier|pickup)$")
    delivery_fee_cents: Optional[int] = Field(None, ge=0)
    carrier_name: Optional[str] = Field(None, max_length=100)
    carrier_code: Optional[str] = Field(None, max_length=20)
    delivery_address: Optional[str] = Field(None, max_length=500)
    delivery_city: Optional[str] = Field(None, max_length=100)
    delivery_postal_code: Optional[str] = Field(None, max_length=10)
    delivery_zone_id: Optional[int] = Field(None, gt=0)
    delivery_instructions: Optional[str] = None


class DevisConvertResponse(BaseSchema):
    """Réponse après conversion d'un devis en réservation."""
    reservation_id: int
    devis_id: int
    status: DevisStatus
    converted_reservation_id: Optional[int]


class DevisSignatureRequest(BaseSchema):
    """Payload pour signer électroniquement un devis."""
    signature_data: str  # base64 PNG


class DevisSignatureResponse(BaseSchema):
    """Réponse après signature électronique."""
    id: int
    signature_url: str
    signed_at: datetime


class DevisListItem(BaseSchema):
    """Item minimal pour la liste des devis."""
    id: int
    reference: str
    status: str
    customer_id: int
    customer_name: str
    total_cents: int
    valid_until: date
    event_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    @computed_field
    @property
    def allowed_actions(self) -> list[str]:
        return STATUS_ALLOWED_ACTIONS.get(self.status, [])

    @computed_field
    @property
    def total_euros(self) -> float:
        return self.total_cents / 100


class DevisRefuseRequest(BaseSchema):
    """Payload pour refuser un devis."""
    reason: Optional[str] = Field(None, max_length=1000)


class DevisNegotiationConcludeRequest(BaseSchema):
    """Payload pour conclure formellement une négociation."""
    outcome: str = Field(..., pattern="^(accepted|refused)$")
    reason: Optional[str] = Field(None, max_length=1000, description="Raison du refus (si outcome=refused)")


class DevisResponse(EntityResponseSchema):
    """Réponse complète d'un devis avec toutes ses sous-entités."""
    reference: str
    customer_id: int
    customer_name: str
    status: str
    event_date: Optional[date] = None
    event_location: Optional[str] = None
    delivery_date: Optional[date] = None
    return_date: Optional[date] = None
    valid_until: date
    tva_rate: int
    subtotal_cents: int
    tva_cents: int
    total_cents: int
    discount_pct: Optional[int] = None
    caution_required: bool
    caution_amount_cents: Optional[int] = None
    notes: Optional[str] = None
    conditions_paiement: Optional[str] = None
    message_accompagnement: Optional[str] = None
    # Livraison
    delivery_method: Optional[str] = None
    delivery_fee_cents: int = 0
    carrier_name: Optional[str] = None
    carrier_code: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_city: Optional[str] = None
    delivery_postal_code: Optional[str] = None
    delivery_zone_id: Optional[int] = None
    delivery_instructions: Optional[str] = None
    refusal_reason: Optional[str] = None
    signature_url: Optional[str] = None
    signed_at: Optional[datetime] = None
    converted_reservation_id: Optional[int] = None
    converted_reservation_reference: Optional[str] = None
    lines: list[DevisLineResponse] = Field(default_factory=list)
    modules: list[DevisModuleResponse] = Field(default_factory=list)
    phases: list[DevisPhaseResponse] = Field(default_factory=list)
    negotiations: list[DevisNegotiationResponse] = Field(default_factory=list)
    change_requests: list[DevisChangeRequestResponse] = Field(default_factory=list)

    @computed_field
    @property
    def allowed_actions(self) -> list[str]:
        """Actions UI autorisées depuis ce statut — source de vérité backend."""
        return STATUS_ALLOWED_ACTIONS.get(self.status, [])

    @computed_field
    @property
    def total_euros(self) -> float:
        return self.total_cents / 100

    @computed_field
    @property
    def subtotal_euros(self) -> float:
        return self.subtotal_cents / 100

    @computed_field
    @property
    def total_weight_grams(self) -> int:
        """Poids total du devis en grammes."""
        return sum(
            (line.weight_grams or 0) * line.quantity
            for line in self.lines
        )

    @computed_field
    @property
    def total_volume_cm3(self) -> int:
        """Volume total du devis en cm³."""
        return sum(
            (line.volume_cm3 or 0) * line.quantity
            for line in self.lines
        )

    @computed_field
    @property
    def total_weight_kg(self) -> float:
        """Poids total du devis en kg."""
        return self.total_weight_grams / 1000

    @computed_field
    @property
    def total_volume_liters(self) -> float:
        """Volume total du devis en litres."""
        return self.total_volume_cm3 / 1000


class DevisCoverageResponse(BaseSchema):
    """Couverture d'un devis : % modules livrés vs restants, progression phases."""
    devis_id: int
    reference: str
    status: str
    total_modules: int
    active_modules: int
    module_types: list[str]
    total_phases: int
    phases_past: int
    phases_current: int
    phases_future: int
    phase_completion_pct: int
    total_lines: int
    subtotal_cents: int

    @computed_field
    @property
    def subtotal_euros(self) -> float:
        return self.subtotal_cents / 100
