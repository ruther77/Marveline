"""Service MFA TOTP — setup, verify, recovery codes (async).

Responsabilities:
    - Generate TOTP secret + provisioning URI (QR code)
    - Verify TOTP codes with anti-replay
    - Generate and verify bcrypt-hashed recovery codes
    - Enable/disable MFA for a user
    - MFA step-up for sensitive actions (spec §05.3)

Architecture:
    - TOTP secret encrypted with AES-256-GCM in DB (app.core.crypto)
    - Recovery codes hashed with bcrypt (single-use)
    - Anti-replay via last_totp_window in DB
    - MFA session tokens stored in Redis (5 min TTL)
    - Step-up tokens stored in Redis-SEC (STEPUP_TTL = 900s)

IAM v2:
    - MFADevice is linked to TenantMembership (membership_id) not User
    - All methods take account_id + tenant_id, resolve membership internally

Files:
    - app/core/crypto.py (encrypt/decrypt TOTP secrets)
    - app/models/mfa.py (MFADevice model)
    - app/constants/security.py (MFAConfig)
"""
import json
import logging
import secrets
import time
from typing import Optional

import bcrypt
import pyotp
import redis.exceptions as redis_exc
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_totp_secret, encrypt_totp_secret
from app.core.redis import redis_client
from app.constants import MFAConfig, RedisKeys
from app.constants.errors import ErrorMessages
from app.models.mfa import MFADevice
from app.models.tenant_membership import TenantMembership
from app.repositories.tenant_membership import AsyncTenantMembershipRepository

logger = logging.getLogger(__name__)

# Redis key prefix for MFA session tokens
MFA_SESSION_PREFIX = "mfa_session:"


