"""Service de gestion des tokens JWT : whitelist, blacklist, rotation, replay detection.

Responsabilités:
    - Refresh token whitelist (JTI → Redis, vérifié à chaque refresh)
    - Access token blacklist (JTI → Redis au logout, vérifié à chaque requête)
    - Token family rotation (chaque refresh émet un nouveau refresh token)
    - Replay detection (réutilisation d'un ancien refresh → toute la famille révoquée)

Architecture:
    - Refresh tokens: WHITELIST (JTI stocké à l'émission, supprimé au logout/rotation)
    - Access tokens: BLACKLIST (JTI ajouté au logout, TTL = temps restant)
    - Token families: tracking de rotation (family_id partagé entre refresh successifs)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.redis import redis_client
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.constants import Limits

logger = logging.getLogger(__name__)

# TTL du refresh token en secondes
REFRESH_TTL_SECONDS = Limits.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


class TokenService:
    """Service de gestion avancée des tokens JWT.

    Patterns:
        - Refresh whitelist: seuls les JTI connus de Redis sont acceptés
        - Access blacklist: les JTI ajoutés au logout sont rejetés par get_current_user
        - Rotation: chaque refresh() invalide l'ancien refresh et émet un nouveau
        - Replay detection: si un JTI déjà consommé est réutilisé, toute la famille est révoquée
    """

    # ========== Helpers: claims builders (fix M24 — pas de duplication) ==========

    @staticmethod
    def _build_access_claims(user_id: int, tenant_id: int, email: str, role: str) -> dict:
        """Construit les claims pour un access token."""
        return {
            "sub": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "role": role,
        }

    @staticmethod
    def _build_refresh_claims(user_id: int, tenant_id: int, family_id: str) -> dict:
        """Construit les claims pour un refresh token."""
        return {
            "sub": user_id,
            "tenant_id": tenant_id,
            "family_id": family_id,
        }

    # ========== Login: émettre tokens + enregistrer ==========

    def issue_tokens(
        self,
        user_id: int,
        tenant_id: int,
        email: str,
        role: str,
    ) -> tuple[str, str, int]:
        """Émet une paire access+refresh tokens et enregistre dans Redis.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            email: Email de l'utilisateur
            role: Rôle RBAC

        Returns:
            Tuple (access_token, refresh_token, expires_in_seconds)
        """
        family_id = str(uuid.uuid4())

        access_claims = self._build_access_claims(user_id, tenant_id, email, role)
        refresh_claims = self._build_refresh_claims(user_id, tenant_id, family_id)

        access_token = create_access_token(access_claims)
        refresh_token = create_refresh_token(refresh_claims)

        # Extraire JTI du refresh token pour whitelist
        refresh_payload = decode_token(refresh_token)
        refresh_jti = refresh_payload["jti"]

        # Stocker refresh JTI dans whitelist Redis
        redis_client.store_refresh_jti(
            jti=refresh_jti,
            user_id=user_id,
            tenant_id=tenant_id,
            family_id=family_id,
            ttl_seconds=REFRESH_TTL_SECONDS,
        )

        # Créer la famille de tokens
        redis_client.store_token_family(
            family_id=family_id,
            user_id=user_id,
            ttl_seconds=REFRESH_TTL_SECONDS,
        )

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return access_token, refresh_token, expires_in

    # ========== Refresh: rotation + replay detection ==========

    def rotate_refresh_token(
        self,
        old_refresh_token: str,
        user_id: int,
        tenant_id: int,
        email: str,
        role: str,
    ) -> tuple[str, str, int]:
        """Effectue une rotation de refresh token.

        1. Valide que le JTI de l'ancien refresh est dans la whitelist
        2. Vérifie que la famille est encore active (pas de replay)
        3. Invalide l'ancien refresh JTI
        4. Émet un nouveau refresh token dans la même famille
        5. Émet un nouveau access token

        Args:
            old_refresh_token: Refresh token actuel (sera invalidé)
            user_id: ID du user (vérifié depuis DB par l'appelant)
            tenant_id: tenant_id du user
            email: email du user
            role: rôle du user

        Returns:
            Tuple (new_access_token, new_refresh_token, expires_in)

        Raises:
            TokenRevoked: si le refresh JTI n'est plus dans la whitelist
            TokenReplayDetected: si la famille est compromise
        """
        from app.core.exceptions import TokenRevoked, TokenReplayDetected

        old_payload = decode_token(old_refresh_token)
        old_jti = old_payload.get("jti")
        family_id = old_payload.get("family_id")

        if not old_jti or not family_id:
            raise TokenRevoked()

        # Vérifier whitelist Redis
        whitelist_data = redis_client.get_refresh_jti(old_jti)

        if whitelist_data is None:
            # JTI absent = soit révoqué, soit déjà consommé (replay!)
            # Vérifier si la famille existe encore
            family_data = redis_client.get_token_family(family_id)
            if family_data and family_data.get("active"):
                # Famille active mais JTI absent → REPLAY DETECTED
                # Révoquer toute la famille (force re-login)
                logger.warning(
                    "Replay detected: jti=%s family=%s user=%s",
                    old_jti, family_id, user_id,
                )
                self._revoke_family(family_id, user_id)
                raise TokenReplayDetected()

            # Famille inactive ou absente → token simplement révoqué
            raise TokenRevoked()

        # Vérifier que la famille est active
        family_data = redis_client.get_token_family(family_id)
        if not family_data or not family_data.get("active"):
            raise TokenRevoked()

        # ── Rotation: invalider ancien, émettre nouveau ──

        # 1. Supprimer ancien JTI de la whitelist
        redis_client.revoke_refresh_jti(old_jti)

        # 2. Émettre nouveau refresh token (même famille)
        new_refresh_claims = self._build_refresh_claims(user_id, tenant_id, family_id)
        new_refresh_token = create_refresh_token(new_refresh_claims)

        # 3. Enregistrer nouveau JTI
        new_payload = decode_token(new_refresh_token)
        new_jti = new_payload["jti"]

        redis_client.store_refresh_jti(
            jti=new_jti,
            user_id=user_id,
            tenant_id=tenant_id,
            family_id=family_id,
            ttl_seconds=REFRESH_TTL_SECONDS,
        )

        # 4. Émettre nouveau access token
        new_access_claims = self._build_access_claims(user_id, tenant_id, email, role)
        new_access_token = create_access_token(new_access_claims)

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return new_access_token, new_refresh_token, expires_in

    # ========== Logout: révoquer tokens ==========

    def revoke_on_logout(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        """Révoque les tokens lors d'un logout.

        1. Blacklist l'access token (JTI + TTL restant)
        2. Si refresh_token fourni: supprime son JTI de la whitelist

        Args:
            access_token: Access token JWT actuel
            refresh_token: Refresh token JWT (optionnel)
        """
        # Blacklist access token
        try:
            access_payload = decode_token(access_token)
            access_jti = access_payload.get("jti")
            if access_jti:
                # TTL = temps restant avant expiration naturelle
                exp = access_payload.get("exp", 0)
                now = int(datetime.now(timezone.utc).timestamp())
                remaining_ttl = max(exp - now, 1)
                redis_client.blacklist_access_jti(access_jti, remaining_ttl)
        except Exception:
            # Token peut être déjà expiré — on ignore
            pass

        # Révoquer refresh token + désactiver sa famille
        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                refresh_jti = refresh_payload.get("jti")
                family_id = refresh_payload.get("family_id")
                if refresh_jti:
                    redis_client.revoke_refresh_jti(refresh_jti)
                if family_id:
                    redis_client.revoke_token_family(family_id)
            except Exception:
                pass

    def revoke_all_user_tokens(self, user_id: int) -> int:
        """Révoque tous les refresh tokens d'un utilisateur.

        Utilisé pour force-logout de toutes les sessions.

        Returns:
            Nombre de tokens révoqués
        """
        return redis_client.revoke_all_refresh_tokens(user_id)

    # ========== Validation: vérifier blacklist access ==========

    def is_access_blacklisted(self, jti: str) -> bool:
        """Vérifie si un access token JTI est blacklisté.

        Appelé dans get_current_user pour chaque requête authentifiée.

        Args:
            jti: JWT ID de l'access token

        Returns:
            True si blacklisté (token révoqué)
        """
        return redis_client.is_access_blacklisted(jti)

    # ========== Validation: vérifier whitelist refresh ==========

    def is_refresh_whitelisted(self, jti: str) -> bool:
        """Vérifie si un refresh token JTI est dans la whitelist.

        Args:
            jti: JWT ID du refresh token

        Returns:
            True si présent (token valide)
        """
        return redis_client.get_refresh_jti(jti) is not None

    # ========== Private ==========

    def _revoke_family(self, family_id: str, user_id: int) -> None:
        """Révoque une famille de tokens entière (replay detection).

        Marque la famille comme inactive et supprime tous les refresh JTI
        associés à ce user (nuclear option).
        """
        redis_client.revoke_token_family(family_id)
        redis_client.revoke_all_refresh_tokens(user_id)
        logger.warning(
            "Token family revoked: family=%s user=%s — all refresh tokens invalidated",
            family_id, user_id,
        )


# Singleton
token_service = TokenService()
