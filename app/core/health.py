"""Services de vérification santé des dépendances CaroCorp.

Ce module fournit des fonctions pour vérifier la santé des dépendances critiques
(PostgreSQL, Redis) et retourner des métriques de performance détaillées.

Utilisé par :
- Endpoints health checks (/health/ready)
- Monitoring Prometheus (métriques infrastructure)
- Debugging production (diagnostics)

Example:
    >>> from app.core.health import check_postgres, check_redis
    >>> from app.core.database import get_db
    >>>
    >>> db = next(get_db())
    >>> is_healthy, metadata = check_postgres(db)
    >>> print(f"PostgreSQL: {metadata['status']}, latency: {metadata['latency_ms']}ms")
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from redis import Redis
import time
from typing import Tuple, Dict, Any


def check_postgres(db: Session) -> Tuple[bool, Dict[str, Any]]:
    """Vérifie la santé de la connexion PostgreSQL.

    Exécute une requête simple SELECT 1 pour vérifier la connectivité
    et mesurer la latence. Collecte aussi des métriques sur le pool de connexions.

    Args:
        db: Session SQLAlchemy active

    Returns:
        Tuple (is_healthy, metadata) où:
        - is_healthy (bool): True si DB accessible, False sinon
        - metadata (dict): Dictionnaire avec:
            - status (str): "healthy" | "unhealthy"
            - latency_ms (float): Temps de réponse SELECT 1 en millisecondes
            - pool_size (int): Taille totale du pool de connexions
            - pool_checked_out (int): Connexions actuellement utilisées
            - error (str): Message d'erreur si unhealthy

    Example:
        >>> is_healthy, metadata = check_postgres(db)
        >>> if is_healthy:
        ...     print(f"DB latency: {metadata['latency_ms']}ms")
        ... else:
        ...     print(f"DB error: {metadata['error']}")

    Notes:
        - Timeout implicite via SQLAlchemy (configurable dans settings)
        - Pas d'exception levée, retourne (False, {error: ...}) si échec
        - Pool metrics utiles pour détecter saturation connexions
    """
    try:
        # Mesurer latence SELECT 1
        start = time.time()
        db.execute(text("SELECT 1"))
        latency_ms = (time.time() - start) * 1000

        # Récupérer métriques pool de connexions
        # Note: En mode test, db.get_bind() retourne une Connection (pas Engine)
        engine = db.get_bind()

        result = {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
        }

        # Ajouter pool metrics uniquement si disponibles (production avec Engine)
        if hasattr(engine, 'pool'):
            pool = engine.pool
            result["pool_size"] = pool.size()
            result["pool_checked_out"] = pool.checkedout()

        return True, result

    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e),
        }


def check_redis(redis_client: Redis) -> Tuple[bool, Dict[str, Any]]:
    """Vérifie la santé de la connexion Redis.

    Exécute un PING Redis pour vérifier la connectivité et mesurer la latence.
    Collecte aussi des métriques sur l'utilisation mémoire et les clients connectés.

    Args:
        redis_client: Instance Redis client

    Returns:
        Tuple (is_healthy, metadata) où:
        - is_healthy (bool): True si Redis accessible, False sinon
        - metadata (dict): Dictionnaire avec:
            - status (str): "healthy" | "unhealthy"
            - latency_ms (float): Temps de réponse PING en millisecondes
            - memory_used_mb (float): Mémoire Redis utilisée en MB
            - connected_clients (int): Nombre de clients connectés
            - error (str): Message d'erreur si unhealthy

    Example:
        >>> from app.core.redis import redis_client
        >>> is_healthy, metadata = check_redis(redis_client)
        >>> if is_healthy:
        ...     print(f"Redis latency: {metadata['latency_ms']}ms")
        ...     print(f"Memory: {metadata['memory_used_mb']} MB")
        ... else:
        ...     print(f"Redis error: {metadata['error']}")

    Notes:
        - Timeout Redis configuré via REDIS_URL (default 5s)
        - INFO command peut être coûteux sur Redis très chargé
        - Pas d'exception levée, retourne (False, {error: ...}) si échec
    """
    try:
        # Mesurer latence PING
        start = time.time()
        pong = redis_client.ping()
        latency_ms = (time.time() - start) * 1000

        if not pong:
            # PING n'a pas retourné True
            return False, {
                "status": "unhealthy",
                "error": "PING returned False",
            }

        # Récupérer métriques Redis via INFO
        info = redis_client.info()

        # Mémoire utilisée (bytes → MB)
        memory_used_bytes = info.get('used_memory', 0)
        memory_used_mb = round(memory_used_bytes / 1024 / 1024, 2)

        # Nombre de clients connectés
        connected_clients = info.get('connected_clients', 0)

        return True, {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "memory_used_mb": memory_used_mb,
            "connected_clients": connected_clients,
        }

    except Exception as e:
        return False, {
            "status": "unhealthy",
            "error": str(e),
        }
