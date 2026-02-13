"""Client Redis pour CaroCorp - CSRF tokens et sessions."""
import redis
from redis import Redis
from typing import Optional
from functools import lru_cache

from app.core.config import settings
from app.constants import Limits, RedisKeys


class RedisClient:
    """Singleton Redis client avec connexion pool.

    Responsabilités:
        - CSRF token storage et validation
        - Session management
        - Rate limiting (future)
        - Refresh tokens storage (future)

    Pattern:
        - Connection pool pour performance
        - Singleton via lru_cache
        - Reconnexion automatique
    """

    def __init__(self):
        """Initialise le client Redis avec connection pool."""
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        """Retourne le client Redis (lazy initialization)."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
        return self._client

    def ping(self) -> bool:
        """Vérifie la connexion Redis.

        Returns:
            True si connexion active, False sinon
        """
        try:
            return self.client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    # ========== CSRF Tokens ==========

    def store_csrf_token(self, user_id: int, token: str, ttl_seconds: int = 900) -> bool:
        """Stocke un token CSRF dans Redis avec TTL.

        Args:
            user_id: ID de l'utilisateur
            token: Token CSRF à stocker
            ttl_seconds: Durée de validité (défaut: 15 minutes)

        Returns:
            True si stockage réussi, False sinon

        Key pattern:
            csrf:{user_id}:{token} = "1"

        Note:
            - Un utilisateur peut avoir plusieurs tokens actifs (multi-onglets)
            - TTL automatique (expiration après 15 min)
            - Token unique (secrets.token_urlsafe)
        """
        try:
            key = f"{RedisKeys.CSRF_TOKEN}{user_id}:{token}"
            return self.client.setex(key, ttl_seconds, "1")
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def validate_csrf_token(self, user_id: int, token: str) -> bool:
        """Valide un token CSRF depuis Redis.

        Args:
            user_id: ID de l'utilisateur
            token: Token CSRF à valider

        Returns:
            True si token valide (existe dans Redis), False sinon

        Security:
            - Vérifie existence du token
            - Vérifie que le token appartient à cet utilisateur
            - Ne révèle pas si l'utilisateur existe (timing attack protection)
        """
        try:
            key = f"{RedisKeys.CSRF_TOKEN}{user_id}:{token}"
            return self.client.exists(key) == 1
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def revoke_csrf_token(self, user_id: int, token: str) -> bool:
        """Révoque un token CSRF spécifique.

        Args:
            user_id: ID de l'utilisateur
            token: Token CSRF à révoquer

        Returns:
            True si révocation réussie, False sinon
        """
        try:
            key = f"{RedisKeys.CSRF_TOKEN}{user_id}:{token}"
            return self.client.delete(key) > 0
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def revoke_all_csrf_tokens(self, user_id: int) -> int:
        """Révoque tous les tokens CSRF d'un utilisateur (logout).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de tokens révoqués
        """
        try:
            pattern = f"{RedisKeys.CSRF_TOKEN}{user_id}:*"
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                return self.client.delete(*keys)
            return 0
        except (redis.ConnectionError, redis.TimeoutError):
            return 0

    # ========== Sessions (future) ==========

    def store_session(self, session_id: str, data: dict, ttl_seconds: int = Limits.SESSION_TIMEOUT_SECONDS) -> bool:
        """Stocke une session utilisateur dans Redis.

        Args:
            session_id: ID de la session
            data: Données de la session (dict)
            ttl_seconds: Durée de validité (défaut: 1 heure)

        Returns:
            True si stockage réussi, False sinon

        Note:
            - Utilise JSON pour stocker les données
            - TTL automatique
        """
        try:
            import json
            key = f"{RedisKeys.SESSION}{session_id}"
            return self.client.setex(key, ttl_seconds, json.dumps(data))
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def get_session(self, session_id: str) -> Optional[dict]:
        """Récupère une session utilisateur depuis Redis.

        Args:
            session_id: ID de la session

        Returns:
            Données de la session ou None si inexistante
        """
        try:
            import json
            key = f"{RedisKeys.SESSION}{session_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return None

    # ========== Health Check ==========

    def health_check(self) -> dict:
        """Vérifie la santé de la connexion Redis.

        Returns:
            Dict avec status et informations

        Example:
            {
                "status": "healthy",
                "connected": True,
                "info": {...}
            }
        """
        try:
            ping_result = self.ping()
            if not ping_result:
                return {"status": "unhealthy", "connected": False}

            info = self.client.info("server")
            return {
                "status": "healthy",
                "connected": True,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds")
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }


@lru_cache()
def get_redis_client() -> RedisClient:
    """Singleton pour le client Redis.

    Returns:
        Instance unique de RedisClient

    Usage:
        redis_client = get_redis_client()
        redis_client.store_csrf_token(user_id, token)
    """
    return RedisClient()


# Instance globale (singleton via lru_cache)
redis_client = get_redis_client()
