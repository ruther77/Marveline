"""Schemas Pydantic pour Container, ContainerAssignment, ContainerItem."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContainerCreate(BaseModel):
    """Création d'un contenant."""

    name: str = Field(..., max_length=200, description="Nom du contenant")
    container_type: str = Field(
        ..., description="Type : bac, carton, palette, housse, caisse"
    )
    length_cm: Optional[int] = Field(None, gt=0, description="Longueur cm")
    width_cm: Optional[int] = Field(None, gt=0, description="Largeur cm")
    height_cm: Optional[int] = Field(None, gt=0, description="Hauteur cm")
    max_weight_grams: Optional[int] = Field(None, gt=0, description="Poids max en grammes")
    serial_number: Optional[str] = Field(None, max_length=100, description="Numéro de série")
    notes: Optional[str] = None


class ContainerUpdate(BaseModel):
    """Mise à jour partielle d'un contenant."""

    name: Optional[str] = Field(None, max_length=200)
    container_type: Optional[str] = None
    length_cm: Optional[int] = Field(None, gt=0)
    width_cm: Optional[int] = Field(None, gt=0)
    height_cm: Optional[int] = Field(None, gt=0)
    max_weight_grams: Optional[int] = Field(None, gt=0)
    serial_number: Optional[str] = Field(None, max_length=100)
    is_available: Optional[bool] = None
    notes: Optional[str] = None


class ContainerResponse(BaseModel):
    """Réponse API pour un contenant."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    container_type: str
    length_cm: Optional[int] = None
    width_cm: Optional[int] = None
    height_cm: Optional[int] = None
    max_weight_grams: Optional[int] = None
    serial_number: Optional[str] = None
    is_available: bool
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ContainerAssignCreate(BaseModel):
    """Affectation d'un contenant à un mouvement."""

    container_id: int = Field(..., gt=0, description="ID du contenant")
    movement_id: int = Field(..., gt=0, description="ID du mouvement de stock")
    notes: Optional[str] = None
    items: list["ContainerItemCreate"] = Field(
        default_factory=list, description="Articles dans le contenant"
    )


class ContainerItemCreate(BaseModel):
    """Article à placer dans un contenant."""

    movement_item_id: int = Field(..., gt=0, description="ID de la ligne mouvement")
    quantity: int = Field(..., gt=0, description="Quantité dans ce contenant")


class ContainerItemResponse(BaseModel):
    """Réponse API pour un article dans un contenant."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    container_assignment_id: int
    movement_item_id: int
    quantity: int
    created_at: datetime
    updated_at: datetime


class ContainerAssignmentResponse(BaseModel):
    """Réponse API pour une affectation contenant-mouvement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    container_id: int
    movement_id: int
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    container: Optional[ContainerResponse] = None
    items: list[ContainerItemResponse] = []


# ── Container Contents (contenu persistant) ─────────────────


class ContainerContentCreate(BaseModel):
    """Ajout d'un produit dans un contenant."""

    product_id: int = Field(..., gt=0, description="ID du produit")
    variant_id: Optional[int] = Field(None, gt=0, description="ID de la variante")
    quantity: int = Field(..., gt=0, description="Quantite a placer")


class ContainerContentUpdate(BaseModel):
    """Mise a jour de la quantite d'un produit dans un contenant."""

    quantity: int = Field(..., gt=0, description="Nouvelle quantite")


class ContainerContentResponse(BaseModel):
    """Reponse API pour un contenu de contenant."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    container_id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    created_at: datetime
    updated_at: datetime
    product_name: Optional[str] = None
    variant_label: Optional[str] = None


class ContainerDetailResponse(ContainerResponse):
    """Reponse enrichie avec contenu + poids total."""

    contents: list[ContainerContentResponse] = []
    contents_count: int = 0
    total_items: int = 0


class ContainerMovementHistoryEntry(BaseModel):
    """Entree d'historique mouvement pour un contenant."""

    model_config = ConfigDict(from_attributes=True)

    movement_id: int
    movement_type: str
    status: str
    scheduled_date: Optional[datetime] = None
    reservation_reference: Optional[str] = None
    items_summary: list[dict] = []


class BulkContentEntry(BaseModel):
    """Entree pour remplacement en masse du contenu."""

    product_id: int = Field(..., gt=0)
    variant_id: Optional[int] = Field(None, gt=0)
    quantity: int = Field(..., gt=0)


class BulkContentRequest(BaseModel):
    """Requete de remplacement du contenu complet."""

    entries: list[BulkContentEntry] = Field(..., min_length=1)
