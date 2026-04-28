"""Schémas pour la recherche globale."""
from typing import Any, Optional
from pydantic import BaseModel


class NavigationTarget(BaseModel):
    """Contrat de navigation stable — indépendant des chemins URL frontend.

    Permet aux clients (mobile, tiers) de naviguer sans parser les URL.
    """
    domain: str          # "reservation" | "product" | "customer" | "invoice" | "devis"
    route_name: str      # nom de route TanStack (ex: "/_app/reservations/$id/")
    params: dict[str, Any] = {}


class SearchResult(BaseModel):
    """Un résultat de recherche unifié."""
    type: str  # "customer" | "product" | "reservation" | "invoice" | "devis"
    id: int
    title: str
    subtitle: Optional[str] = None
    url: str  # route frontend (navigation directe)
    target: Optional[NavigationTarget] = None  # contrat navigation stable §9.6.3

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    """Réponse de la recherche globale."""
    results: list[SearchResult]
    total: int
    query: str
