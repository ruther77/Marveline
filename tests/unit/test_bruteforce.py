"""Tests unitaires pour le service BruteForce — escalation multi-niveaux Redis.

Couvre :
    - 3 niveaux d'escalation (normal, captcha, delay)
    - Compteurs per-email ET per-IP
    - Reset des compteurs après login réussi
    - BruteForceStatus dataclass

Fichier service testé : app/services/bruteforce.py
Fichier constants : app/constants/security.py (BruteForceThresholds)
Fichier Redis : app/core/redis.py (méthodes brute force)
"""
import pytest
from unittest.mock import patch, AsyncMock

from app.services.bruteforce import BruteForceService, BruteForceStatus
from app.constants import BruteForceThresholds, RedisKeys


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def bf_service():
    """Instance fraîche du service (pas le singleton)."""
    return BruteForceService()


@pytest.fixture
def mock_redis():
    """Mock async du redis_client pour tests unitaires purs (pas de Redis réel)."""
    with patch("app.services.bruteforce.redis_client") as mock:
        mock.get_brute_force_count = AsyncMock(return_value=0)
        mock.increment_brute_force = AsyncMock(return_value=1)
        mock.reset_brute_force = AsyncMock(return_value=True)
        yield mock


# ─────────────────────────────────────────────────────────────────────
# BruteForceStatus dataclass
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceStatus:
    """Tests pour le dataclass BruteForceStatus."""

    def test_default_values(self):
        """Valeurs par défaut = tout permis."""
        status = BruteForceStatus()
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.delay_seconds == 0
        assert status.locked is False
        assert status.locked_until_seconds == 0
        assert status.attempts == 0

    def test_captcha_and_delay_status(self):
        """Statut captcha + délai — cas typique niveau 3 (allowed=True)."""
        status = BruteForceStatus(
            allowed=True, captcha_required=True,
            delay_seconds=8, attempts=8,
        )
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 8
        assert status.locked is False

    def test_captcha_status(self):
        """Statut captcha requis."""
        status = BruteForceStatus(
            allowed=True, captcha_required=True, attempts=3,
        )
        assert status.allowed is True
        assert status.captcha_required is True

    def test_delay_status(self):
        """Statut avec délai progressif."""
        status = BruteForceStatus(
            allowed=True, captcha_required=True,
            delay_seconds=4, attempts=7,
        )
        assert status.delay_seconds == 4


# ─────────────────────────────────────────────────────────────────────
# check_and_enforce — escalation levels
# ─────────────────────────────────────────────────────────────────────

