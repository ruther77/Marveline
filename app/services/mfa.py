"""Service MFA TOTP — setup, verify, recovery codes.

Responsabilities:
    - Generate TOTP secret + provisioning URI (QR code)
    - Verify TOTP codes with anti-replay
    - Generate and verify bcrypt-hashed recovery codes
    - Enable/disable MFA for a user

Architecture:
    - TOTP secret encrypted with AES-256-GCM in DB (app.core.crypto)
    - Recovery codes hashed with bcrypt (single-use)
    - Anti-replay via last_totp_window in DB
    - MFA session tokens stored in Redis (5 min TTL)

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
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_totp_secret, encrypt_totp_secret
from app.core.redis import redis_client
from app.constants import MFAConfig, RedisKeys
from app.models.mfa import MFADevice

logger = logging.getLogger(__name__)

# Redis key prefix for MFA session tokens
MFA_SESSION_PREFIX = "mfa_session:"


class MFAService:
    """Service de gestion MFA TOTP.

    Instance-level state only (no class variables) to avoid cross-user leaks.
    Each method takes db session and user_id as explicit parameters.
    """

    def setup_totp(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
        email: str,
    ) -> tuple[str, str, list[str]]:
        """Generate a new TOTP secret and provisioning URI.

        If the user already has a pending (not enabled) MFA device, replace it.
        If MFA is already enabled, raise ValueError.

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID
            email: User email (for provisioning URI label)

        Returns:
            Tuple of (secret_plaintext, provisioning_uri, recovery_codes)
            - secret_plaintext: Base32-encoded secret (for QR display)
            - provisioning_uri: otpauth:// URI for authenticator apps
            - recovery_codes: List of 8 plaintext recovery codes

        Raises:
            ValueError: If MFA is already enabled for this user
        """
        # Check for existing enabled device
        existing = (
            db.query(MFADevice)
            .filter(MFADevice.user_id == user_id, MFADevice.tenant_id == tenant_id)
            .first()
        )

        if existing and existing.is_enabled:
            raise ValueError("MFA is already enabled for this user")

        # Remove pending (not enabled) device if exists
        if existing and not existing.is_enabled:
            db.delete(existing)
            db.flush()

        # Generate TOTP secret
        secret = pyotp.random_base32()

        # Generate recovery codes
        recovery_codes = [
            secrets.token_hex(MFAConfig.RECOVERY_CODE_LENGTH // 2)
            for _ in range(MFAConfig.RECOVERY_CODE_COUNT)
        ]

        # Hash recovery codes with bcrypt
        recovery_hashes = []
        for code in recovery_codes:
            hashed = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10))
            recovery_hashes.append(hashed.decode("utf-8"))

        # Encrypt TOTP secret
        encrypted = encrypt_totp_secret(secret)

        # Create MFA device (not yet enabled — needs verify-setup)
        device = MFADevice(
            user_id=user_id,
            tenant_id=tenant_id,
            encrypted_secret=encrypted,
            is_enabled=False,
            recovery_codes_hash=json.dumps(recovery_hashes),
            last_totp_window=None,
        )
        db.add(device)
        db.flush()

        # Build provisioning URI
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        provisioning_uri = totp.provisioning_uri(name=email, issuer_name=MFAConfig.ISSUER_NAME)

        logger.info("MFA setup initiated: user=%s tenant=%s", user_id, tenant_id)

        return secret, provisioning_uri, recovery_codes

    def verify_setup(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
        totp_code: str,
    ) -> bool:
        """Verify the initial TOTP code to complete MFA setup.

        This enables the MFA device after the user proves they have
        the correct authenticator app configured.

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID
            totp_code: 6-digit TOTP code from authenticator app

        Returns:
            True if code valid and MFA enabled

        Raises:
            ValueError: If no pending MFA device found or code invalid
        """
        device = (
            db.query(MFADevice)
            .filter(
                MFADevice.user_id == user_id,
                MFADevice.tenant_id == tenant_id,
                MFADevice.is_enabled == False,  # noqa: E712
            )
            .first()
        )

        if not device:
            raise ValueError("No pending MFA setup found")

        # Decrypt secret and verify
        secret = decrypt_totp_secret(device.encrypted_secret)
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)

        if not totp.verify(totp_code, valid_window=MFAConfig.TOTP_WINDOW):
            raise ValueError("Invalid TOTP code")

        # Enable MFA device
        current_window = int(time.time()) // MFAConfig.TOTP_PERIOD
        device.is_enabled = True
        device.last_totp_window = current_window
        db.flush()

        logger.info("MFA enabled: user=%s tenant=%s", user_id, tenant_id)
        return True

    def verify_totp(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
        totp_code: str,
    ) -> bool:
        """Verify a TOTP code for login (MFA step 2).

        Includes anti-replay: rejects codes from the same time window
        as the last accepted code.

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID
            totp_code: 6-digit TOTP code

        Returns:
            True if code valid

        Raises:
            ValueError: If MFA not enabled, or code invalid/replayed
        """
        device = self._get_enabled_device(db, user_id, tenant_id)
        if not device:
            raise ValueError("MFA is not enabled for this user")

        secret = decrypt_totp_secret(device.encrypted_secret)
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)

        if not totp.verify(totp_code, valid_window=MFAConfig.TOTP_WINDOW):
            raise ValueError("Invalid TOTP code")

        # Anti-replay: check time window
        current_window = int(time.time()) // MFAConfig.TOTP_PERIOD
        if device.last_totp_window is not None and current_window <= device.last_totp_window:
            raise ValueError("TOTP code already used (anti-replay)")

        # Update last accepted window
        device.last_totp_window = current_window
        db.flush()

        return True

    def verify_recovery_code(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
        recovery_code: str,
    ) -> bool:
        """Verify and consume a recovery code (single-use).

        Removes the matched code hash from the stored list.

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID
            recovery_code: Recovery code string

        Returns:
            True if code valid and consumed

        Raises:
            ValueError: If MFA not enabled, no codes left, or code invalid
        """
        device = self._get_enabled_device(db, user_id, tenant_id)
        if not device:
            raise ValueError("MFA is not enabled for this user")

        if not device.recovery_codes_hash:
            raise ValueError("No recovery codes available")

        hashes = json.loads(device.recovery_codes_hash)
        if not hashes:
            raise ValueError("No recovery codes available")

        # Check each hash
        code_bytes = recovery_code.encode("utf-8")
        matched_index = None
        for i, stored_hash in enumerate(hashes):
            if bcrypt.checkpw(code_bytes, stored_hash.encode("utf-8")):
                matched_index = i
                break

        if matched_index is None:
            raise ValueError("Invalid recovery code")

        # Remove used code (single-use)
        hashes.pop(matched_index)
        device.recovery_codes_hash = json.dumps(hashes)
        db.flush()

        logger.info(
            "Recovery code used: user=%s tenant=%s remaining=%d",
            user_id, tenant_id, len(hashes),
        )

        return True

    def disable_mfa(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
    ) -> bool:
        """Disable MFA for a user (delete the device).

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            True if MFA was disabled

        Raises:
            ValueError: If MFA is not enabled
        """
        device = (
            db.query(MFADevice)
            .filter(MFADevice.user_id == user_id, MFADevice.tenant_id == tenant_id)
            .first()
        )

        if not device:
            raise ValueError("MFA is not enabled for this user")

        db.delete(device)
        db.flush()

        logger.info("MFA disabled: user=%s tenant=%s", user_id, tenant_id)
        return True

    def is_mfa_enabled(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
    ) -> bool:
        """Check if MFA is enabled for a user.

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            True if user has an enabled MFA device
        """
        device = self._get_enabled_device(db, user_id, tenant_id)
        return device is not None

    def get_recovery_codes_count(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
    ) -> int:
        """Get the number of remaining recovery codes.

        Returns:
            Number of remaining codes (0 if MFA not enabled or no codes)
        """
        device = self._get_enabled_device(db, user_id, tenant_id)
        if not device or not device.recovery_codes_hash:
            return 0
        try:
            hashes = json.loads(device.recovery_codes_hash)
            return len(hashes)
        except (json.JSONDecodeError, TypeError):
            return 0

    def regenerate_recovery_codes(
        self,
        db: Session,
        user_id: int,
        tenant_id: int,
    ) -> list[str]:
        """Regenerate recovery codes for a user with MFA enabled.

        Replaces all existing codes with fresh ones.

        Args:
            db: SQLAlchemy session
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            List of new plaintext recovery codes

        Raises:
            ValueError: If MFA is not enabled
        """
        device = self._get_enabled_device(db, user_id, tenant_id)
        if not device:
            raise ValueError("MFA is not enabled for this user")

        # Generate new recovery codes
        recovery_codes = [
            secrets.token_hex(MFAConfig.RECOVERY_CODE_LENGTH // 2)
            for _ in range(MFAConfig.RECOVERY_CODE_COUNT)
        ]

        # Hash with bcrypt
        recovery_hashes = []
        for code in recovery_codes:
            hashed = bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt(rounds=10))
            recovery_hashes.append(hashed.decode("utf-8"))

        device.recovery_codes_hash = json.dumps(recovery_hashes)
        db.flush()

        logger.info(
            "Recovery codes regenerated: user=%s tenant=%s count=%d",
            user_id, tenant_id, len(recovery_codes),
        )

        return recovery_codes

    # ========== MFA Session Tokens (Redis) ==========

    def create_mfa_session(
        self,
        user_id: int,
        tenant_id: int,
        email: str,
        role: str,
        ip_address: str,
    ) -> str:
        """Create a temporary MFA session token in Redis.

        This token is issued after successful password verification
        when MFA is enabled. It must be exchanged for real tokens
        via /mfa/verify within MFA_SESSION_TTL_SECONDS.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            email: User email
            role: User role
            ip_address: Client IP

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
        redis_client.client.setex(key, MFAConfig.MFA_SESSION_TTL_SECONDS, data)

        logger.info("MFA session created: user=%s", user_id)
        return token

    def validate_mfa_session(self, token: str) -> Optional[dict]:
        """Validate and consume a MFA session token.

        The token is deleted after validation (single-use).

        Args:
            token: MFA session token

        Returns:
            Dict with user data or None if invalid/expired
        """
        key = f"{MFA_SESSION_PREFIX}{token}"
        data = redis_client.client.get(key)
        if not data:
            return None

        # Single-use: delete after reading
        redis_client.client.delete(key)

        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None

    # ========== Private ==========

    @staticmethod
    def _get_enabled_device(
        db: Session,
        user_id: int,
        tenant_id: int,
    ) -> Optional[MFADevice]:
        """Get the enabled MFA device for a user."""
        return (
            db.query(MFADevice)
            .filter(
                MFADevice.user_id == user_id,
                MFADevice.tenant_id == tenant_id,
                MFADevice.is_enabled == True,  # noqa: E712
            )
            .first()
        )


# Singleton
mfa_service = MFAService()
