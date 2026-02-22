"""Point d'entree principal de l'API CaroCorp."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

try:
    import sentry_sdk
    _SENTRY_AVAILABLE = True
except ImportError:
    _SENTRY_AVAILABLE = False

from app.core.config import settings
from app.constants import PublicEndpoints
from app.core.logging import configure_logging
from app.core.metrics import metrics_endpoint
from app.api.v1 import api_router
from app.middleware.security import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)
from app.middleware.audit import AuditMiddleware
from app.middleware.exception_handler import register_exception_handlers
from app.middleware.metrics import MetricsMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.timing import TimingMiddleware

logger = logging.getLogger(__name__)

if _SENTRY_AVAILABLE and settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=0.1,
        ignore_errors=[404, 401, 422],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler — startup et shutdown (fix M14)."""
    configure_logging(
        level="DEBUG" if settings.DEBUG else "INFO",
        json_format=not settings.DEBUG,
    )
    logger.info(
        "Starting %s v%s (debug=%s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.DEBUG,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Factory pour creer l'application FastAPI.

    Ordre d'execution des middlewares (LIFO — dernier ajoute = premier execute) :
        Request ->
        MetricsMiddleware          (outermost — capture tout, y compris 429)
        TimingMiddleware           (mesure duree totale)
        TrustedHostMiddleware      (bloque hosts non autorises)
        CORSMiddleware             (preflight CORS)
        CSRFProtectionMiddleware   (validation CSRF)
        SecurityHeadersMiddleware  (ajout headers securite)
        RateLimitMiddleware        (rate limiting)
        GZipMiddleware             (compression reponses)
        RequestContextMiddleware   (X-Request-ID, JWT claims, ContextVars)
        AuditMiddleware            (innermost — audit actions)
        -> Exception Handlers -> Routes
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="API de gestion de location de vaisselle et accessoires pour evenements",
        docs_url=PublicEndpoints.DOCS if settings.DEBUG else None,
        redoc_url=PublicEndpoints.REDOC if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # --- Exception handlers (s'appliquent apres les middlewares) ---
    register_exception_handlers(app)

    # --- Middlewares (LIFO : dernier ajoute = premier execute) ---
    # Ordre d'ajout : innermost (premier) → outermost (dernier)
    # Execution requete : outermost → ... → innermost → handler
    # Execution reponse : handler → innermost → ... → outermost

    # Innermost — proche du handler
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=settings.GZIP_MIN_SIZE)

    # Couche securite
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFProtectionMiddleware)

    # Couche reseau
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-CSRF-Token",
            "X-Request-ID",
            "Accept",
            "Accept-Language",
            "Cache-Control",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-Response-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.carocorp.local", "testserver", "api"],
    )

    # Outermost — capturent TOUTES les responses (y compris 429 rate limit)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(MetricsMiddleware)

    # --- Routes ---
    app.include_router(api_router, prefix="/api/v1")

    # --- Static files ---
    uploads_dir = "/app/uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # Sous-dossier dommages (photos de dommages)
    damages_dir = os.path.join(uploads_dir, "damages")
    os.makedirs(damages_dir, exist_ok=True)

    @app.get("/metrics")
    def metrics():
        """Endpoint Prometheus metrics (scraping externe, public)."""
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
