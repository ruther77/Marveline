"""Service cache Redis pour CaroCorp.

Pattern fail-open : Si Redis échoue, laisser passer (availability > consistency).

Stratégies de cache :
- Products : TTL 5min (données relativement stables)
- Customers : TTL 10min (changent peu fréquemment)
- Reservations : TTL 1min (statut change souvent)

Invalidation :
- Write-through : Invalidation immédiate sur mutation (create/update/delete)
- Pattern-based : Invalidation de groupes (ex: tous les products)

Example usage :
    cache = CacheService()

    # Get/Set simple
    value = cache.get("product:123")
    cache.set("product:123", {"id": 123, "name": "Assiette"}, ttl=300)

    # Delete
    cache.delete("product:123")

    # Invalidate pattern (tous les products)
    cache.invalidate_pattern("product:*")

    # Décorateurs
    @cached(key_prefix="product", ttl=300)
    def get_product(product_id: int):
        return db.query(Product).filter_by(id=product_id).first()

    @cache_invalidate(patterns=["product:*"])
    def update_product(product_id: int, data: dict):
        # Update DB
        cache invalidé automatiquement après mutation
"""
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, List, Callable
from functools import wraps


class _DateEncoder(json.JSONEncoder):
    """Encodeur JSON qui gère date, datetime et Decimal."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

from app.core.redis import redis_cache
from app.core.metrics import redis_commands_total, redis_command_duration_seconds

logger = logging.getLogger(__name__)


class CacheService:
    """Service cache Redis avec fail-open strategy.

    Pattern fail-open :
    - Si Redis échoue (timeout, connection error), laisser passer
    - Retourner None sur cache miss (caller doit fetch depuis DB)
    - Ne jamais lever d'exception (availability > consistency)

    Metrics :
    - redis_commands_total{command="get"} : Nombre de GET Redis
    - redis_command_duration_seconds{command="get"} : Latence GET Redis

    Notes :
        - Sérialisation JSON automatique (dict/list → string)
        - UTF-8 encoding
        - TTL en secondes
    """

    def __init__(self):
        """Initialise CacheService avec client Redis."""
        self.redis = redis_cache

    async def get(self, key: str) -> Optional[Any]:
        """Récupère valeur depuis cache Redis.

        Args:
            key: Clé Redis (ex: "product:123", "customer:456")

        Returns:
            Valeur désérialisée (dict/list/str/int) ou None si cache miss

        Example:
            >>> cache.get("product:123")
            {"id": 123, "name": "Assiette", "price_cents": 150}

            >>> cache.get("product:999")  # Cache miss
            None

        Notes:
            - Fail-open : retourne None si Redis échoue
            - Désérialisation JSON automatique
            - Métrique redis_commands_total{command="get"} incrémentée
        """
        try:
            import time
            start_time = time.time()

            # GET Redis (via méthode async FAIL-OPEN de RedisCacheClient)
            value = await self.redis.cache_get(key)

            # Métriques
            duration = time.time() - start_time
            redis_commands_total.labels(command="get").inc()
            redis_command_duration_seconds.labels(command="get").observe(duration)

            if value is None:
                return None

            # Désérialiser JSON (decode_responses=True → toujours str)
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        except Exception as e:
            # Fail-open : loguer et retourner None
            logger.warning(f"Cache GET failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Enregistre valeur dans cache Redis avec TTL.

        Args:
            key: Clé Redis
            value: Valeur à cacher (dict/list/str/int)
            ttl: Time-to-live en secondes (défaut 5min)

        Returns:
            True si succès, False si échec

        Example:
            >>> cache.set("product:123", {"id": 123, "name": "Assiette"}, ttl=300)
            True

            >>> cache.set("customer:456", customer_dict, ttl=600)
            True

        Notes:
            - Fail-open : retourne False si Redis échoue (ne lève pas exception)
            - Sérialisation JSON automatique pour dict/list
            - TTL = expiration automatique Redis
        """
        try:
            import time
            start_time = time.time()

            # Sérialiser JSON si dict/list
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value, ensure_ascii=False, cls=_DateEncoder)
            else:
                serialized = str(value)

            # SET avec TTL (via méthode async FAIL-OPEN de RedisCacheClient)
            await self.redis.cache_set(key, serialized, ttl)

            # Métriques
            duration = time.time() - start_time
            redis_commands_total.labels(command="set").inc()
            redis_command_duration_seconds.labels(command="set").observe(duration)

            return True

        except Exception as e:
            # Fail-open : loguer et retourner False
            logger.warning(f"Cache SET failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Supprime clé du cache Redis.

        Args:
            key: Clé Redis à supprimer

        Returns:
            True si supprimé, False si échec ou clé inexistante

        Example:
            >>> cache.delete("product:123")
            True

        Notes:
            - Fail-open : retourne False si Redis échoue
            - Idempotent (supprimer clé inexistante = False)
        """
        try:
            import time
            start_time = time.time()

            # DEL Redis (via méthode async FAIL-OPEN de RedisCacheClient)
            result = await self.redis.cache_delete(key)

            # Métriques
            duration = time.time() - start_time
            redis_commands_total.labels(command="del").inc()
            redis_command_duration_seconds.labels(command="del").observe(duration)

            return result

        except Exception as e:
            # Fail-open
            logger.warning(f"Cache DELETE failed for key {key}: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalide toutes les clés matchant un pattern.

        Args:
            pattern: Pattern Redis (ex: "product:*", "customer:123:*")

        Returns:
            Nombre de clés supprimées (0 si échec)

        Example:
            >>> cache.invalidate_pattern("product:*")
            42  # 42 clés product:* supprimées

            >>> cache.invalidate_pattern("reservation:*")
            15

        Notes:
            - Utilise SCAN (pas KEYS) pour éviter bloquer Redis en production
            - Fail-open : retourne 0 si Redis échoue
            - Peut prendre du temps si millions de clés (SCAN itératif)

        Warning:
            - Pattern trop large (ex: "*") peut être lent
            - Préférer patterns spécifiques (ex: "product:*")
        """
        try:
            import time
            start_time = time.time()

            deleted_count = 0

            # SCAN itératif (évite bloquer Redis)
            cursor = 0
            while True:
                cursor, keys = await self.redis.client.scan(cursor, match=pattern, count=100)

                if keys:
                    # Supprimer batch de clés
                    deleted_count += await self.redis.client.delete(*keys)

                if cursor == 0:
                    break

            # Métriques
            duration = time.time() - start_time
            redis_commands_total.labels(command="scan").inc()
            redis_command_duration_seconds.labels(command="scan").observe(duration)

            logger.info(f"Cache invalidated {deleted_count} keys for pattern: {pattern}")
            return deleted_count

        except Exception as e:
            # Fail-open
            logger.warning(f"Cache INVALIDATE_PATTERN failed for pattern {pattern}: {e}")
            return 0

    async def flush_all(self) -> bool:
        """Vide TOUT le cache Redis (DANGEREUX - usage tests uniquement).

        Returns:
            True si succès, False si échec

        Warning:
            - NE JAMAIS utiliser en production
            - Supprime TOUTES les clés Redis (cache + rate limiting + sessions)
            - Usage : tests uniquement (cleanup entre tests)

        Example:
            >>> cache.flush_all()  # Tests uniquement !
            True
        """
        try:
            await self.redis.client.flushdb()
            logger.warning("Cache FLUSHED - All keys deleted")
            return True
        except Exception as e:
            logger.error(f"Cache FLUSH_ALL failed: {e}")
            return False


# P1-03 : decorateur @cached() supprime (code mort — jamais appele dans le codebase)


def cache_invalidate(patterns: List[str]):
    """Décorateur invalidation cache : supprime clés après mutation.

    Pattern write-through : invalider cache APRÈS mutation DB réussie.

    Args:
        patterns: Liste de patterns Redis à invalider (ex: ["product:*", "customer:123:*"])

    Example:
        @cache_invalidate(patterns=["product:*"])
        def update_product(product_id: int, data: dict, tenant_id: int):
            # Update DB
            db.query(Product).filter_by(id=product_id, tenant_id=tenant_id).update(data)
            db.commit()
            # Cache invalidé automatiquement APRÈS commit

        @cache_invalidate(patterns=["customer:1:*", "reservation:*"])
        def delete_customer(customer_id: int, tenant_id: int):
            db.query(Customer).filter_by(id=customer_id, tenant_id=tenant_id).delete()
            db.commit()
            # Cache customer + reservations associées invalidés

    Notes:
        - Invalidation APRÈS fonction (mutation DB d'abord)
        - Fail-open : si invalidation échoue, ne lève pas exception (logged warning)
        - Support patterns multiples (ex: invalider products + reservations)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Exécuter fonction (mutation DB)
            result = func(*args, **kwargs)

            # Invalider cache APRÈS mutation
            cache = CacheService()
            for pattern in patterns:
                cache.invalidate_pattern(pattern)

            return result

        return wrapper
    return decorator


# Singleton global
cache_service = CacheService()
