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
from app.api.jwks import router as jwks_router
from app.middleware.cors import StrictCORSMiddleware
from app.middleware.degraded import DegradedModeMiddleware
from app.middleware.security import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)
from app.middleware.app_enforcement import AppEnforcementMiddleware
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
    # Charger les scripts Lua Redis-SEC au démarrage (§3.6 — rotation atomique)
    try:
        from app.core.redis import redis_sec
        await redis_sec.load_lua_scripts()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load Lua scripts — refresh will use non-atomic fallback: %s", exc)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Factory pour creer l'application FastAPI.

    Ordre d'execution des middlewares (LIFO — dernier ajoute = premier execute) :
        Request ->
        MetricsMiddleware          (outermost — capture tout, y compris 429)
        TimingMiddleware           (mesure duree totale)
        TrustedHostMiddleware      (bloque hosts non autorises)
        StrictCORSMiddleware       (§7.4 — bloque 403 origines hors whitelist)
        CORSMiddleware             (headers preflight CORS standards)
        DegradedModeMiddleware     (§S-08.4 — mode dégradé 4 niveaux)
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
    app.add_middleware(AppEnforcementMiddleware)  # ISO-APP-01 — enforcement app↔tenant
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFProtectionMiddleware)

    # Couche reseau (LIFO — CORSMiddleware ajouté avant → StrictCORSMiddleware s'exécute en premier)
    # DEBUG : allow_origin_regex accepte *.ngrok-free.dev et *.trycloudflare.com pour tunnels dev
    _tunnel_regex = (
        r"https://[a-z0-9\-]+\.(ngrok-free\.dev|trycloudflare\.com)"
        if settings.DEBUG else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=_tunnel_regex,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-CSRF-Token",
            "X-Request-ID",
            "X-E2E-Bypass",
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
    app.add_middleware(DegradedModeMiddleware)  # §S-08.4 — mode dégradé 4 niveaux
    app.add_middleware(StrictCORSMiddleware)  # §7.4 — defense-in-depth, bloque origines inconnues avant CORSMiddleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

    # Outermost — capturent TOUTES les responses (y compris 429 rate limit)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(MetricsMiddleware)

    # --- Routes ---
    app.include_router(jwks_router)  # /.well-known/jwks.json (CaroCorp §1.5)
    app.include_router(api_router, prefix="/api/v1")

    # --- WebSocket KDS (restaurant temps réel) ---
    from app.api.ws.kds import router as ws_kds_router
    app.include_router(ws_kds_router)  # WS /ws/kds + /ws/salle

    # --- Static files ---
    uploads_dir = settings.UPLOAD_DIR or "uploads"
    if not os.path.isabs(uploads_dir):
        uploads_dir = os.path.abspath(uploads_dir)
    try:
        os.makedirs(uploads_dir, exist_ok=True)
    except PermissionError:
        fallback_uploads_dir = os.path.abspath("uploads")
        logger.warning(
            "Upload dir %s not writable; falling back to %s",
            uploads_dir,
            fallback_uploads_dir,
        )
        uploads_dir = fallback_uploads_dir
        os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # P1-19 : securiser les fichiers uploades (anti-XSS via SVG/HTML)
    @app.middleware("http")
    async def secure_uploads_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/uploads/"):
            # PDFs ETL : servis inline dans iframe (vue split)
            if request.url.path.startswith("/uploads/etl/") and request.url.path.endswith(".pdf"):
                response.headers["Content-Type"] = "application/pdf"
                response.headers["Content-Disposition"] = "inline"
            else:
                response.headers["Content-Type"] = "application/octet-stream"
                response.headers["Content-Disposition"] = "attachment"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # Sous-dossier dommages (photos de dommages)
    damages_dir = os.path.join(uploads_dir, "damages")
    os.makedirs(damages_dir, exist_ok=True)

    from fastapi import Request as FastAPIRequest

    @app.get("/metrics")
    def metrics(request: FastAPIRequest):
        """Endpoint Prometheus metrics (P2-15 : protege par API key ou localhost)."""
        import ipaddress
        client_ip = request.client.host if request.client else ""
        metrics_key = request.headers.get("X-Metrics-Key", "")
        metrics_api_key = os.environ.get("METRICS_API_KEY", "")
        # Autoriser localhost + reseau Docker interne (172.16-31.x.x)
        is_local = client_ip in ("127.0.0.1", "::1")
        is_docker = False
        try:
            is_docker = ipaddress.ip_address(client_ip).is_private
        except ValueError:
            pass
        if not is_local and not is_docker and (not metrics_api_key or metrics_key != metrics_api_key):
            from fastapi import HTTPException
            raise HTTPException(403)
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
