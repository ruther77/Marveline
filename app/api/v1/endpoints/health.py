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
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.core.health import check_postgres, check_redis
from app.core.redis import redis_client
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
def readiness_probe(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Readiness probe avec vérification dépendances critiques.

    Utilisé par Kubernetes readiness probe pour savoir si le pod peut recevoir du trafic.
    Vérifie PostgreSQL + Redis avec timeout strict.

    Args:
        db: Session SQLAlchemy (dependency injection)

    Returns:
        Dict avec :
        - status: "ready" | "not_ready"
        - service: nom du service
        - version: version applicative
        - checks: dict des vérifications (postgres, redis)

    Raises:
        HTTPException 503 Service Unavailable si au moins une dépendance est down

    Example succès (200):
        >>> GET /health/ready
        >>> {
        ...   "status": "ready",
        ...   "service": "CaroCorp",
        ...   "version": "0.1.0",
        ...   "checks": {
        ...     "postgres": {"status": "healthy", "latency_ms": 3.45},
        ...     "redis": {"status": "healthy", "latency_ms": 1.23}
        ...   }
        ... }

    Example échec (503):
        >>> GET /health/ready
        >>> {
        ...   "status": "not_ready",
        ...   "checks": {
        ...     "postgres": {"status": "unhealthy", "error": "connection refused"}
        ...   }
        ... }

    Notes:
        - Timeout total < 2 secondes (SELECT 1 + PING)
        - Si échec → Kubernetes arrête d'envoyer du trafic au pod
        - Retourne 503 Service Unavailable si not_ready
        - Pool metrics utiles pour détecter saturation connexions
    """
    # Vérifier PostgreSQL
    postgres_healthy, postgres_metadata = check_postgres(db)

    # Vérifier Redis
    redis_healthy, redis_metadata = check_redis(redis_client.client)

    # Déterminer status global
    all_healthy = postgres_healthy and redis_healthy

    response = {
        "status": "ready" if all_healthy else "not_ready",
        "service": "CaroCorp",
        "version": settings.APP_VERSION,
        "checks": {
            "postgres": postgres_metadata,
            "redis": redis_metadata,
        }
    }

    # Retourner 503 si au moins une dépendance est down
    if not all_healthy:
        return JSONResponse(
            content=response,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return response