class TestCheckAndEnforce:
    """Tests pour check_and_enforce() — vérification AVANT tentative."""

    async def test_normal_0_attempts(self, bf_service, mock_redis):
        """0 tentatives → normal, tout permis."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=0)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.delay_seconds == 0
        assert status.locked is False
        assert status.attempts == 0

    async def test_normal_2_attempts(self, bf_service, mock_redis):
        """2 tentatives → encore normal."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=2)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.attempts == 2

    async def test_captcha_at_3_attempts(self, bf_service, mock_redis):
        """3 tentatives → CAPTCHA requis (seuil CAPTCHA_THRESHOLD=3)."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=3)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 0
        assert status.attempts == 3

    async def test_captcha_at_4_attempts(self, bf_service, mock_redis):
        """4 tentatives → CAPTCHA toujours requis."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=4)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 0

    async def test_delay_at_5_attempts(self, bf_service, mock_redis):
        """5 tentatives → délai 1s + captcha (seuil DELAY_THRESHOLD=5)."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=5)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 1  # BASE_DELAY * 2^(5-5) = 1*1 = 1

    async def test_delay_at_6_attempts(self, bf_service, mock_redis):
        """6 tentatives → délai 2s."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=6)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.delay_seconds == 2  # 1 * 2^(6-5) = 2

    async def test_delay_at_7_attempts(self, bf_service, mock_redis):
        """7 tentatives → délai 4s."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=7)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.delay_seconds == 4  # 1 * 2^(7-5) = 4

    async def test_delay_capped_at_max(self, bf_service, mock_redis):
        """Délai plafonné à MAX_DELAY_SECONDS même avec beaucoup de tentatives."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=20)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.delay_seconds <= BruteForceThresholds.MAX_DELAY_SECONDS
        assert status.allowed is True

    async def test_high_attempts_still_allowed(self, bf_service, mock_redis):
        """8 tentatives → toujours allowed (pas de lockout dur)."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=8)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == BruteForceThresholds.BASE_DELAY_SECONDS * (
            2 ** (8 - BruteForceThresholds.DELAY_THRESHOLD)
        )

    async def test_uses_max_of_email_and_ip_counts(self, bf_service, mock_redis):
        """Utilise le max entre compteur email et compteur IP."""

        async def email_vs_ip(key):
            if key.startswith(RedisKeys.BRUTE_FORCE_IP):
                return 4  # IP
            return 2  # email

        mock_redis.get_brute_force_count.side_effect = email_vs_ip
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.captcha_required is True
        assert status.attempts == 4


# ─────────────────────────────────────────────────────────────────────
# record_failed_attempt — escalation post-tentative
# ─────────────────────────────────────────────────────────────────────

class TestRecordFailedAttempt:
    """Tests pour record_failed_attempt() — enregistrement APRÈS échec."""

    async def test_first_attempt_normal(self, bf_service, mock_redis):
        """Première tentative échouée → normal."""
        mock_redis.increment_brute_force = AsyncMock(return_value=1)
        status = await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.attempts == 1

    async def test_increments_both_email_and_ip(self, bf_service, mock_redis):
        """Incrémente les compteurs email ET IP."""
        mock_redis.increment_brute_force = AsyncMock(return_value=1)
        await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        calls = mock_redis.increment_brute_force.call_args_list
        assert len(calls) == 2
        # Premier appel = email
        assert calls[0][0][0] == f"{RedisKeys.BRUTE_FORCE_USER}test@example.com"
        # Deuxième appel = IP
        assert calls[1][0][0] == f"{RedisKeys.BRUTE_FORCE_IP}1.2.3.4"

    async def test_captcha_after_3_failures(self, bf_service, mock_redis):
        """3 échecs → captcha requis."""
        mock_redis.increment_brute_force = AsyncMock(return_value=3)
        status = await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.captcha_required is True
        assert status.allowed is True

    async def test_delay_after_5_failures(self, bf_service, mock_redis):
        """5 échecs → délai + captcha."""
        mock_redis.increment_brute_force = AsyncMock(return_value=5)
        status = await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.captcha_required is True
        assert status.delay_seconds == 1

    async def test_no_lock_after_8_failures(self, bf_service, mock_redis):
        """8 échecs → toujours allowed, délai exponentiel (pas de lockout dur)."""
        mock_redis.increment_brute_force = AsyncMock(return_value=8)
        status = await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds > 0
        assert status.locked is False

    async def test_uses_max_of_email_ip_for_escalation(self, bf_service, mock_redis):
        """Escalation basée sur max(email_count, ip_count)."""

        async def side_effect(key, ttl):
            if key.startswith(RedisKeys.BRUTE_FORCE_IP):
                return 5  # IP
            return 2  # email

        mock_redis.increment_brute_force.side_effect = side_effect
        status = await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.delay_seconds >= 1
        assert status.captcha_required is True

    async def test_ttl_passed_to_increment(self, bf_service, mock_redis):
        """Le TTL de la fenêtre est passé correctement à Redis."""
        mock_redis.increment_brute_force = AsyncMock(return_value=1)
        await bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        for call in mock_redis.increment_brute_force.call_args_list:
            assert call[0][1] == BruteForceThresholds.ATTEMPT_WINDOW_SECONDS


# ─────────────────────────────────────────────────────────────────────
# record_successful_login — reset compteurs
# ─────────────────────────────────────────────────────────────────────

class TestRecordSuccessfulLogin:
    """Tests pour record_successful_login() — reset après succès."""

    async def test_resets_email_counter(self, bf_service, mock_redis):
        """Reset le compteur email."""
        await bf_service.record_successful_login("test@example.com", "1.2.3.4")
        calls = mock_redis.reset_brute_force.call_args_list
        email_call = [c for c in calls if c[0][0] == f"{RedisKeys.BRUTE_FORCE_USER}test@example.com"]
        assert len(email_call) == 1

    async def test_resets_ip_counter(self, bf_service, mock_redis):
        """Reset le compteur IP."""
        await bf_service.record_successful_login("test@example.com", "1.2.3.4")
        calls = mock_redis.reset_brute_force.call_args_list
        ip_call = [c for c in calls if c[0][0] == f"{RedisKeys.BRUTE_FORCE_IP}1.2.3.4"]
        assert len(ip_call) == 1

    async def test_resets_both_counters(self, bf_service, mock_redis):
        """Reset les deux compteurs."""
        await bf_service.record_successful_login("test@example.com", "1.2.3.4")
        assert mock_redis.reset_brute_force.call_count == 2


# ─────────────────────────────────────────────────────────────────────
# Escalation levels — vérification exhaustive des seuils
# ─────────────────────────────────────────────────────────────────────

class TestEscalationLevels:
    """Vérification exhaustive de chaque niveau d'escalation (politique sans lockout)."""

    @pytest.mark.parametrize("attempts,expected_allowed,expected_captcha,expected_delay,expected_locked", [
        # Normal (0-2)
        (0, True, False, 0, False),
        (1, True, False, 0, False),
        (2, True, False, 0, False),
        # Captcha (3-4)
        (3, True, True, 0, False),
        (4, True, True, 0, False),
        # Delay (5+) — jamais de lockout dur
        (5, True, True, 1, False),    # 1 * 2^0 = 1
        (6, True, True, 2, False),    # 1 * 2^1 = 2
        (7, True, True, 4, False),    # 1 * 2^2 = 4
        (8, True, True, 8, False),    # 1 * 2^3 = 8
        (9, True, True, 16, False),   # 1 * 2^4 = 16
        (10, True, True, 30, False),  # 1 * 2^5 = 32 → plafonné à 30
    ], ids=[
        "normal-0", "normal-1", "normal-2",
        "captcha-3", "captcha-4",
        "delay-5-1s", "delay-6-2s", "delay-7-4s",
        "delay-8-8s", "delay-9-16s", "delay-10-30s",
    ])
    async def test_escalation_level(
        self, bf_service, mock_redis,
        attempts, expected_allowed, expected_captcha, expected_delay, expected_locked,
    ):
        """Vérifie l'escalation pour chaque nombre de tentatives."""
        mock_redis.get_brute_force_count = AsyncMock(return_value=attempts)
        status = await bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is expected_allowed
        assert status.captcha_required is expected_captcha
        assert status.delay_seconds == expected_delay
        assert status.locked is expected_locked


