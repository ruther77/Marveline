"""Point d'entrée principal de l'API CaroCorp."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.api.v1 import api_router
from app.middleware.security import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)


def create_application() -> FastAPI:
    """Factory pour créer l'application FastAPI."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="API de gestion de location de vaisselle et accessoires pour événements",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
    )

    # Security Headers Middleware (premier pour headers sur toutes réponses)
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
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.carocorp.local"],
    )

    # CSRF Protection Middleware
    app.add_middleware(CSRFProtectionMiddleware)

    # Rate Limiting Middleware
    app.add_middleware(RateLimitMiddleware)

    # Routes API v1
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        """Endpoint de santé pour monitoring."""
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

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
