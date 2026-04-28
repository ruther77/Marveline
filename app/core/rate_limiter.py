"""Rate Limiter pour protection DDoS CaroCorp.

Fournit un rate limiting multi-niveaux basé sur Redis pour protéger l'API
contre les abus et les attaques DDoS.

Stratégie multi-niveaux :
- Global IP : 1000 req/min (protection brute force générale)
- Login : 5 req/min (protection brute force authentification)
- User authentifié : 200 req/min (quotas utilisateur)
- Mutations (POST/PUT/DELETE) : 100 req/min (protection write-heavy abuse)
- Reads (GET) : 300 req/min (protection read-heavy abuse)

Pattern Redis :
- INCR atomique pour compteur distribué
- TTL automatique pour fenêtre glissante
- Key pattern : rate_limit:{scope}:{identifier}:{timestamp}

Example:
    >>> from app.core.rate_limiter import RateLimiter
    >>> from app.core.redis import redis_client
    >>>
    >>> limiter = RateLimiter(redis_client)
    >>> allowed, metadata = limiter.check_rate_limit(
    ...     key="rate_limit:ip:192.168.1.1",
    ...     limit=100,
    ...     window_seconds=60
    ... )
    >>> if not allowed:
    ...     print(f"Rate limit exceeded. Retry after {metadata['retry_after']}s")

Notes:
    - Redis INCR est atomique (safe pour concurrency)
    - TTL garantit nettoyage automatique (pas de memory leak)
    - Reset timestamp = current_time + window_seconds
    - Headers 429 conformes RFC 6585
"""
import logging
import time
from typing import Tuple, Dict, Any
from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger(__name__)

from app.constants import RateLimitScope, RedisKeys


