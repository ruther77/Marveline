"""Point d'entrée principal de l'API CaroCorp."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.constants import PublicEndpoints
from app.core.metrics import metrics_endpoint
from app.api.v1 import api_router
from app.middleware.security import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)
from app.middleware.audit import AuditMiddleware
from app.middleware.metrics import MetricsMiddleware


def create_application() -> FastAPI:
    """Factory pour créer l'application FastAPI."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="API de gestion de location de vaisselle et accessoires pour événements",
        docs_url=PublicEndpoints.DOCS if settings.DEBUG else None,
        redoc_url=PublicEndpoints.REDOC if settings.DEBUG else None,
    )

    # Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted Host Middleware (protection contre Host Header Injection)
    # Note: "testserver" est ajouté pour compatibilité avec TestClient
    allowed_hosts = ["localhost", "127.0.0.1", "*.carocorp.local", "testserver"]
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts,
    )

    # CSRF Protection Middleware
    app.add_middleware(CSRFProtectionMiddleware)

    # Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)

    # Audit Middleware (trace toutes les actions authentifiées)
    app.add_middleware(AuditMiddleware)

    # Metrics Middleware (DERNIER ajouté = PREMIER exécuté en LIFO, capture TOUTES les responses incluant 429)
    app.add_middleware(MetricsMiddleware)

    # Routes API v1 (inclut /api/v1/health/*, /api/v1/auth/*, etc.)
    app.include_router(api_router, prefix="/api/v1")

    # Endpoint Prometheus metrics (scraping externe)
    @app.get("/metrics")
    def metrics():
        """Endpoint Prometheus metrics.

        Exposition métriques RED (Rate, Errors, Duration) pour monitoring production.

        Returns:
            Response text/plain format Prometheus

        Example curl:
            $ curl http://localhost:8001/metrics
            # HELP http_requests_total Total HTTP requests
            # TYPE http_requests_total counter
            http_requests_total{method="GET",path="/api/v1/products",status="200"} 42.0
            ...

        Notes:
            - Appelé toutes les 15s par Prometheus (scrape_interval)
            - Pas d'authentification requise (endpoint public)
            - Compression gzip automatique si supportée
        """
        return metrics_endpoint()

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
