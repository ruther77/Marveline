"""Client Redis pour CaroCorp - CSRF tokens et sessions."""
import json
import redis
from redis import Redis
from typing import Optional
from functools import lru_cache

from app.core.config import settings
from app.constants import Limits, RedisKeys, SessionConfig


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

    # ========== Refresh Token Whitelist ==========

    def store_refresh_jti(self, jti: str, user_id: int, tenant_id: int, family_id: str, ttl_seconds: int) -> bool:
        """Stocke un JTI de refresh token dans la whitelist Redis.

        Args:
            jti: JWT ID unique du refresh token
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            family_id: ID de la famille de tokens (pour rotation tracking)
            ttl_seconds: Durée de vie (= durée du refresh token)

        Returns:
            True si stockage réussi
        """
        try:
            key = f"{RedisKeys.REFRESH_WHITELIST}{jti}"
            data = json.dumps({"user_id": user_id, "tenant_id": tenant_id, "family_id": family_id})
            return self.client.setex(key, ttl_seconds, data)
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def get_refresh_jti(self, jti: str) -> Optional[dict]:
        """Vérifie si un JTI de refresh token est dans la whitelist.

        Returns:
            Dict {user_id, tenant_id, family_id} ou None si absent/révoqué
        """
        try:
            key = f"{RedisKeys.REFRESH_WHITELIST}{jti}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return None

    def revoke_refresh_jti(self, jti: str) -> bool:
        """Révoque un JTI de refresh token (supprime de la whitelist).

        Returns:
            True si supprimé, False sinon
        """
        try:
            key = f"{RedisKeys.REFRESH_WHITELIST}{jti}"
            return self.client.delete(key) > 0
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    # ========== Access Token Blacklist ==========

    def blacklist_access_jti(self, jti: str, ttl_seconds: int) -> bool:
        """Ajoute un JTI d'access token à la blacklist.

        Args:
            jti: JWT ID de l'access token à invalider
            ttl_seconds: TTL = temps restant avant expiration naturelle du token

        Returns:
            True si ajouté
        """
        try:
            key = f"{RedisKeys.ACCESS_BLACKLIST}{jti}"
            return self.client.setex(key, ttl_seconds, "1")
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def is_access_blacklisted(self, jti: str) -> bool:
        """Vérifie si un JTI d'access token est dans la blacklist.

        Returns:
            True si blacklisté
        """
        try:
            key = f"{RedisKeys.ACCESS_BLACKLIST}{jti}"
            return self.client.exists(key) == 1
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    # ========== Token Family (Rotation Tracking) ==========

    def store_token_family(self, family_id: str, user_id: int, ttl_seconds: int) -> bool:
        """Crée une famille de tokens (pour tracking de rotation).

        Args:
            family_id: UUID de la famille
            user_id: ID du user propriétaire
            ttl_seconds: Durée de vie de la famille

        Returns:
            True si créé
        """
        try:
            key = f"{RedisKeys.TOKEN_FAMILY}{family_id}"
            data = json.dumps({"user_id": user_id, "active": True})
            return self.client.setex(key, ttl_seconds, data)
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def get_token_family(self, family_id: str) -> Optional[dict]:
        """Récupère les données d'une famille de tokens.

        Returns:
            Dict {user_id, active} ou None
        """
        try:
            key = f"{RedisKeys.TOKEN_FAMILY}{family_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return None

    def revoke_token_family(self, family_id: str) -> bool:
        """Révoque une famille de tokens entière (replay detected).

        Met active=False pour marquer la famille comme compromise.

        Returns:
            True si révoqué
        """
        try:
            key = f"{RedisKeys.TOKEN_FAMILY}{family_id}"
            data = self.client.get(key)
            if not data:
                return False
            family_data = json.loads(data)
            family_data["active"] = False
            ttl = self.client.ttl(key)
            if ttl > 0:
                self.client.setex(key, ttl, json.dumps(family_data))
            return True
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return False

    def revoke_all_refresh_tokens(self, user_id: int) -> int:
        """Révoque tous les refresh tokens d'un utilisateur.

        Returns:
            Nombre de tokens révoqués
        """
        try:
            pattern = f"{RedisKeys.REFRESH_WHITELIST}*"
            count = 0
            for key in self.client.scan_iter(match=pattern, count=100):
                data = self.client.get(key)
                if data:
                    token_data = json.loads(data)
                    if token_data.get("user_id") == user_id:
                        self.client.delete(key)
                        count += 1
            return count
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return 0

    # ========== Brute Force Counters ==========

    def increment_brute_force(self, key_prefix: str, identifier: str, ttl_seconds: int) -> int:
        """Incrémente un compteur brute force avec TTL glissant.

        Args:
            key_prefix: Préfixe Redis (bf_email: ou bf_ip:)
            identifier: Email ou IP
            ttl_seconds: Durée de la fenêtre de comptage

        Returns:
            Nombre de tentatives après incrément
        """
        try:
            key = f"{key_prefix}{identifier}"
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            results = pipe.execute()
            return results[0]  # valeur après INCR
        except (redis.ConnectionError, redis.TimeoutError):
            return 0

    def get_brute_force_count(self, key_prefix: str, identifier: str) -> int:
        """Récupère le nombre de tentatives brute force.

        Returns:
            Nombre de tentatives (0 si clé absente)
        """
        try:
            key = f"{key_prefix}{identifier}"
            count = self.client.get(key)
            return int(count) if count else 0
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return 0

    def reset_brute_force(self, key_prefix: str, identifier: str) -> bool:
        """Reset un compteur brute force (après login réussi).

        Returns:
            True si supprimé
        """
        try:
            key = f"{key_prefix}{identifier}"
            self.client.delete(key)
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def set_brute_force_lock(self, identifier: str, ttl_seconds: int) -> bool:
        """Verrouille un identifiant (email) pour brute force.

        Returns:
            True si verrouillé
        """
        try:
            key = f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
            return self.client.setex(key, ttl_seconds, "1")
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def is_brute_force_locked(self, identifier: str) -> bool:
        """Vérifie si un identifiant est verrouillé.

        Returns:
            True si verrouillé
        """
        try:
            key = f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
            return self.client.exists(key) == 1
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def get_brute_force_lock_ttl(self, identifier: str) -> int:
        """Retourne le TTL restant du lock brute force.

        Returns:
            Secondes restantes (0 si pas de lock)
        """
        try:
            key = f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
            ttl = self.client.ttl(key)
            return max(ttl, 0)
        except (redis.ConnectionError, redis.TimeoutError):
            return 0

    def set_brute_force_alert_sent(self, identifier: str, ttl_seconds: int) -> bool:
        """Marque qu'une alerte admin a été envoyée pour cet identifiant.

        Empêche le spam d'alertes (idempotence).

        Returns:
            True si marqué (première fois), False si déjà marqué
        """
        try:
            key = f"{RedisKeys.BRUTE_FORCE_ALERT}{identifier}"
            # SET NX = seulement si la clé n'existe pas
            return self.client.set(key, "1", ex=ttl_seconds, nx=True)
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    # ========== Sessions ==========

    def store_session(self, session_id: str, data: dict, ttl_seconds: int = SessionConfig.SESSION_TTL_SECONDS) -> bool:
        """Stocke une session utilisateur dans Redis + met à jour l'index user.

        Args:
            session_id: ID de la session (UUID)
            data: Données de la session (doit contenir user_id)
            ttl_seconds: Durée de validité (défaut: 7 jours)

        Returns:
            True si stockage réussi, False sinon
        """
        try:
            key = f"{RedisKeys.SESSION}{session_id}"
            self.client.setex(key, ttl_seconds, json.dumps(data))

            # Mettre à jour l'index user → sessions
            user_id = data.get("user_id")
            if user_id is not None:
                idx_key = f"{RedisKeys.SESSION_USER_INDEX}{user_id}"
                self.client.sadd(idx_key, session_id)
                self.client.expire(idx_key, ttl_seconds)

            return True
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def get_session(self, session_id: str) -> Optional[dict]:
        """Récupère une session utilisateur depuis Redis.

        Args:
            session_id: ID de la session

        Returns:
            Données de la session ou None si inexistante/expirée
        """
        try:
            key = f"{RedisKeys.SESSION}{session_id}"
            data = self.client.get(key)
            return json.loads(data) if data else None
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return None

    def delete_session(self, session_id: str, user_id: int) -> bool:
        """Supprime une session et met à jour l'index user.

        Args:
            session_id: ID de la session
            user_id: ID de l'utilisateur (pour l'index)

        Returns:
            True si supprimé
        """
        try:
            key = f"{RedisKeys.SESSION}{session_id}"
            self.client.delete(key)

            idx_key = f"{RedisKeys.SESSION_USER_INDEX}{user_id}"
            self.client.srem(idx_key, session_id)
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def list_user_sessions(self, user_id: int) -> list[dict]:
        """Liste toutes les sessions actives d'un utilisateur.

        Nettoie automatiquement les entrées stale (sessions expirées).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste des sessions actives (peut être vide)
        """
        try:
            idx_key = f"{RedisKeys.SESSION_USER_INDEX}{user_id}"
            session_ids = self.client.smembers(idx_key)

            sessions = []
            stale_ids = []
            for sid in session_ids:
                data = self.get_session(sid)
                if data:
                    sessions.append(data)
                else:
                    stale_ids.append(sid)

            # Nettoyer les entrées stale
            if stale_ids:
                self.client.srem(idx_key, *stale_ids)

            return sessions
        except (redis.ConnectionError, redis.TimeoutError):
            return []

    def delete_all_user_sessions(self, user_id: int) -> int:
        """Supprime toutes les sessions d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de sessions supprimées
        """
        try:
            idx_key = f"{RedisKeys.SESSION_USER_INDEX}{user_id}"
            session_ids = self.client.smembers(idx_key)

            count = 0
            for sid in session_ids:
                key = f"{RedisKeys.SESSION}{sid}"
                self.client.delete(key)
                count += 1

            self.client.delete(idx_key)
            return count
        except (redis.ConnectionError, redis.TimeoutError):
            return 0

    def update_session_activity(self, session_id: str, ttl_seconds: int = SessionConfig.SESSION_TTL_SECONDS) -> bool:
        """Met à jour last_activity et refresh le TTL d'une session.

        Args:
            session_id: ID de la session
            ttl_seconds: Nouveau TTL (défaut: 7 jours)

        Returns:
            True si mis à jour, False si session inexistante
        """
        try:
            from datetime import datetime, timezone

            key = f"{RedisKeys.SESSION}{session_id}"
            data = self.client.get(key)
            if not data:
                return False

            session_data = json.loads(data)
            session_data["last_activity"] = datetime.now(timezone.utc).isoformat()
            self.client.setex(key, ttl_seconds, json.dumps(session_data))
            return True
        except (redis.ConnectionError, redis.TimeoutError, ValueError):
            return False

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