# ─────────────────────────────────────────────────────────────────────
# Instance variables — pas de class variables (fix bug ancien CaroCorp)
# ─────────────────────────────────────────────────────────────────────

class TestNoClassVariables:
    """Vérifie qu'il n'y a pas de class variables partagées (fix P0 ancien)."""

    def test_no_shared_state_between_instances(self):
        """Deux instances sont indépendantes (pas de class variable _memory_attempts)."""
        svc1 = BruteForceService()
        svc2 = BruteForceService()
        # Vérifie qu'il n'y a pas d'attributs de classe mutables
        class_attrs = {
            k: v for k, v in vars(BruteForceService).items()
            if not k.startswith("_") and not callable(v)
        }
        assert len(class_attrs) == 0, (
            f"BruteForceService a des class variables partagées : {class_attrs}"
        )

    def test_singleton_exists(self):
        """Le singleton brute_force_service est accessible."""
        from app.services.bruteforce import brute_force_service
        assert isinstance(brute_force_service, BruteForceService)


# ─────────────────────────────────────────────────────────────────────
# Thresholds constants — valeurs attendues
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceThresholds:
    """Vérifie les valeurs des constantes de seuil (politique sans lockout dur)."""

    def test_captcha_threshold(self):
        assert BruteForceThresholds.CAPTCHA_THRESHOLD == 3

    def test_delay_threshold(self):
        assert BruteForceThresholds.DELAY_THRESHOLD == 5

    def test_max_delay(self):
        assert BruteForceThresholds.MAX_DELAY_SECONDS == 30

    def test_attempt_window(self):
        assert BruteForceThresholds.ATTEMPT_WINDOW_SECONDS == 900

    def test_base_delay(self):
        assert BruteForceThresholds.BASE_DELAY_SECONDS == 1

    def test_escalation_order(self):
        """CAPTCHA_THRESHOLD < DELAY_THRESHOLD."""
        assert (
            BruteForceThresholds.CAPTCHA_THRESHOLD
            < BruteForceThresholds.DELAY_THRESHOLD
        )
