"""Endpoints Carrier — devis transporteurs via Boxtal."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.deps import require_scope, UserCompat
from app.core.permissions import Scope
from app.repositories.tenant_settings import AsyncTenantSettingsRepository
from app.services.carrier import CarrierQuoteRequest, CarrierService

router = APIRouter(prefix="/carrier", tags=["Carrier"])


class CarrierQuoteBody(BaseModel):
    """Requete de devis transporteur."""

    weight_grams: int = Field(..., gt=0, description="Poids total en grammes")
    volume_cm3: Optional[int] = Field(None, ge=0, description="Volume total en cm3")
    length_cm: Optional[int] = Field(None, gt=0)
    width_cm: Optional[int] = Field(None, gt=0)
    height_cm: Optional[int] = Field(None, gt=0)
    destination_postal_code: str = Field(
        ..., min_length=2, max_length=10, description="Code postal destination"
    )
    destination_country: str = Field("FR", min_length=2, max_length=2)


class CarrierQuoteResponse(BaseModel):
    """Devis transporteur."""

    carrier_name: str
    carrier_code: str
    service_name: str
    price_cents: int
    delivery_days: Optional[int] = None
    currency: str = "EUR"


@router.post("/quotes", response_model=list[CarrierQuoteResponse])
async def get_carrier_quotes(
    body: CarrierQuoteBody,
    current_user: UserCompat = Depends(require_scope(Scope.RESERVATIONS_READ)),
    db: AsyncSession = Depends(get_async_db),
) -> list[CarrierQuoteResponse]:
    """Recupere les devis transporteurs pour une expedition.

    Origine : code postal du tenant (depuis TenantSettings).
    Destination : code postal fourni dans la requete.
    """
    repo = AsyncTenantSettingsRepository(db)
    tenant_settings = await repo.get(current_user.tenant_id)

    origin_postal_code = getattr(tenant_settings, "origin_postal_code", None) if tenant_settings else None
    if not origin_postal_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Code postal d'origine non configure dans les parametres du tenant",
        )

    service = CarrierService()
    quotes = await service.get_quotes(
        CarrierQuoteRequest(
            weight_grams=body.weight_grams,
            volume_cm3=body.volume_cm3,
            length_cm=body.length_cm,
            width_cm=body.width_cm,
            height_cm=body.height_cm,
            origin_postal_code=origin_postal_code,
            destination_postal_code=body.destination_postal_code,
            destination_country=body.destination_country,
        )
    )

    return [CarrierQuoteResponse.model_validate(q, from_attributes=True) for q in quotes]
