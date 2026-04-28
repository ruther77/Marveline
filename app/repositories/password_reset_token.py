"""Repository pour les tokens de réinitialisation de mot de passe.

Spec §04-AUTH-FLOWS §4.4 :
    - create()  : stocke le hash SHA-256 du token avec TTL 1h
    - consume() : trouve + marque used=True atomiquement (SELECT FOR UPDATE)
    - cleanup_expired() : purge les tokens expirés/utilisés (maintenance)

Security :
    - Tous les lookups filtrent sur tenant_id (invariant A1)
    - consume() utilise SELECT FOR UPDATE (atomicité anti-race-condition)
    - Tokens expirés ou déjà utilisés → None (pas d'info leakage)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken

logger = logging.getLogger(__name__)

# TTL conforme spec §4.4
PASSWORD_RESET_TTL_SECONDS = 3600  # 1h


class PasswordResetTokenRepository:
    """Repository dédié aux tokens de reset password.

    Responsabilités :
        - Créer des tokens (hash uniquement, jamais le brut)
        - Consommer un token de manière atomique (find + mark_used)
        - Purger les tokens expirés/utilisés

    Multi-tenant :
        - create() : tenant_id obligatoire (invariant A1)
        - consume() : pas de filtre tenant (lookup par hash unique) —
          la double vérification se fait via user_id dans auth.py
        - cleanup_expired() : filtre tenant_id obligatoire
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        token_hash: str,
        account_id: int,
        email: str,
    ) -> PasswordResetToken:
        """Crée un nouveau token de reset password en BD (IAM v2).

        Args:
            token_hash: SHA-256 hex du token brut (64 chars)
            account_id: ID du compte global (IAM v2)
            email: Email destinataire (pour audit)

        Returns:
            Token créé avec expires_at = now + 1h
        """
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=PASSWORD_RESET_TTL_SECONDS)
        token = PasswordResetToken(
            token_hash=token_hash,
            account_id=account_id,
            email=email,
            expires_at=expires_at,
            used=False,
        )
        self.db.add(token)
        self.db.flush()
        logger.debug("Password reset token created: account_id=%s", account_id)
        return token

    def consume(self, token_hash: str) -> Optional[PasswordResetToken]:
        """Consomme atomiquement un token valide (single-use).

        Utilise SELECT FOR UPDATE pour garantir qu'un seul appel concurrent
        peut marquer le token comme utilisé (anti-race-condition).

        Args:
            token_hash: SHA-256 hex du token reçu dans l'URL

        Returns:
            Token trouvé et marqué used=True, ou None si :
                - token inconnu
                - token déjà utilisé (used=True)
                - token expiré (expires_at <= now)
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > now,
            )
            .with_for_update()
        )
        token = self.db.execute(stmt).scalar_one_or_none()
        if not token:
            return None

        token.used = True
        self.db.flush()
        logger.debug("Password reset token consumed: account_id=%s", token.account_id)
        return token

    def cleanup_expired(self, tenant_id: int) -> int:
        """Purge les tokens expirés ou déjà consommés pour un tenant.

        À appeler périodiquement (tâche Celery ou maintenance).

        Args:
            tenant_id: ID du tenant

        Returns:
            Nombre de tokens supprimés
        """
        now = datetime.now(timezone.utc)
        tokens = (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.tenant_id == tenant_id,
                or_(
                    PasswordResetToken.expires_at <= now,
                    PasswordResetToken.used == True,  # noqa: E712
                ),
            )
            .all()
        )
        count = len(tokens)
        for token in tokens:
            self.db.delete(token)
        if count:
            self.db.flush()
            logger.info(
                "Cleaned up %d expired/used password reset tokens for tenant_id=%s",
                count,
                tenant_id,
            )
        return count


class AsyncPasswordResetTokenRepository:
    """Version async de PasswordResetTokenRepository pour FastAPI."""

    def __init__(self, db) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession
        self.db: AsyncSession = db

    async def create(
        self,
        token_hash: str,
        account_id: int,
        email: str,
    ) -> PasswordResetToken:
        """Crée un nouveau token de reset password en BD (async) — IAM v2."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=PASSWORD_RESET_TTL_SECONDS)
        token = PasswordResetToken(
            token_hash=token_hash,
            account_id=account_id,
            email=email,
            expires_at=expires_at,
            used=False,
        )
        self.db.add(token)
        await self.db.flush()
        logger.debug("Password reset token created: account_id=%s", account_id)
        return token

    async def consume(self, token_hash: str) -> Optional[PasswordResetToken]:
        """Consomme atomiquement un token valide (single-use, async)."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > now,
            )
            .with_for_update()
        )
        token = await self.db.scalar(stmt)
        if not token:
            return None
        token.used = True
        await self.db.flush()
        logger.debug("Password reset token consumed: account_id=%s", token.account_id)
        return token

    async def cleanup_expired(self, tenant_id: int) -> int:
        """Purge les tokens expirés ou déjà consommés pour un tenant (async)."""
        now = datetime.now(timezone.utc)
        stmt = select(PasswordResetToken).filter(
            PasswordResetToken.tenant_id == tenant_id,
            or_(
                PasswordResetToken.expires_at <= now,
                PasswordResetToken.used == True,  # noqa: E712
            ),
        )
        result = await self.db.execute(stmt)
        tokens = result.scalars().all()
        count = len(tokens)
        for token in tokens:
            self.db.delete(token)
        if count:
            await self.db.flush()
            logger.info(
                "Cleaned up %d expired/used password reset tokens for tenant_id=%s",
                count,
                tenant_id,
            )
        return count
