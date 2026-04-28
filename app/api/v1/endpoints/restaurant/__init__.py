"""Endpoints FastAPI — domaine Restaurant (module V2 alimentaire).

Routers exportés :
  dashboard_router : GET /restaurant/dashboard/*
  cuisine_router   : instances-preparation, types-preparation, tickets-cuisine
  commandes_router : tables, commandes, lignes-commande, paiement
  ingredients_router : ingredients, mouvements-stock
  historique_router : historique commandes + export CSV
  bar_router       : catalogue boissons, tickets-bar, appliquer-formule
  transferts_router : demandes de transfert restaurant → épicerie (BACK-TRANSFER-RESTO-01)
"""
from app.api.v1.endpoints.restaurant.bar import router as bar_router
from app.api.v1.endpoints.restaurant.commandes import router as commandes_router
from app.api.v1.endpoints.restaurant.cuisine import router as cuisine_router
from app.api.v1.endpoints.restaurant.dashboard import router as dashboard_router
from app.api.v1.endpoints.restaurant.historique import router as historique_router
from app.api.v1.endpoints.restaurant.ingredient_sourcing import router as ingredient_sourcing_router
from app.api.v1.endpoints.restaurant.ingredients import router as ingredients_router
from app.api.v1.endpoints.restaurant.transferts import router as transferts_router

__all__ = [
    "bar_router",
    "commandes_router",
    "cuisine_router",
    "dashboard_router",
    "historique_router",
    "ingredient_sourcing_router",
    "ingredients_router",
    "transferts_router",
]
