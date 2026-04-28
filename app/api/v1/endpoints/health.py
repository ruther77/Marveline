"""Endpoints Health Checks pour CaroCorp.

Fournit 3 endpoints pour monitoring production et Kubernetes :
- GET /health : Liveness probe (toujours healthy)
- GET /health/ready : Readiness probe (vérifie dépendances critiques)
- GET /health/live : Alias pour /health (compatibilité load balancers)

Utilisé par :
- Kubernetes liveness/readiness probes
- Load balancers (health checks actifs)
- Monitoring Prometheus (availability metrics)
- Alerting production (détection pannes)

Example Kubernetes deployment.yaml:
    livenessProbe:
      httpGet:
        path: /health/live
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 10

Example response /health/ready (200 OK):
    {
      "status": "ready",
      "service": "CaroCorp",
      "version": "0.1.0",
      "checks": {
        "postgres": {
          "status": "healthy",
          "latency_ms": 3.45,
          "pool_size": 5,
          "pool_checked_out": 2
        },
        "redis": {
          "status": "healthy",
          "latency_ms": 1.23,
          "memory_used_mb": 45.67,
          "connected_clients": 3
        }
      }
    }

Example response /health/ready (503 Service Unavailable - DB down):
    {
      "status": "not_ready",
      "service": "CaroCorp",
      "version": "0.1.0",
      "checks": {
        "postgres": {
          "status": "unhealthy",
          "error": "connection timeout"
        },
        "redis": {
          "status": "healthy",
          "latency_ms": 1.45
        }
      }
    }
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.core.health import check_postgres, check_redis_async
from app.core.redis import redis_client, redis_sec, redis_cache
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Liveness probe simple (toujours healthy).

    Utilisé par Kubernetes liveness probe pour savoir si le pod doit être redémarré.
    Ne vérifie AUCUNE dépendance externe pour éviter les faux positifs.

    Returns:
        Dict avec status="ok" (toujours)

    Example:
        >>> GET /health
        >>> {"status": "ok"}

    Notes:
        - Timeout < 100ms (pas de DB/Redis check)
        - Toujours 200 OK sauf si le processus est crashé
        - Si cet endpoint échoue → Kubernetes redémarre le pod
    """
    return {"status": "ok"}


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness_probe() -> Dict[str, str]:
    """Alias pour /health (compatibilité load balancers).

    Certains load balancers préfèrent /health/live pour les liveness probes.
    Identique à GET /health.

    Returns:
        Dict avec status="ok" (toujours)
    """
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(db: Session = Depends(get_db)):
    """Readiness probe — verifie PostgreSQL + Redis + Celery."""
    postgres_healthy, postgres_metadata = check_postgres(db)
    redis_healthy, redis_metadata = await check_redis_async(redis_client.client)

    # Celery health check via Redis broker ping
    celery_healthy = False
    celery_metadata = {"status": "unknown"}
    try:
        from app.tasks.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=2.0)
        active = inspector.active()
        if active is not None:
            worker_count = len(active)
            celery_healthy = worker_count > 0
            celery_metadata = {"status": "healthy" if celery_healthy else "no_workers", "workers": worker_count}
        else:
            celery_metadata = {"status": "unreachable"}
    except Exception as e:
        celery_metadata = {"status": "error", "detail": str(e)[:100]}

    all_healthy = postgres_healthy and redis_healthy and celery_healthy
    response = {
        "status": "ready" if all_healthy else "not_ready",
        "service": "CaroCorp",
        "version": settings.APP_VERSION,
        "checks": {
            "postgres": postgres_metadata,
            "redis": redis_metadata,
            "celery": celery_metadata,
        }
    }

    if not all_healthy:
        return JSONResponse(content=response, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return response


@router.get("/status", status_code=status.HTTP_200_OK)
async def system_status() -> Dict[str, Any]:
    """Status page publique — niveau de dégradation + composants."""
    degradation_level = await redis_sec.get_degradation_level()

    redis_sec_ok = await redis_sec.ping()
    redis_cache_ok = await redis_cache.ping()

    if degradation_level == "EMERGENCY_BYPASS":
        overall = "major_outage"
    elif degradation_level in ("AUTH_DOWN", "READ_ONLY"):
        overall = "partial_outage"
    elif not redis_sec_ok or not redis_cache_ok:
        overall = "degraded_performance"
    else:
        overall = "operational"

    return {
        "status": overall,
        "degradation_level": degradation_level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.APP_VERSION,
        "components": {
            "redis_sec":   "operational" if redis_sec_ok else "major_outage",
            "redis_cache": "operational" if redis_cache_ok else "degraded_performance",
            "api":         "operational",
        },
        "incidents": [] if overall == "operational" else [
            {"level": degradation_level, "since": datetime.now(timezone.utc).isoformat()}
        ],
    }
