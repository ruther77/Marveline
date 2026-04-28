"""Service de protection brute force : escalation multi-niveaux Redis.

Responsabilités:
    - Compteurs de tentatives par email ET par IP dans Redis
    - Escalation progressive : normal → captcha → delay → lock → lock+alert
    - Reset des compteurs après login réussi
    - Idempotence des alertes admin (une seule alerte par fenêtre)

Architecture:
    - Compteurs per-email: bf_email:{email} (TTL 15 min glissant)
    - Compteurs per-IP: bf_ip:{ip} (TTL 15 min glissant)
    - Lock: bf_lock:{email} (TTL 15 min)
    - Alert sent: bf_alert:{email} (TTL 15 min, SET NX = une seule fois)

Toutes les méthodes sont async (redis.asyncio, PHASE 2).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.redis import redis_client
from app.constants import BruteForceThresholds, CredentialStuffingThresholds, RedisKeys

logger = logging.getLogger(__name__)


@dataclass
class BruteForceStatus:
    """Résultat de la vérification brute force."""

    allowed: bool = True
    captcha_required: bool = False
    delay_seconds: int = 0
    locked: bool = False
    locked_until_seconds: int = 0
    attempts: int = 0


class BruteForceService:
    """Service de protection brute force avec escalation Redis."""

    async def check_and_enforce(
        self, email: str, ip_address: str, device_id: Optional[str] = None
    ) -> BruteForceStatus:
        """Vérifie l'état brute force AVANT une tentative de login.

        Politique sans lockout dur : escalation CAPTCHA + délai, jamais de blocage.
        """
        attempts = await self._get_max_attempts(email, ip_address, device_id)

        if attempts >= BruteForceThresholds.DELAY_THRESHOLD:
            delay = BruteForceThresholds.BASE_DELAY_SECONDS * (
                2 ** (attempts - BruteForceThresholds.DELAY_THRESHOLD)
            )
            return BruteForceStatus(
                allowed=True,
                captcha_required=True,
                delay_seconds=min(delay, BruteForceThresholds.MAX_DELAY_SECONDS),
                attempts=attempts,
            )

        if attempts >= BruteForceThresholds.CAPTCHA_THRESHOLD:
            return BruteForceStatus(allowed=True, captcha_required=True, attempts=attempts)

        return BruteForceStatus(allowed=True, attempts=attempts)

    async def record_failed_attempt(
        self, email: str, ip_address: str, device_id: Optional[str] = None
    ) -> BruteForceStatus:
        """Enregistre une tentative échouée et retourne le nouveau statut."""
        window = BruteForceThresholds.ATTEMPT_WINDOW_SECONDS

        email_count = await redis_client.increment_brute_force(
            f"{RedisKeys.BRUTE_FORCE_USER}{email}", window
        )
        ip_count = await redis_client.increment_brute_force(
            f"{RedisKeys.BRUTE_FORCE_IP}{ip_address}", window
        )
        device_count = (
            await redis_client.increment_brute_force(
                f"{RedisKeys.BRUTE_FORCE_DEVICE}{device_id}", window
            )
            if device_id
            else 0
        )

        attempts = max(email_count, ip_count, device_count)

        if attempts >= BruteForceThresholds.DELAY_THRESHOLD:
            delay = BruteForceThresholds.BASE_DELAY_SECONDS * (
                2 ** (attempts - BruteForceThresholds.DELAY_THRESHOLD)
            )
            return BruteForceStatus(
                allowed=True,
                captcha_required=True,
                delay_seconds=min(delay, BruteForceThresholds.MAX_DELAY_SECONDS),
                attempts=attempts,
            )

        if attempts >= BruteForceThresholds.CAPTCHA_THRESHOLD:
            return BruteForceStatus(allowed=True, captcha_required=True, attempts=attempts)

        return BruteForceStatus(allowed=True, attempts=attempts)

    async def record_successful_login(
        self, email: str, ip_address: str, device_id: Optional[str] = None
    ) -> None:
        """Reset les compteurs après un login réussi."""
        await redis_client.reset_brute_force(f"{RedisKeys.BRUTE_FORCE_USER}{email}")
        await redis_client.reset_brute_force(f"{RedisKeys.BRUTE_FORCE_IP}{ip_address}")
        if device_id:
            await redis_client.reset_brute_force(f"{RedisKeys.BRUTE_FORCE_DEVICE}{device_id}")

    async def record_global_failure(self) -> None:
        """Incrémente le compteur global de credential stuffing de la minute courante."""
        minute_key = (
            f"{RedisKeys.CREDENTIAL_STUFFING}"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        )
        count = await redis_client.increment_credential_stuffing(minute_key)

        if count > CredentialStuffingThresholds.BLOCK_THRESHOLD:
            await redis_client.set_login_blocked(CredentialStuffingThresholds.BLOCK_TTL_SECONDS)
            logger.critical(
                "CREDENTIAL STUFFING BLOCK: %d failures/min — login globalement bloqué (PAGERDUTY)",
                count,
            )
        elif count > CredentialStuffingThresholds.CAPTCHA_THRESHOLD:
            await redis_client.set_captcha_required(CredentialStuffingThresholds.CAPTCHA_TTL_SECONDS)
            logger.critical(
                "CREDENTIAL STUFFING CAPTCHA: %d failures/min — captcha:required activé",
                count,
            )
        elif count > CredentialStuffingThresholds.WARNING_THRESHOLD:
            logger.warning("Credential stuffing détecté : %d failures/min", count)

    async def validate_captcha_token(self, captcha_token: Optional[str]) -> bool:
        """Valide un token hCaptcha côté serveur (FAIL-CLOSED, appel async).

        Async pour ne pas bloquer l'event loop FastAPI (fix BUG-CAPTCHA-SYNC-01).
        """
        from app.core.config import settings  # noqa: PLC0415

        # Skip validation entirely when CAPTCHA is disabled (dev/test)
        if not settings.HCAPTCHA_ENABLED:
            logger.debug("HCAPTCHA_ENABLED=False — captcha accepté sans vérification API")
            return True

        if not captcha_token:
            return False

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    settings.HCAPTCHA_VERIFY_URL,
                    data={"secret": settings.HCAPTCHA_SECRET_KEY, "response": captcha_token},
                    timeout=3.0,
                )
            resp.raise_for_status()
            return bool(resp.json().get("success", False))
        except Exception:
            logger.warning("hCaptcha API indisponible — CAPTCHA rejeté (FAIL-CLOSED)")
            return False

    async def _get_max_attempts(
        self, email: str, ip_address: str, device_id: Optional[str] = None
    ) -> int:
        """Retourne le max entre compteurs email, IP et device."""
        email_count = await redis_client.get_brute_force_count(
            f"{RedisKeys.BRUTE_FORCE_USER}{email}"
        )
        ip_count = await redis_client.get_brute_force_count(
            f"{RedisKeys.BRUTE_FORCE_IP}{ip_address}"
        )
        device_count = (
            await redis_client.get_brute_force_count(
                f"{RedisKeys.BRUTE_FORCE_DEVICE}{device_id}"
            )
            if device_id
            else 0
        )
        return max(email_count, ip_count, device_count)


# Singleton
brute_force_service = BruteForceService()
