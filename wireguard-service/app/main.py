"""Factory FastAPI pour le microservice WireGuard."""

import logging

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings


def create_application() -> FastAPI:
    """Crée et configure l'application FastAPI."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/wg/docs" if settings.is_development else None,
        redoc_url="/wg/redoc" if settings.is_development else None,
        openapi_url="/wg/openapi.json" if settings.is_development else None,
    )

    # Middleware — pas de CORS (service interne uniquement)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],
        )

    # Validate production secrets at startup
    if settings.is_production:
        settings.validate_production_secrets()

    # Routes
    app.include_router(api_v1_router)

    @app.get("/wg/health")
    def health_check():
        return {"status": "ok", "service": settings.APP_NAME}

    return app


app = create_application()
