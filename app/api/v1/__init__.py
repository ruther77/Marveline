"""Routeur principal API v1."""
from fastapi import APIRouter

# Routeur principal v1
api_router = APIRouter()

# Import des endpoints (à décommenter au fur et à mesure)
# from app.api.v1.endpoints import auth, reservations, products, invoices

# Inclusion des sous-routeurs
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
# api_router.include_router(products.router, prefix="/products", tags=["products"])
# api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])


@api_router.get("/")
async def root():
    """Endpoint racine de l'API v1."""
    return {
        "message": "CaroCorp API v1",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": "/api/docs",
            "redoc": "/api/redoc",
        }
    }
