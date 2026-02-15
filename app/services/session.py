"""Service de gestion des sessions utilisateur (Redis-backed).

Responsabilités:
    - Créer une session au login (metadata: IP, user-agent, family_id)
    - Lister les sessions actives d'un utilisateur
    - Révoquer une session (+ tokens associés)
    - Révoquer toutes les sessions (force re-login partout)
    - Mise à jour last_activity
    - Enforcement max sessions par user (éviction de la plus ancienne)

Architecture:
    - Sessions stockées dans Redis (pas en DB) car éphémères
    - Index user → sessions via Redis SET (session_idx:{user_id})
    - TTL aligné avec refresh token (7 jours)
    - Chaque session liée à un token family_id (pour revocation coordonnée)

Fichiers liés:
    - app/core/redis.py (store_session, get_session, etc.)
    - app/services/token.py (revocation tokens lors de revocation session)
    - app/constants/security.py (SessionConfig, RedisKeys)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.redis import redis_client
from app.constants import SessionConfig, RedisKeys

logger = logging.getLogger(__name__)


class SessionService:
    """Service de gestion des sessions utilisateur.

    Patterns:
        - Session créée au login, supprimée au logout
        - Max 5 sessions par user (la plus ancienne est évincée)
        - Chaque session liée à un family_id (token family)
        - Revocation session = revocation famille de tokens associée
    """

    # ========== Create ==========

    def create_session(
        self,
        user_id: int,
        tenant_id: int,
        family_id: str,
        ip_address: str,
        user_agent: str,
    ) -> str:
        """Crée une nouvelle session utilisateur dans Redis.

        Enforce max sessions : si l'utilisateur a déjà MAX_SESSIONS_PER_USER
        sessions actives, la plus ancienne est évincée (tokens révoqués).

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            family_id: ID de la famille de tokens (pour revocation coordonnée)
            ip_address: IP du client
            user_agent: User-Agent du client

        Returns:
            session_id (UUID string)
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "family_id": family_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": now,
            "last_activity": now,
        }

        # Enforce max sessions avant de créer la nouvelle
        self._enforce_max_sessions(user_id)

        # Stocker la session dans Redis
        redis_client.store_session(
            session_id=session_id,
            data=session_data,
            ttl_seconds=SessionConfig.SESSION_TTL_SECONDS,
        )

        logger.info(
            "Session created: session=%s user=%s tenant=%s ip=%s",
            session_id, user_id, tenant_id, ip_address,
        )

        return session_id

    # ========== Read ==========

    def get_session(self, session_id: str) -> Optional[dict]:
        """Récupère une session par son ID.

        Args:
            session_id: ID de la session

        Returns:
            Dict avec les données de session ou None si inexistante
        """
        return redis_client.get_session(session_id)

    def get_session_by_family(self, user_id: int, family_id: str) -> Optional[dict]:
        """Trouve une session par son family_id (pour logout).

        Scanne les sessions de l'utilisateur (max 5) pour trouver
        celle associée à la famille de tokens.

        Args:
            user_id: ID de l'utilisateur
            family_id: ID de la famille de tokens

        Returns:
            Dict session ou None si non trouvée
        """
        sessions = redis_client.list_user_sessions(user_id)
        for session in sessions:
            if session.get("family_id") == family_id:
                return session
        return None

    def list_sessions(self, user_id: int) -> list[dict]:
        """Liste toutes les sessions actives d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste des sessions (triées par created_at, plus récente en premier)
        """
        sessions = redis_client.list_user_sessions(user_id)
        # Trier par created_at décroissant (plus récente en premier)
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions

    # ========== Revoke ==========

    def revoke_session(self, session_id: str, user_id: int) -> bool:
        """Révoque une session et les tokens associés.

        1. Récupère les données de session (pour family_id)
        2. Révoque la famille de tokens associée
        3. Supprime la session de Redis

        Args:
            session_id: ID de la session à révoquer
            user_id: ID de l'utilisateur (pour vérification + index)

        Returns:
            True si session trouvée et révoquée, False sinon
        """
        session_data = redis_client.get_session(session_id)
        if not session_data:
            return False

        # Vérifier que la session appartient bien au user
        if session_data.get("user_id") != user_id:
            logger.warning(
                "Session revoke denied: session=%s belongs to user=%s, not user=%s",
                session_id, session_data.get("user_id"), user_id,
            )
            return False

        # Révoquer la famille de tokens associée
        family_id = session_data.get("family_id")
        if family_id:
            self._revoke_token_family(family_id)

        # Supprimer la session
        redis_client.delete_session(session_id, user_id)

        logger.info(
            "Session revoked: session=%s user=%s family=%s",
            session_id, user_id, family_id,
        )

        return True

    def revoke_all_sessions(self, user_id: int) -> int:
        """Révoque toutes les sessions d'un utilisateur (force re-login partout).

        Pour chaque session active:
        1. Révoque la famille de tokens associée
        2. Supprime la session

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de sessions révoquées
        """
        sessions = redis_client.list_user_sessions(user_id)

        for session in sessions:
            family_id = session.get("family_id")
            if family_id:
                self._revoke_token_family(family_id)

        count = redis_client.delete_all_user_sessions(user_id)

        if count > 0:
            logger.info(
                "All sessions revoked: user=%s count=%s",
                user_id, count,
            )

        return count

    # ========== Update ==========

    def update_activity(self, session_id: str) -> bool:
        """Met à jour le timestamp last_activity d'une session.

        Appelé périodiquement (ex: dans middleware) pour tracker l'activité.

        Args:
            session_id: ID de la session

        Returns:
            True si mis à jour, False si session inexistante
        """
        return redis_client.update_session_activity(session_id)

    # ========== Private ==========

    def _enforce_max_sessions(self, user_id: int) -> None:
        """Évince les sessions les plus anciennes si le max est atteint.

        Stratégie: si user a >= MAX sessions, supprimer la plus ancienne
        (par created_at) pour faire de la place.
        """
        sessions = redis_client.list_user_sessions(user_id)

        if len(sessions) < SessionConfig.MAX_SESSIONS_PER_USER:
            return

        # Trier par created_at croissant (plus ancienne en premier)
        sessions.sort(key=lambda s: s.get("created_at", ""))

        # Nombre de sessions à évincer pour faire de la place
        to_evict = len(sessions) - SessionConfig.MAX_SESSIONS_PER_USER + 1

        for session in sessions[:to_evict]:
            sid = session.get("session_id")
            family_id = session.get("family_id")
            if sid:
                if family_id:
                    self._revoke_token_family(family_id)
                redis_client.delete_session(sid, user_id)
                logger.info(
                    "Session evicted (max reached): session=%s user=%s",
                    sid, user_id,
                )

    @staticmethod
    def _revoke_token_family(family_id: str) -> None:
        """Révoque une famille de tokens via le client Redis.

        Marque la famille comme inactive (bloque les refresh futurs).
        """
        redis_client.revoke_token_family(family_id)


# Singleton
session_service = SessionService()
