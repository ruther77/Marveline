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
    - Pas de class variables partagées (fix bug ancien CaroCorp)
"""
import logging
from dataclasses import dataclass

from app.core.redis import redis_client
from app.constants import BruteForceThresholds, RedisKeys

logger = logging.getLogger(__name__)


@dataclass
class BruteForceStatus:
    """Résultat de la vérification brute force.

    Attributes:
        allowed: True si la tentative est autorisée
        captcha_required: True si un CAPTCHA doit être présenté
        delay_seconds: Délai à appliquer avant de répondre (0 = aucun)
        locked: True si le compte est verrouillé
        locked_until_seconds: Secondes restantes avant déverrouillage (0 si pas lock)
        attempts: Nombre de tentatives (max entre email et IP)
    """

    allowed: bool = True
    captcha_required: bool = False
    delay_seconds: int = 0
    locked: bool = False
    locked_until_seconds: int = 0
    attempts: int = 0


class BruteForceService:
    """Service de protection brute force avec escalation Redis.

    Niveaux d'escalation (basés sur max(email_count, ip_count)):
        0-2  : Normal (aucune restriction)
        3-4  : CAPTCHA requis
        5-7  : Délai progressif (1s, 2s, 4s)
        8-9  : Lock temporaire (15 min)
        10+  : Lock + alerte admin (idempotente)

    Instance variables uniquement — pas de class variables
    (fix du bug P0 _memory_attempts de l'ancien CaroCorp).
    """

    def check_and_enforce(self, email: str, ip_address: str) -> BruteForceStatus:
        """Vérifie l'état brute force AVANT une tentative de login.

        Args:
            email: Email normalisé (lowercase, stripped)
            ip_address: Adresse IP du client

        Returns:
            BruteForceStatus avec les restrictions à appliquer
        """
        # Vérifier si le compte est verrouillé
        if redis_client.is_brute_force_locked(email):
            lock_ttl = redis_client.get_brute_force_lock_ttl(email)
            return BruteForceStatus(
                allowed=False,
                locked=True,
                locked_until_seconds=lock_ttl,
                attempts=self._get_max_attempts(email, ip_address),
            )

        # Compter tentatives
        attempts = self._get_max_attempts(email, ip_address)

        # Escalation
        if attempts >= BruteForceThresholds.LOCK_THRESHOLD:
            # Déjà au seuil de lock mais pas encore verrouillé
            # (peut arriver si le lock a expiré mais le compteur non)
            return BruteForceStatus(
                allowed=False,
                locked=True,
                locked_until_seconds=BruteForceThresholds.LOCK_DURATION_SECONDS,
                attempts=attempts,
            )

        if attempts >= BruteForceThresholds.DELAY_THRESHOLD:
            # Délai progressif: 2^(attempts - DELAY_THRESHOLD) secondes
            delay = BruteForceThresholds.BASE_DELAY_SECONDS * (
                2 ** (attempts - BruteForceThresholds.DELAY_THRESHOLD)
            )
            return BruteForceStatus(
                allowed=True,
                captcha_required=True,
                delay_seconds=min(delay, 30),  # Cap à 30s
                attempts=attempts,
            )

        if attempts >= BruteForceThresholds.CAPTCHA_THRESHOLD:
            return BruteForceStatus(
                allowed=True,
                captcha_required=True,
                attempts=attempts,
            )

        # Normal
        return BruteForceStatus(allowed=True, attempts=attempts)

    def record_failed_attempt(self, email: str, ip_address: str) -> BruteForceStatus:
        """Enregistre une tentative échouée et retourne le nouveau statut.

        Args:
            email: Email normalisé
            ip_address: Adresse IP du client

        Returns:
            BruteForceStatus après incrémentation
        """
        window = BruteForceThresholds.ATTEMPT_WINDOW_SECONDS

        # Incrémenter compteurs email ET IP
        email_count = redis_client.increment_brute_force(
            RedisKeys.BRUTE_FORCE_EMAIL, email, window
        )
        ip_count = redis_client.increment_brute_force(
            RedisKeys.BRUTE_FORCE_IP, ip_address, window
        )

        attempts = max(email_count, ip_count)

        # Escalation post-tentative
        if attempts >= BruteForceThresholds.LOCK_THRESHOLD:
            # Verrouiller le compte
            redis_client.set_brute_force_lock(
                email, BruteForceThresholds.LOCK_DURATION_SECONDS
            )
            logger.warning(
                "Brute force lock: email=%s ip=%s attempts=%d",
                email, ip_address, attempts,
            )

            # Alerte admin au seuil exact (idempotente via SET NX)
            if attempts >= BruteForceThresholds.ALERT_THRESHOLD:
                alert_sent = redis_client.set_brute_force_alert_sent(
                    email, BruteForceThresholds.ATTEMPT_WINDOW_SECONDS
                )
                if alert_sent:
                    logger.critical(
                        "BRUTE FORCE ALERT: email=%s ip=%s attempts=%d — admin notification",
                        email, ip_address, attempts,
                    )

            lock_ttl = redis_client.get_brute_force_lock_ttl(email)
            return BruteForceStatus(
                allowed=False,
                locked=True,
                locked_until_seconds=lock_ttl,
                attempts=attempts,
            )

        if attempts >= BruteForceThresholds.DELAY_THRESHOLD:
            delay = BruteForceThresholds.BASE_DELAY_SECONDS * (
                2 ** (attempts - BruteForceThresholds.DELAY_THRESHOLD)
            )
            return BruteForceStatus(
                allowed=True,
                captcha_required=True,
                delay_seconds=min(delay, 30),
                attempts=attempts,
            )

        if attempts >= BruteForceThresholds.CAPTCHA_THRESHOLD:
            return BruteForceStatus(
                allowed=True,
                captcha_required=True,
                attempts=attempts,
            )

        return BruteForceStatus(allowed=True, attempts=attempts)

    def record_successful_login(self, email: str, ip_address: str) -> None:
        """Reset les compteurs après un login réussi.

        Args:
            email: Email normalisé
            ip_address: Adresse IP du client
        """
        redis_client.reset_brute_force(RedisKeys.BRUTE_FORCE_EMAIL, email)
        redis_client.reset_brute_force(RedisKeys.BRUTE_FORCE_IP, ip_address)

    def _get_max_attempts(self, email: str, ip_address: str) -> int:
        """Retourne le max entre compteur email et compteur IP."""
        email_count = redis_client.get_brute_force_count(
            RedisKeys.BRUTE_FORCE_EMAIL, email
        )
        ip_count = redis_client.get_brute_force_count(
            RedisKeys.BRUTE_FORCE_IP, ip_address
        )
        return max(email_count, ip_count)


# Singleton
brute_force_service = BruteForceService()
