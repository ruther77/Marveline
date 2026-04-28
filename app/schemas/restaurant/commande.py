"""Schemas Pydantic — CommandeRestaurant.

Shapes :
  POST body    : { "table_id": 5 }
  GET liste    : V2_API_RESTAURANT.md §GET /restaurant/commandes (historique + active)
  GET détail   : V2_API_RESTAURANT.md §GET /restaurant/commandes/{id}
  POST paiement: V2_API_RESTAURANT.md §POST /restaurant/commandes/{id}/paiement

TVA variable par ligne (ADR-06-BIS) — `tva_cts` est la somme des TVA ligne par ligne.
Pas de `tva_rate` global — DETECT_DIVERGENCE résolu : convention > shape historique.

`date_fermeture` : null tant que OUVERTE, renseigné à PAYEE/ANNULEE.
"""
from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema
from app.schemas.restaurant.ligne_commande import LigneCommandeResponse, LigneHistoriqueResponse


MODES_PAIEMENT = {"especes", "CB", "virement", "mixte"}


class CommandeCreate(BaseSchema):
    """Body POST /restaurant/commandes."""
    table_id: Optional[int] = None
    nb_couverts: int = Field(..., ge=1)
    nom_client: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class FractionPaiement(BaseSchema):
    label: str = Field(..., min_length=1)
    montant_cts: int = Field(..., ge=0)
    mode: str = Field(..., pattern="^(especes|CB|virement)$")


class PaiementRequest(BaseSchema):
    """Body POST /restaurant/commandes/{id}/paiement."""
    mode_paiement: str = Field(..., pattern="^(especes|CB|virement|mixte)$")
    montant_encaisse_cts: int = Field(..., ge=0)
    pourboire_cts: int = Field(default=0, ge=0)
    fractions: Optional[list[FractionPaiement]] = None


class CommandeResponse(BaseSchema):
    """Ligne dans la liste commandes (active ou historique)."""
    id: int
    table_numero: Optional[str]
    statut: str
    date_ouverture: datetime
    date_fermeture: Optional[datetime]
    nb_couverts: int
    nom_client: Optional[str] = None
    total_cts: Optional[int]
    pourboire_cts: int


class CommandeListResponse(BaseSchema):
    """Shape GET /restaurant/commandes (historique) avec CA période."""
    items: list[CommandeResponse]
    page: int
    per_page: int
    total: int
    ca_periode_cts: int


class CommandeDetail(BaseSchema):
    """Shape GET /restaurant/commandes/{id} (vue serveur — commande active).

    `sous_total_cts` et `tva_cts` calculés en temps réel (TVA variable ADR-06-BIS).
    """
    id: int
    table_numero: Optional[str]
    statut: str
    date_ouverture: datetime
    nb_couverts: int
    nom_client: Optional[str] = None
    lignes: list[LigneCommandeResponse]
    sous_total_cts: int
    tva_cts: int
    total_cts: int


class CommandeDetailHistorique(BaseSchema):
    """Shape GET /restaurant/commandes/{id} (vue historique — commande fermée).

    `tva_cts` : somme des TVA par ligne, chacune calculée avec son propre taux.
    Formule ligne : round(prix_cts * qte * taux / (1 + taux)).
    """
    id: int
    table_numero: Optional[str]
    statut: str
    date_ouverture: datetime
    date_fermeture: Optional[datetime]
    lignes: list[LigneHistoriqueResponse]
    sous_total_cts: int
    tva_cts: int
    total_ttc_cts: int
    pourboire_cts: int
    mode_paiement: Optional[str]
    fractions: Optional[list[FractionPaiement]]