class RateLimiter:
    """Rate limiter distribué basé sur Redis.

    Utilise Redis INCR + EXPIRE pour compteurs atomiques distribués.
    Supporte fenêtres glissantes et quotas multi-niveaux.

    Attributes:
        redis_client: Client Redis pour stockage compteurs
    """

    def __init__(self, redis_client: AsyncRedis):
        """Initialise le rate limiter.

        Args:
            redis_client: Instance Redis client
        """
        self.redis = redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> Tuple[bool, Dict[str, Any]]:
        """Vérifie si une requête est autorisée selon le rate limit.

        Utilise Redis INCR atomique pour incrémenter le compteur.
        Si premier accès (count=1), définit TTL = window_seconds.

        Args:
            key: Clé Redis unique (ex: "rate_limit:ip:192.168.1.1")
            limit: Nombre maximum de requêtes autorisées
            window_seconds: Fenêtre temporelle en secondes (ex: 60 pour 1 minute)

        Returns:
            Tuple (allowed, metadata) où :
            - allowed (bool): True si requête autorisée, False si limite atteinte
            - metadata (dict): Informations rate limit avec :
                - limit (int): Limite maximale
                - remaining (int): Nombre de requêtes restantes (>= 0)
                - reset (int): Timestamp Unix quand compteur reset
                - retry_after (int): Secondes à attendre avant retry (si blocked)
                - current (int): Nombre de requêtes actuelles

        Example:
            >>> allowed, meta = limiter.check_rate_limit(
            ...     key="rate_limit:login:user@example.com",
            ...     limit=5,
            ...     window_seconds=60
            ... )
            >>> print(f"Allowed: {allowed}")
            >>> print(f"Remaining: {meta['remaining']}/{meta['limit']}")
            >>> print(f"Reset at: {meta['reset']}")

        Notes:
            - INCR est atomique (thread-safe, concurrent-safe)
            - TTL définit uniquement au premier INCR (count=1)
            - Si Redis down, retourne (False, {}) FAIL-CLOSED (securite > disponibilite)
            - Fenêtre glissante approximative (précision = 1 seconde)
        """
        try:
            # INCR atomique (retourne nouvelle valeur)
            current_count = await self.redis.incr(key)

            # Si premier accès, définir TTL
            if current_count == 1:
                await self.redis.expire(key, window_seconds)

            # Récupérer TTL restant pour calculer reset timestamp
            ttl = await self.redis.ttl(key)
            if ttl == -1:
                # Pas de TTL défini (race condition possible), le définir
                await self.redis.expire(key, window_seconds)
                ttl = window_seconds

            # Calculer timestamps
            current_time = int(time.time())
            reset_timestamp = current_time + ttl

            # Vérifier si limite dépassée
            allowed = current_count <= limit

            # Calculer remaining (min 0 pour éviter valeurs négatives)
            remaining = max(0, limit - current_count)

            metadata = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_timestamp,
                "retry_after": ttl if not allowed else 0,
                "current": current_count,
            }

            return allowed, metadata

        except Exception as e:
            # FAIL-CLOSED : Redis down = bloquer (securite > disponibilite)
            # Le monitoring doit alerter sur cette erreur immediatement
            logger.critical("Rate limiter Redis DOWN — FAIL-CLOSED (503): %s", e)
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset": int(time.time()) + 30,
                "retry_after": 30,
                "current": 0,
                "error": "rate_limiter_unavailable",
            }

    def get_scope_config(self, scope: str) -> Tuple[int, int]:
        """Retourne (limit, window_seconds) pour un scope donné.

        Scopes supportés :
        - "global_ip" : 1000 req/min (anti-DDoS général)
        - "login" : 5 req/min (anti brute force auth)
        - "user_authenticated" : 200 req/min (quota user)
        - "mutations" : 100 req/min (POST/PUT/DELETE)
        - "reads" : 300 req/min (GET)

        Args:
            scope: Nom du scope

        Returns:
            Tuple (limit, window_seconds)

        Raises:
            ValueError: Si scope inconnu

        Example:
            >>> limit, window = limiter.get_scope_config("login")
            >>> print(f"Login: {limit} req/{window}s")
            Login: 5 req/60s
        """
        configs = {
            RateLimitScope.GLOBAL_IP: (1000, 60),  # 1000 req/minute
            RateLimitScope.LOGIN: (5, 60),  # 5 req/minute (strict)
            RateLimitScope.USER_AUTHENTICATED: (200, 60),  # 200 req/minute (Marveline)
            RateLimitScope.API_KEY_AUTHENTICATED: (1000, 60),  # 1000 req/minute (M2M)
            RateLimitScope.MUTATIONS: (100, 60),  # 100 mutations/minute
            RateLimitScope.READS: (300, 60),  # 300 reads/minute
            # App-specific — quotas adaptés au profil d'usage
            RateLimitScope.EPICERIE_AUTHENTICATED: (500, 60),  # POS scan haute fréquence
            RateLimitScope.EPICERIE_MUTATIONS: (300, 60),  # Ventes POS rapides
            RateLimitScope.RESTAURANT_AUTHENTICATED: (500, 60),  # Service salle rapide
            RateLimitScope.RESTAURANT_MUTATIONS: (300, 60),  # Commandes cuisine temps réel
        }

        if scope not in configs:
            raise ValueError(f"Unknown rate limit scope: {scope}")

        return configs[scope]

    def build_key(self, scope: str, identifier: str) -> str:
        """Construit une clé Redis pour un scope et identifier.

        Args:
            scope: Type de rate limit (ex: "global_ip", "login")
            identifier: Identifiant unique (ex: IP, user_id, email)

        Returns:
            Clé Redis formatée

        Example:
            >>> key = limiter.build_key("global_ip", "192.168.1.1")
            >>> print(key)
            rate_limit:global_ip:192.168.1.1

        Notes:
            - Pattern : rate_limit:{scope}:{identifier}
            - Identifier doit être unique et stable
            - Éviter caractères spéciaux dans identifier
        """
        return f"{RedisKeys.RATE_LIMIT}{scope}:{identifier}"
