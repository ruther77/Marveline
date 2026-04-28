"""Schémas Pydantic pour les opérations terrain (départ / retour / QR)."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DepartureItem(BaseModel):
    """Article pour la checklist de départ.

    Pour un produit individuel : product_id rempli, bundle_id absent.
    Pour un article issu d'un pack : product_id du produit réel + bundle_id/bundle_name
    pour permettre au frontend de regrouper visuellement sous un header pack.
    """

    line_id: int
    product_id: int
    product_name: str
    quantity_expected: int
    image_url: Optional[str] = None
    sku: Optional[str] = None
    bundle_id: Optional[int] = None
    bundle_name: Optional[str] = None
    is_bundle_item: bool = False


class ReturnItem(BaseModel):
    """Article pour la checklist de retour.

    Même logique que DepartureItem pour le regroupement pack.
    """

    line_id: int
    product_id: int
    product_name: str
    quantity_expected: int
    image_url: Optional[str] = None
    sku: Optional[str] = None
    bundle_id: Optional[int] = None
    bundle_name: Optional[str] = None
    is_bundle_item: bool = False


class DepartureState(BaseModel):
    """État de la checklist de départ pour une réservation."""

    model_config = ConfigDict(from_attributes=True)

    reservation_id: int
    reference: str
    customer_name: Optional[str] = None
    status: str
    total_items: int
    checked_items: int
    can_depart: bool  # True si status == pre_check et tous items cochés et caution réglée
    departure_blocked_reason: Optional[str] = None  # "pre_check_incomplete" | "deposit_required" | None
    items: list[DepartureItem] = []


class ReturnState(BaseModel):
    """État du retour pour une réservation."""

    model_config = ConfigDict(from_attributes=True)

    reservation_id: int
    reference: str
    customer_name: Optional[str] = None
    status: str
    delivery_date: Optional[date]
    return_date: Optional[date]
    can_return: bool  # True si status == delivered
    items: list[ReturnItem] = []

    # Solde restant à régler après le retour (D — warning non bloquant 2026-04-26).
    # Calcul : invoice.total_amount_cents - invoice.paid_amount_cents (>=0).
    # Si > 0, l'UI affiche un banner avec CTA "Générer une facture du solde".
    balance_due_cents: int = 0


class DepartureBlockRequest(BaseModel):
    reason: str


class DepartureLineItem(BaseModel):
    """État saisi côté UI lors du départ."""

    line_id: int
    product_id: int
    quantity_loaded: int
    condition: str = "good"
    qr_scanned: bool = False
    scanned_codes: list[str] = []


class DepartureValidateRequest(BaseModel):
    """Corps optionnel pour la validation du départ — stocke la signature."""

    signature_url: Optional[str] = None
    items: list[DepartureLineItem] = []


class ReturnDamageInput(BaseModel):
    """Dommage déclaré sur un article lors du retour."""

    damage_type_name: str
    description: str
    fee_cents: int = 0
    photo_urls: list[str] = []


class ReturnLineItem(BaseModel):
    """État d'une ligne de réservation au retour."""

    line_id: int
    quantity_returned: int
    condition: str = "good"
    damages: list[ReturnDamageInput] = []


class ReturnValidateRequest(BaseModel):
    """Corps optionnel pour la validation du retour — stocke la signature + états articles."""

    signature_url: Optional[str] = None
    items: list[ReturnLineItem] = []


class ReturnDamageRequest(BaseModel):
    description: str
    damage_type_name: str
    fee_cents: int = 0
    stock_item_id: Optional[int] = None
    photo_urls: list[str] = []


class DamageReportResponse(BaseModel):
    """Résumé d'un incident dommage créé lors du retour."""

    model_config = ConfigDict(from_attributes=True)

    reservation_id: int
    damage_type_id: int
    damage_type_name: str
    description: str
    fee_cents: int
    invoice_charge_id: Optional[int] = None


class QrResult(BaseModel):
    """Résultat du lookup QR / numéro de série."""

    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    stock_item_id: int
    serial_number: Optional[str]
    stock_status: str


class PhotoUploadResponse(BaseModel):
    url: str
    filename: str