class MFAService:
    """Service de gestion MFA TOTP (async) — IAM v2.

    Instance-level state only (no class variables) to avoid cross-user leaks.
    Each DB method takes AsyncSession and account_id + tenant_id as parameters.
    MFADevice is linked to TenantMembership (membership_id), not to User directly.
    """

    async def setup_totp(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        email: str,
    ) -> tuple[str, str, list[str]]:
        """Generate a new TOTP secret and provisioning URI.

        If the user already has a pending (not enabled) MFA device, replace it.
        If MFA is already enabled, raise ValueError.

        Args:
            user_id: account_id (IAM v2)
            tenant_id: tenant context

        Returns:
            Tuple of (secret_plaintext, provisioning_uri, recovery_codes)
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)

        result = await db.execute(
            select(MFADevice).filter(
                MFADevice.membership_id == membership_id,
            )
        )
        existing = result.scalars().first()

        if existing and existing.is_enabled:
            raise ValueError("MFA is already enabled for this user")

        if existing and not existing.is_enabled:
            await db.delete(existing)
            await db.flush()

        secret = pyotp.random_base32()

        recovery_codes = [
            secrets.token_hex(MFAConfig.RECOVERY_CODE_LENGTH // 2)
            for _ in range(MFAConfig.RECOVERY_CODE_COUNT)
        ]

        recovery_hashes = []
        for code in recovery_codes:
            hashed = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10))
            recovery_hashes.append(hashed.decode("utf-8"))

        ct, nonce, enc_dek, key_ver = encrypt_totp_secret(secret)

        device = MFADevice(
            membership_id=membership_id,
            encrypted_secret=ct,
            totp_secret_nonce=nonce,
            totp_encrypted_dek=enc_dek,
            totp_key_version=key_ver,
            is_enabled=False,
            recovery_codes_hash=json.dumps(recovery_hashes),
            last_totp_window=None,
        )
        db.add(device)
        await db.flush()

        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        # Issuer name tenant-scoped : charge depuis tenant_settings (fallback global)
        from app.services.invoice_pdf import load_brand_for_tenant
        brand = await load_brand_for_tenant(db, tenant_id)
        issuer = brand.get("mfa_issuer_name") or MFAConfig.ISSUER_NAME
        provisioning_uri = totp.provisioning_uri(name=email, issuer_name=issuer)

        logger.info("MFA setup initiated: account=%s tenant=%s", user_id, tenant_id)
        return secret, provisioning_uri, recovery_codes

    async def verify_setup(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        totp_code: str,
    ) -> bool:
        """Verify the initial TOTP code to complete MFA setup.

        Args:
            user_id: account_id (IAM v2)

        Returns:
            True if code valid and MFA enabled

        Raises:
            ValueError: If no pending MFA device found or code invalid
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)

        result = await db.execute(
            select(MFADevice).filter(
                MFADevice.membership_id == membership_id,
                MFADevice.is_enabled == False,  # noqa: E712
            )
        )
        device = result.scalars().first()

        if not device:
            raise ValueError("No pending MFA setup found")

        secret = decrypt_totp_secret(
            device.encrypted_secret,
            device.totp_secret_nonce,
            device.totp_encrypted_dek,
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)

        if not totp.verify(totp_code, valid_window=MFAConfig.TOTP_WINDOW):
            raise ValueError("Invalid TOTP code")

        current_window = int(time.time()) // MFAConfig.TOTP_PERIOD
        device.is_enabled = True
        device.last_totp_window = current_window
        await db.flush()

        logger.info("MFA enabled: account=%s tenant=%s", user_id, tenant_id)
        return True

    async def verify_totp(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        totp_code: str,
    ) -> bool:
        """Verify a TOTP code for login (MFA step 2).

        Includes anti-replay: rejects codes from the same time window
        as the last accepted code.

        Args:
            user_id: account_id (IAM v2)

        Returns:
            True if code valid

        Raises:
            ValueError: If MFA not enabled, or code invalid/replayed
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)
        # SELECT FOR UPDATE pour atomicité anti-replay (A1/P0-05)
        device = await self._get_enabled_device(db, membership_id, with_for_update=True)
        if not device:
            raise ValueError("MFA is not enabled for this user")

        secret = decrypt_totp_secret(
            device.encrypted_secret,
            device.totp_secret_nonce,
            device.totp_encrypted_dek,
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)

        if not totp.verify(totp_code, valid_window=MFAConfig.TOTP_WINDOW):
            raise ValueError("Invalid TOTP code")

        current_window = int(time.time()) // MFAConfig.TOTP_PERIOD
        if device.last_totp_window is not None and current_window <= device.last_totp_window:
            raise ValueError("TOTP code already used (anti-replay)")

        device.last_totp_window = current_window
        await db.flush()
        return True

    async def verify_recovery_code(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
        recovery_code: str,
    ) -> bool:
        """Verify and consume a recovery code (single-use).

        Removes the matched code hash from the stored list.

        Args:
            user_id: account_id (IAM v2)

        Returns:
            True if code valid and consumed

        Raises:
            ValueError: If MFA not enabled, no codes left, or code invalid
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)
        # SELECT FOR UPDATE pour single-use atomique (A2/P1-08)
        device = await self._get_enabled_device(db, membership_id, with_for_update=True)
        if not device:
            raise ValueError("MFA is not enabled for this user")

        if not device.recovery_codes_hash:
            raise ValueError("No recovery codes available")

        try:
            hashes = json.loads(device.recovery_codes_hash)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("MFA recovery codes corrompus device %s: %s", device.id, e)
            raise HTTPException(status_code=500, detail=ErrorMessages.INTERNAL_ERROR)
        if not hashes:
            raise ValueError("No recovery codes available")

        code_bytes = recovery_code.encode("utf-8")
        matched_index = None
        for i, stored_hash in enumerate(hashes):
            if bcrypt.checkpw(code_bytes, stored_hash.encode("utf-8")):
                matched_index = i
                break

        if matched_index is None:
            raise ValueError("Invalid recovery code")

        hashes.pop(matched_index)
        device.recovery_codes_hash = json.dumps(hashes)
        await db.flush()

        logger.info(
            "Recovery code used: account=%s tenant=%s remaining=%d",
            user_id, tenant_id, len(hashes),
        )
        return True

    async def disable_mfa(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> bool:
        """Disable MFA for a user (delete the device).

        Args:
            user_id: account_id (IAM v2)

        Returns:
            True if MFA was disabled

        Raises:
            ValueError: If MFA is not enabled
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)

        result = await db.execute(
            select(MFADevice).filter(
                MFADevice.membership_id == membership_id,
            )
        )
        device = result.scalars().first()

        if not device:
            raise ValueError("MFA is not enabled for this user")

        await db.delete(device)
        await db.flush()

        logger.info("MFA disabled: account=%s tenant=%s", user_id, tenant_id)
        return True

    async def is_mfa_enabled(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> bool:
        """Check if MFA is enabled for a user.

        Args:
            user_id: account_id (IAM v2)
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)
        device = await self._get_enabled_device(db, membership_id)
        return device is not None

    async def get_recovery_codes_count(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> int:
        """Get the number of remaining recovery codes.

        Args:
            user_id: account_id (IAM v2)
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)
        device = await self._get_enabled_device(db, membership_id)
        if not device or not device.recovery_codes_hash:
            return 0
        try:
            hashes = json.loads(device.recovery_codes_hash)
            return len(hashes)
        except (json.JSONDecodeError, TypeError):
            return 0

    async def regenerate_recovery_codes(
        self,
        db: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> list[str]:
        """Regenerate recovery codes for a user with MFA enabled.

        Replaces all existing codes with fresh ones.

        Args:
            user_id: account_id (IAM v2)

        Returns:
            List of new plaintext recovery codes

        Raises:
            ValueError: If MFA is not enabled
        """
        membership_id = await self._resolve_membership_id(db, user_id, tenant_id)
        device = await self._get_enabled_device(db, membership_id)
        if not device:
            raise ValueError("MFA is not enabled for this user")

        recovery_codes = [
            secrets.token_hex(MFAConfig.RECOVERY_CODE_LENGTH // 2)
            for _ in range(MFAConfig.RECOVERY_CODE_COUNT)
        ]

        recovery_hashes = []
        for code in recovery_codes:
            hashed = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10))
            recovery_hashes.append(hashed.decode("utf-8"))

        device.recovery_codes_hash = json.dumps(recovery_hashes)
        await db.flush()

        logger.info(
            "Recovery codes regenerated: account=%s tenant=%s count=%d",
            user_id, tenant_id, len(recovery_codes),
        )
        return recovery_codes

    # ========== MFA Session Tokens (Redis) ==========

    async def create_mfa_session(
        self,
        user_id: int,
        tenant_id: int,
        email: str,
        role: str,
        ip_address: str,
    ) -> str:
        """Create a temporary MFA session token in Redis (5 min TTL).

        Returns:
            MFA session token (opaque string)
        """
        token = secrets.token_urlsafe(32)
        key = f"{MFA_SESSION_PREFIX}{token}"
        data = json.dumps({
            "user_id": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "role": role,
            "ip_address": ip_address,
        })
        try:
            await redis_client.client.setex(key, MFAConfig.MFA_SESSION_TTL_SECONDS, data)
        except (redis_exc.ConnectionError, redis_exc.TimeoutError) as exc:
            logger.critical("Redis-SEC down — cannot create MFA session: %s", exc)
            raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE") from exc
        logger.info("MFA session created: user=%s", user_id)
        return token

    async def validate_mfa_session(self, token: str) -> Optional[dict]:
        """Validate and consume a MFA session token (single-use).

        Returns:
            Dict with user data or None if invalid/expired
        """
        key = f"{MFA_SESSION_PREFIX}{token}"
        # getdel() atomique — single-use garanti (A3/P1-09)
        raw = await redis_client.client.getdel(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    # ========== MFA Step-Up (spec §05.3) ==========

    async def verify_stepup(
        self,
        db: AsyncSession,
        user_id: int,
        device_id: str,
        totp_code: str,
    ) -> None:
        """Valide le code TOTP et écrit stepup:{uid}:{did} EX STEPUP_TTL dans Redis-SEC.

        Args:
            db: AsyncSession SQLAlchemy
            user_id: account_id (IAM v2)
            device_id: Claim 'did' extrait du JWT access token
            totp_code: Code TOTP 6 chiffres

        Raises:
            ValueError("MFA_NOT_CONFIGURED"): Si l'user n'a pas de device TOTP activé
            ValueError("TOTP_INVALID"): Si le code est incorrect ou rejoué
        """
        # JOIN membership pour résoudre account_id → device (sans tenant_id dans step-up)
        # SELECT FOR UPDATE pour anti-replay atomique (A1 étendu à step-up)
        result = await db.execute(
            select(MFADevice)
            .join(TenantMembership, MFADevice.membership_id == TenantMembership.id)
            .filter(
                TenantMembership.account_id == user_id,
                MFADevice.is_enabled == True,  # noqa: E712
            )
            .with_for_update()
        )
        device = result.scalars().first()

        if not device:
            raise ValueError("MFA_NOT_CONFIGURED")

        secret = decrypt_totp_secret(
            device.encrypted_secret,
            device.totp_secret_nonce,
            device.totp_encrypted_dek,
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)

        if not totp.verify(totp_code, valid_window=MFAConfig.TOTP_WINDOW):
            raise ValueError("TOTP_INVALID")

        current_window = int(time.time()) // MFAConfig.TOTP_PERIOD
        if device.last_totp_window is not None and current_window <= device.last_totp_window:
            raise ValueError("TOTP_INVALID")

        device.last_totp_window = current_window
        await db.flush()

        key = RedisKeys.stepup(user_id, device_id)
        try:
            await redis_client.client.setex(key, MFAConfig.STEPUP_TTL, "1")
        except (redis_exc.ConnectionError, redis_exc.TimeoutError) as exc:
            logger.critical("Redis-SEC down — cannot write step-up token: %s", exc)
            raise HTTPException(status_code=503, detail="SERVICE_UNAVAILABLE") from exc

        logger.info("Step-up MFA verified: account=%s device=%s", user_id, device_id)

    async def is_stepup_valid(self, user_id: int, device_id: str) -> bool:
        """Vérifie EXISTS stepup:{uid}:{did} dans Redis-SEC.

        Returns:
            True si la clé step-up est présente (step-up actif), False sinon
        """
        key = RedisKeys.stepup(user_id, device_id)
        return bool(await redis_client.client.exists(key))

    # ========== Private ==========

    async def _resolve_membership_id(
        self,
        db: AsyncSession,
        account_id: int,
        tenant_id: int,
    ) -> int:
        """Résout le membership_id depuis (account_id, tenant_id).

        Raises:
            ValueError: Si aucun membership actif trouvé.
        """
        repo = AsyncTenantMembershipRepository(db)
        membership = await repo.get_active(account_id, tenant_id)
        if not membership:
            raise ValueError("No active membership for this user in this tenant")
        return membership.id

    @staticmethod
    async def _get_enabled_device(
        db: AsyncSession,
        membership_id: int,
        with_for_update: bool = False,
    ) -> Optional[MFADevice]:
        """Get the enabled MFA device for a membership.

        Args:
            membership_id: ID du TenantMembership (IAM v2)
            with_for_update: Si True, ajoute SELECT FOR UPDATE pour atomicité (A1/A2).
        """
        query = select(MFADevice).filter(
            MFADevice.membership_id == membership_id,
            MFADevice.is_enabled == True,  # noqa: E712
        )
        if with_for_update:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalars().first()


# Singleton
mfa_service = MFAService()
