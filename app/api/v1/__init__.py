"""Routeur principal API v1."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, products, customers, reservations, invoices, audit, health, sessions, mfa, categories, bundles, users, api_keys, features, vpn, inventory_movements, dashboard
from app.constants import PublicEndpoints

# Routeur principal v1
api_router = APIRouter()

# Inclusion des sous-routeurs
api_router.include_router(auth.router)  # Prefix déjà défini dans auth.router
api_router.include_router(health.router)  # Health checks (Kubernetes probes)
api_router.include_router(products.router)
api_router.include_router(customers.router)
api_router.include_router(reservations.router)
api_router.include_router(invoices.router)
api_router.include_router(sessions.router)  # Session management
api_router.include_router(mfa.router)  # MFA TOTP
api_router.include_router(categories.router)  # Categories produits
api_router.include_router(bundles.router)  # Bundles (packs de produits)
api_router.include_router(users.router)  # User profile management
api_router.include_router(api_keys.router)  # API Keys M2M
api_router.include_router(features.router)  # Feature Flags
api_router.include_router(vpn.router)  # VPN WireGuard proxy
api_router.include_router(inventory_movements.router)  # Mouvements de stock
api_router.include_router(dashboard.router)  # Dashboard KPIs
api_router.include_router(audit.router)  # Admin uniquement


@api_router.get("/")
async def root():
    """Endpoint racine de l'API v1."""
    return {
        "message": "CaroCorp API v1",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": PublicEndpoints.DOCS,
            "redoc": PublicEndpoints.REDOC,
        }
    }
