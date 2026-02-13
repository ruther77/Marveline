"""Routeur principal API v1."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, products, customers, reservations, invoices, audit, health
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
