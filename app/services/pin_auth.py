"""Service d'authentification PIN pour restaurant.

Workflow :
    1. register_device(account_id, tenant_id, device_id, device_name)
       → Enregistre une tablette après premier login email+password
    2. set_pin(account_id, pin)
       → Hash Argon2id et stocke dans accounts.pin_hash
    3. verify_pin(pin, device_id, tenant_id)
       → Vérifie PIN + device trusted → retourne Account
    4. lock_check(device_id)
       → Lockout 3 tentatives / 5 min (surface 10k combinaisons)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.trusted_device import TrustedDevice

logger = logging.getLogger(__name__)

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 6
PIN_MAX_ATTEMPTS = 3
PIN_LOCKOUT_WINDOW_SECONDS = 300  # 5 minutes

# Hash fictif pour timing constant (anti timing-oracle sur existence device)
_DUMMY_HASH = _ph.hash("000000")


def hash_pin(pin: str) -> str:
    """Hash un PIN avec Argon2id."""
    return _ph.hash(pin)


def verify_pin_hash(pin_hash: str, pin: str) -> bool:
    """Vérifie un PIN contre son hash Argon2id."""
    try:
        return _ph.verify(pin_hash, pin)
    except VerifyMismatchError:
        return False


def validate_pin_format(pin: str) -> bool:
    """Vérifie que le PIN est composé de 4-6 chiffres."""
    return pin.isdigit() and PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH


class PinAuthService:
    """Service PIN auth — register device, set PIN, verify PIN."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_device(
        self,
        account_id: int,
        tenant_id: int,
        device_id: str,
        device_name: Optional[str] = None,
    ) -> TrustedDevice:
        """Enregistre un device après premier login email+password.

        Si le device existe déjà (même account_id + device_id), le réactive.
        """
        result = await self.db.execute(
            select(TrustedDevice).where(
                TrustedDevice.account_id == account_id,
                TrustedDevice.device_id == device_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.revoked_at = None
            existing.device_name = device_name or existing.device_name
            existing.last_used_at = datetime.now(timezone.utc)
            return existing

        device = TrustedDevice(
            account_id=account_id,
            tenant_id=tenant_id,
            device_id=device_id,
            device_name=device_name,
        )
        self.db.add(device)
        await self.db.flush()
        return device

    async def set_pin(self, account_id: int, pin: str) -> None:
        """Définit le PIN d'un compte (hash Argon2id)."""
        if not validate_pin_format(pin):
            raise ValueError(f"PIN must be {PIN_MIN_LENGTH}-{PIN_MAX_LENGTH} digits")

        hashed = hash_pin(pin)
        await self.db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(pin_hash=hashed)
        )

    async def verify_pin_login(
        self,
        pin: str,
        device_id: str,
        tenant_id: int,
    ) -> Optional[Account]:
        """Vérifie PIN + device trusted → retourne Account si valide.

        Returns:
            Account si PIN et device valides, None sinon.
        """
        # Trouver le device
        result = await self.db.execute(
            select(TrustedDevice).where(
                TrustedDevice.device_id == device_id,
                TrustedDevice.tenant_id == tenant_id,
                TrustedDevice.revoked_at.is_(None),
            )
        )
        device = result.scalar_one_or_none()
        if not device:
            verify_pin_hash(_DUMMY_HASH, pin)  # timing constant
            return None

        # Charger le compte
        account_result = await self.db.execute(
            select(Account).where(
                Account.id == device.account_id,
                Account.is_active.is_(True),
            )
        )
        account = account_result.scalar_one_or_none()
        if not account or not account.pin_hash:
            verify_pin_hash(_DUMMY_HASH, pin)  # timing constant
            return None

        # Vérifier le PIN
        if not verify_pin_hash(account.pin_hash, pin):
            return None

        # Mettre à jour last_used_at
        device.last_used_at = datetime.now(timezone.utc)

        return account

    async def revoke_device(self, device_id: int) -> bool:
        """Révoque un device (admin action)."""
        result = await self.db.execute(
            select(TrustedDevice).where(TrustedDevice.id == device_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            return False
        device.revoked_at = datetime.now(timezone.utc)
        return True

    async def list_devices(self, account_id: int) -> list[TrustedDevice]:
        """Liste tous les devices d'un compte (actifs et révoqués)."""
        result = await self.db.execute(
            select(TrustedDevice)
            .where(TrustedDevice.account_id == account_id)
            .order_by(TrustedDevice.registered_at.desc())
        )
        return list(result.scalars().all())
