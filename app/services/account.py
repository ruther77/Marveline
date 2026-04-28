"""Service Account — identité globale (IAM v2).

Responsabilités :
    - Création de comptes globaux
    - Vérification credentials (email + password, timing-safe)
    - Changement/reset de mot de passe
    - Migration transparente bcrypt → Argon2id

Isolation tenant : aucune — les comptes sont globaux.
L'isolation se fait au niveau TenantMembership (app/services/membership.py).
"""
import hashlib
import logging
import secrets
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_client, redis_sec
from app.core.security import (
    DUMMY_HASH,
    get_password_hash,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.constants import ErrorMessages, Limits, RedisKeys
from app.models.account import Account
from app.repositories.account import AsyncAccountRepository
from app.repositories.password_reset_token import AsyncPasswordResetTokenRepository
from app.services.hibp import is_password_compromised
from app.services.notification import notification_service

logger = logging.getLogger(__name__)


class AccountService:
    """Service de gestion des comptes globaux (IAM v2 — sans filtre tenant)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._repo = AsyncAccountRepository(db)

    async def get_by_id(self, account_id: int) -> Optional[Account]:
        """Récupère un compte par ID."""
        return await self._repo.get_by_id(account_id)

    async def get_active_by_id(self, account_id: int) -> Optional[Account]:
        """Récupère un compte actif par ID."""
        return await self._repo.get_active_by_id(account_id)

    async def verify_credentials(
        self,
        email: str,
        password: str,
    ) -> Optional[Account]:
        """Vérifie email + password, retourne l'Account ou None.

        Toujours exécuter DUMMY_HASH si compte absent OU sans password (OAuth-only)
        — timing-safe contre user enumeration.
        Rehash transparent bcrypt → Argon2id si nécessaire.
        """
        account = await self._repo.get_by_email(email.lower().strip())
        if not account:
            verify_password(password, DUMMY_HASH)
            return None

        # S1.T9 (F296) — Compte OAuth-only : hashed_password=None.
        # `verify_password(password, None)` levait TypeError 500 + permettait
        # de distinguer OAuth-only (500) vs identifiants invalides (401).
        # Fix : appeler verify_password sur DUMMY_HASH (timing-safe) puis None.
        if not account.hashed_password:
            verify_password(password, DUMMY_HASH)
            return None

        if not verify_password(password, account.hashed_password):
            return None

        if needs_rehash(account.hashed_password):
            account.hashed_password = get_password_hash(password)
            await self.db.flush()

        return account

    async def create_account(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> Account:
        """Crée un nouveau compte global (hors tenant).

        409 si email déjà enregistré (global).
        400 si password trop faible.
        """
        email = email.lower().strip()

        if await self._repo.email_exists(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorMessages.EMAIL_ALREADY_EXISTS,
            )

        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        account = Account(
            external_id=str(uuid.uuid4()),
            email=email,
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        return await self._repo.create(account)

    async def change_password(
        self,
        account_id: int,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change le mot de passe d'un compte (spec §4.5).

        Séquence : brute force check → verify old → forbid same → strength → HIBP → update.
        """
        brute_key = RedisKeys.brute_force_pwd_change(account_id)
        attempts = await redis_sec.get_brute_force_count(brute_key)
        if attempts >= Limits.PASSWORD_CHANGE_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ErrorMessages.PASSWORD_CHANGE_RATE_LIMITED,
            )

        account = await self._repo.get_by_id(account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorMessages.USER_NOT_FOUND,
            )

        if not verify_password(current_password, account.hashed_password):
            await redis_sec.increment_brute_force(
                brute_key, Limits.PASSWORD_CHANGE_WINDOW_SECONDS
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ErrorMessages.CURRENT_PASSWORD_INCORRECT,
            )

        if verify_password(new_password, account.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_SAME_AS_CURRENT,
            )

        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        if is_password_compromised(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_COMPROMISED,
            )

        account.hashed_password = get_password_hash(new_password)
        account.password_change_required = False
        await self._repo.flush(account)
        await redis_sec.reset_brute_force(brute_key)
        return True

    async def forgot_password(
        self,
        email: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Demande de reset — anti-énumération (toujours True en sortie)."""
        email = email.lower().strip()

        rate_count = await redis_client.increment_password_reset_rate(email)
        if rate_count > Limits.PASSWORD_RESET_MAX_PER_EMAIL:
            return True  # silencieux

        account = await self._repo.get_active_by_email(email)
        if not account:
            return True  # silencieux — anti info-leakage

        raw_bytes = secrets.token_bytes(32)
        raw_token = raw_bytes.hex()
        token_hash = hashlib.sha256(raw_bytes).hexdigest()

        await AsyncPasswordResetTokenRepository(self.db).create(
            token_hash=token_hash,
            account_id=account.id,
            email=email,
        )

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        notification_service.send_password_reset_email(email, reset_url)
        return True

    async def reset_password(
        self,
        token: str,
        new_password: str,
    ) -> bool:
        """Réinitialise le mot de passe via token email (spec §4.4)."""
        try:
            raw_bytes = bytes.fromhex(token)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )

        token_hash = hashlib.sha256(raw_bytes).hexdigest()
        reset_token = await AsyncPasswordResetTokenRepository(self.db).consume(token_hash)
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )

        account_id = reset_token.account_id
        if not account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )

        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        if is_password_compromised(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_COMPROMISED,
            )

        account = await self._repo.get_by_id(account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.PASSWORD_RESET_TOKEN_INVALID,
            )

        account.hashed_password = get_password_hash(new_password)
        account.password_change_required = False
        await self._repo.flush(account)
        return True

    async def flag_password_compromised(self, account_id: int) -> None:
        """Marque password_change_required=True si HIBP détecte une compromission."""
        account = await self._repo.get_by_id(account_id)
        if account and not account.password_change_required:
            account.password_change_required = True
            await self.db.flush()
