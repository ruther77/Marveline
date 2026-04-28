"""Schemas Pydantic — LigneCommandeRestaurant.

Shapes :
  POST body  : V2_API_RESTAURANT.md §Body POST /restaurant/commandes/{id}/lignes
  GET cuisine: V2_API_RESTAURANT.md §Shape GET /restaurant/commandes/tickets-cuisine
  GET détail : champ `lignes` dans CommandeDetail (commande.py)

Formule boissons : suggestion retournée si multiple de 3 boissons identiques.
"""
from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class LigneCommandeCreate(BaseSchema):
    """Body POST /restaurant/commandes/{id}/lignes."""
    variante_plat_id: int
    instance_preparation_id: Optional[int] = None
    side_id: Optional[int] = None
    quantite: int = Field(default=1, ge=1)
    notes: Optional[str] = Field(None, max_length=500)


class SuggestionFormule(BaseSchema):
    """Suggestion formule boissons retournée côté service (multiple de 3)."""
    variante_formule_id: int
    label: str
    economies_cts: int
    boissons_concernees_ids: list[int] = Field(default_factory=list)


class LigneCommandeResponse(BaseSchema):
    """Ligne dans GET /restaurant/commandes/{id} (vue serveur)."""
    ligne_id: int
    variante_nom: str
    side_nom: Optional[str]
    instance_preparation_id: Optional[int]
    statut_plat: str
    prix_unitaire_cts: int
    quantite: int
    notes: Optional[str]


class LigneCommandeCreateResponse(BaseSchema):
    """Réponse POST /restaurant/commandes/{id}/lignes."""
    ligne_id: int
    variante_nom: Optional[str] = None  # R8 : nom de la variante ajoutée
    statut_plat: str
    prix_unitaire_cts: Optional[int] = None  # R8 : snapshot prix au moment de l'ajout
    suggestion_formule: Optional[SuggestionFormule] = None


class TicketCuisineItem(BaseSchema):
    """Item plat (shape plate, conservé pour compatibilité interne)."""
    ligne_id: int
    commande_id: int
    table_numero: Optional[str]
    statut_plat: str
    variante_nom: str
    side_nom: Optional[str]
    notes: Optional[str]
    heure_commande: datetime


class TicketCuisineLigne(BaseSchema):
    """Ligne dans un ticket cuisine groupé — R2."""
    ligne_id: int
    variante_nom: str
    side_nom: Optional[str]
    statut_plat: str
    instance_preparation_id: Optional[int]
    stock_disponible: bool  # R2 : portions_restantes > 0 (ADR-14)
    notes: Optional[str]


class TicketCuisineTicket(BaseSchema):
    """Ticket cuisine groupé par commande — R2 (FC_RESTAURANT_CUISINE.md §GET /tickets-cuisine)."""
    ticket_id: str  # "T{commande_id}"
    commande_id: int
    table_numero: Optional[str]
    heure_envoi: Optional[datetime]
    lignes: list[TicketCuisineLigne]


class TicketCuisineResponse(BaseSchema):
    items: list[TicketCuisineTicket]


class StatutLigneUpdate(BaseSchema):
    """Body PATCH /restaurant/lignes-commande/{id}/statut."""
    statut: str = Field(..., pattern="^(LANCEE|PRETE|SERVIE)$")


class MarquerPretRequest(BaseSchema):
    """Body POST /restaurant/commandes/{id}/marquer-pret."""
    ligne_ids: Optional[list[int]] = None


class MarquerPretResponse(BaseSchema):
    """Réponse POST /restaurant/commandes/{id}/marquer-pret — R7."""
    commande_id: int
    lignes_mises_a_jour: int
    lignes_ignorees: int


class LigneHistoriqueResponse(BaseSchema):
    """Ligne dans CommandeDetail (historique) — inclut montant_cts calculé."""
    ligne_id: int
    type: str  # plat | boisson | formule
    description: str
    side: Optional[str]
    quantite: int
    prix_unitaire_cts: int
    montant_cts: int


class BoissonsTicketLigne(BaseSchema):
    """Ligne boisson dans le ticket bar."""
    ligne_id: int
    variante_nom: str
    quantite: int
    prix_unitaire_cts: int
    statut_plat: str
    notes: Optional[str]
    heure_commande: datetime
    suggestion_formule: Optional[SuggestionFormule] = None


class BoissonsTicket(BaseSchema):
    """Ticket bar : groupe de lignes boissons pour une commande en attente."""
    commande_id: int
    table_numero: Optional[str]
    date_ouverture: datetime
    suggestion_formule: Optional[SuggestionFormule] = None
    lignes: list[BoissonsTicketLigne]


class BoissonsTicketResponse(BaseSchema):
    """Réponse GET /restaurant/commandes/tickets-bar."""
    items: list[BoissonsTicket]


class AppliquerFormuleRequest(BaseSchema):
    """Body POST /restaurant/commandes/{id}/appliquer-formule."""
    variante_formule_id: int
