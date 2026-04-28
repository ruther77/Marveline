"""Schemas Pydantic pour TenantBrand (endpoint public)."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TenantBrandPublic(BaseModel):
    """Identite brand publique — servie avant login pour habiller l'UI."""

    model_config = ConfigDict(from_attributes=True)

    display_name: str = Field(..., description="Nom affiche (ex: 'Le Splendid Events')")
    legal_name: str = Field(..., description="Raison sociale (ex: 'Le Splendid Events SAS')")
    tagline: Optional[str] = None
    primary_color: str = Field(..., description="Couleur primaire hex (#c9a961)")
    primary_rgb: str = Field(..., description="RGB decompose ('201 169 97') pour CSS vars")
    palette: Optional[dict[str, str]] = Field(None, description="Shades 50..950 hex")
    logo_url: Optional[str] = None
    logo_square_url: Optional[str] = None
    favicon_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
