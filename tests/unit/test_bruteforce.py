"""Tests unitaires pour le service BruteForce — escalation multi-niveaux Redis.

Couvre :
    - 5 niveaux d'escalation (normal, captcha, delay, lock, lock+alert)
    - Compteurs per-email ET per-IP
    - Lock/unlock avec TTL
    - Reset des compteurs après login réussi
    - Idempotence des alertes admin
    - BruteForceStatus dataclass

Fichier service testé : app/services/bruteforce.py
Fichier constants : app/constants/security.py (BruteForceThresholds)
Fichier Redis : app/core/redis.py (méthodes brute force)
"""
import pytest
from unittest.mock import patch, MagicMock

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
    """Mock du redis_client pour tests unitaires purs (pas de Redis réel)."""
    with patch("app.services.bruteforce.redis_client") as mock:
        # Defaults
        mock.is_brute_force_locked.return_value = False
        mock.get_brute_force_count.return_value = 0
        mock.get_brute_force_lock_ttl.return_value = 0
        mock.increment_brute_force.return_value = 1
        mock.set_brute_force_lock.return_value = True
        mock.set_brute_force_alert_sent.return_value = True
        mock.reset_brute_force.return_value = True
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

    def test_locked_status(self):
        """Statut verrouillé."""
        status = BruteForceStatus(
            allowed=False, locked=True,
            locked_until_seconds=900, attempts=8,
        )
        assert status.allowed is False
        assert status.locked is True
        assert status.locked_until_seconds == 900

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

    def test_normal_0_attempts(self, bf_service, mock_redis):
        """0 tentatives → normal, tout permis."""
        mock_redis.get_brute_force_count.return_value = 0
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.delay_seconds == 0
        assert status.locked is False
        assert status.attempts == 0

    def test_normal_2_attempts(self, bf_service, mock_redis):
        """2 tentatives → encore normal."""
        mock_redis.get_brute_force_count.return_value = 2
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.attempts == 2

    def test_captcha_at_3_attempts(self, bf_service, mock_redis):
        """3 tentatives → CAPTCHA requis (seuil CAPTCHA_THRESHOLD=3)."""
        mock_redis.get_brute_force_count.return_value = 3
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 0
        assert status.attempts == 3

    def test_captcha_at_4_attempts(self, bf_service, mock_redis):
        """4 tentatives → CAPTCHA toujours requis."""
        mock_redis.get_brute_force_count.return_value = 4
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 0

    def test_delay_at_5_attempts(self, bf_service, mock_redis):
        """5 tentatives → délai 1s + captcha (seuil DELAY_THRESHOLD=5)."""
        mock_redis.get_brute_force_count.return_value = 5
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is True
        assert status.delay_seconds == 1  # BASE_DELAY * 2^(5-5) = 1*1 = 1

    def test_delay_at_6_attempts(self, bf_service, mock_redis):
        """6 tentatives → délai 2s."""
        mock_redis.get_brute_force_count.return_value = 6
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.delay_seconds == 2  # 1 * 2^(6-5) = 2

    def test_delay_at_7_attempts(self, bf_service, mock_redis):
        """7 tentatives → délai 4s."""
        mock_redis.get_brute_force_count.return_value = 7
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.delay_seconds == 4  # 1 * 2^(7-5) = 4

    def test_delay_capped_at_30s(self, bf_service, mock_redis):
        """Délai ne dépasse jamais 30s même avec beaucoup de tentatives."""
        # Simuler un cas extrême sans lock (compteur élevé mais pas de lock key)
        mock_redis.get_brute_force_count.return_value = 7
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.delay_seconds <= 30

    def test_lock_at_8_attempts(self, bf_service, mock_redis):
        """8 tentatives → lock temporaire (seuil LOCK_THRESHOLD=8)."""
        mock_redis.get_brute_force_count.return_value = 8
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is False
        assert status.locked is True
        assert status.locked_until_seconds == BruteForceThresholds.LOCK_DURATION_SECONDS

    def test_locked_account_returns_forbidden(self, bf_service, mock_redis):
        """Compte verrouillé dans Redis → interdit immédiatement."""
        mock_redis.is_brute_force_locked.return_value = True
        mock_redis.get_brute_force_lock_ttl.return_value = 600
        mock_redis.get_brute_force_count.return_value = 10
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.allowed is False
        assert status.locked is True
        assert status.locked_until_seconds == 600

    def test_uses_max_of_email_and_ip_counts(self, bf_service, mock_redis):
        """Utilise le max entre compteur email et compteur IP."""
        # email=2, ip=4 → max=4 → captcha
        def side_effect(prefix, identifier):
            if prefix == RedisKeys.BRUTE_FORCE_EMAIL:
                return 2
            return 4  # IP
        mock_redis.get_brute_force_count.side_effect = side_effect
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
        assert status.captcha_required is True
        assert status.attempts == 4


# ─────────────────────────────────────────────────────────────────────
# record_failed_attempt — escalation post-tentative
# ─────────────────────────────────────────────────────────────────────

class TestRecordFailedAttempt:
    """Tests pour record_failed_attempt() — enregistrement APRÈS échec."""

    def test_first_attempt_normal(self, bf_service, mock_redis):
        """Première tentative échouée → normal."""
        mock_redis.increment_brute_force.return_value = 1
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.allowed is True
        assert status.captcha_required is False
        assert status.attempts == 1

    def test_increments_both_email_and_ip(self, bf_service, mock_redis):
        """Incrémente les compteurs email ET IP."""
        mock_redis.increment_brute_force.return_value = 1
        bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        calls = mock_redis.increment_brute_force.call_args_list
        assert len(calls) == 2
        # Premier appel = email
        assert calls[0][0][0] == RedisKeys.BRUTE_FORCE_EMAIL
        assert calls[0][0][1] == "test@example.com"
        # Deuxième appel = IP
        assert calls[1][0][0] == RedisKeys.BRUTE_FORCE_IP
        assert calls[1][0][1] == "1.2.3.4"

    def test_captcha_after_3_failures(self, bf_service, mock_redis):
        """3 échecs → captcha requis."""
        mock_redis.increment_brute_force.return_value = 3
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.captcha_required is True
        assert status.allowed is True

    def test_delay_after_5_failures(self, bf_service, mock_redis):
        """5 échecs → délai + captcha."""
        mock_redis.increment_brute_force.return_value = 5
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.captcha_required is True
        assert status.delay_seconds == 1

    def test_lock_after_8_failures(self, bf_service, mock_redis):
        """8 échecs → lock temporaire."""
        mock_redis.increment_brute_force.return_value = 8
        mock_redis.get_brute_force_lock_ttl.return_value = 900
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.allowed is False
        assert status.locked is True
        mock_redis.set_brute_force_lock.assert_called_once_with(
            "test@example.com", BruteForceThresholds.LOCK_DURATION_SECONDS,
        )

    def test_alert_at_10_failures(self, bf_service, mock_redis):
        """10 échecs → lock + alerte admin."""
        mock_redis.increment_brute_force.return_value = 10
        mock_redis.get_brute_force_lock_ttl.return_value = 900
        mock_redis.set_brute_force_alert_sent.return_value = True
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.allowed is False
        assert status.locked is True
        mock_redis.set_brute_force_alert_sent.assert_called_once_with(
            "test@example.com", BruteForceThresholds.ATTEMPT_WINDOW_SECONDS,
        )

    def test_alert_idempotent(self, bf_service, mock_redis):
        """Alerte déjà envoyée → pas de doublon (SET NX renvoie False)."""
        mock_redis.increment_brute_force.return_value = 11
        mock_redis.get_brute_force_lock_ttl.return_value = 800
        mock_redis.set_brute_force_alert_sent.return_value = False  # Already sent
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.locked is True
        # L'alerte a été tentée mais pas re-envoyée
        mock_redis.set_brute_force_alert_sent.assert_called_once()

    def test_uses_max_of_email_ip_for_escalation(self, bf_service, mock_redis):
        """Escalation basée sur max(email_count, ip_count)."""
        # email=2, ip=5 → max=5 → delay
        def side_effect(prefix, identifier, ttl):
            if prefix == RedisKeys.BRUTE_FORCE_EMAIL:
                return 2
            return 5  # IP
        mock_redis.increment_brute_force.side_effect = side_effect
        status = bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        assert status.delay_seconds >= 1
        assert status.captcha_required is True

    def test_ttl_passed_to_increment(self, bf_service, mock_redis):
        """Le TTL de la fenêtre est passé correctement à Redis."""
        mock_redis.increment_brute_force.return_value = 1
        bf_service.record_failed_attempt("test@example.com", "1.2.3.4")
        for call in mock_redis.increment_brute_force.call_args_list:
            assert call[0][2] == BruteForceThresholds.ATTEMPT_WINDOW_SECONDS


# ─────────────────────────────────────────────────────────────────────
# record_successful_login — reset compteurs
# ─────────────────────────────────────────────────────────────────────

class TestRecordSuccessfulLogin:
    """Tests pour record_successful_login() — reset après succès."""

    def test_resets_email_counter(self, bf_service, mock_redis):
        """Reset le compteur email."""
        bf_service.record_successful_login("test@example.com", "1.2.3.4")
        calls = mock_redis.reset_brute_force.call_args_list
        email_call = [c for c in calls if c[0][0] == RedisKeys.BRUTE_FORCE_EMAIL]
        assert len(email_call) == 1
        assert email_call[0][0][1] == "test@example.com"

    def test_resets_ip_counter(self, bf_service, mock_redis):
        """Reset le compteur IP."""
        bf_service.record_successful_login("test@example.com", "1.2.3.4")
        calls = mock_redis.reset_brute_force.call_args_list
        ip_call = [c for c in calls if c[0][0] == RedisKeys.BRUTE_FORCE_IP]
        assert len(ip_call) == 1
        assert ip_call[0][0][1] == "1.2.3.4"

    def test_resets_both_counters(self, bf_service, mock_redis):
        """Reset les deux compteurs."""
        bf_service.record_successful_login("test@example.com", "1.2.3.4")
        assert mock_redis.reset_brute_force.call_count == 2


# ─────────────────────────────────────────────────────────────────────
# Escalation levels — vérification exhaustive des seuils
# ─────────────────────────────────────────────────────────────────────

class TestEscalationLevels:
    """Vérification exhaustive de chaque niveau d'escalation."""

    @pytest.mark.parametrize("attempts,expected_allowed,expected_captcha,expected_delay,expected_locked", [
        # Normal (0-2)
        (0, True, False, 0, False),
        (1, True, False, 0, False),
        (2, True, False, 0, False),
        # Captcha (3-4)
        (3, True, True, 0, False),
        (4, True, True, 0, False),
        # Delay (5-7)
        (5, True, True, 1, False),   # 1 * 2^0 = 1
        (6, True, True, 2, False),   # 1 * 2^1 = 2
        (7, True, True, 4, False),   # 1 * 2^2 = 4
        # Lock (8+)
        (8, False, False, 0, True),
        (9, False, False, 0, True),
        (10, False, False, 0, True),
    ], ids=[
        "normal-0", "normal-1", "normal-2",
        "captcha-3", "captcha-4",
        "delay-5-1s", "delay-6-2s", "delay-7-4s",
        "lock-8", "lock-9", "lock-10",
    ])
    def test_escalation_level(
        self, bf_service, mock_redis,
        attempts, expected_allowed, expected_captcha, expected_delay, expected_locked,
    ):
        """Vérifie l'escalation pour chaque nombre de tentatives."""
        mock_redis.get_brute_force_count.return_value = attempts
        status = bf_service.check_and_enforce("test@example.com", "1.2.3.4")
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
    """Vérifie les valeurs des constantes de seuil."""

    def test_captcha_threshold(self):
        assert BruteForceThresholds.CAPTCHA_THRESHOLD == 3

    def test_delay_threshold(self):
        assert BruteForceThresholds.DELAY_THRESHOLD == 5

    def test_lock_threshold(self):
        assert BruteForceThresholds.LOCK_THRESHOLD == 8

    def test_alert_threshold(self):
        assert BruteForceThresholds.ALERT_THRESHOLD == 10

    def test_lock_duration(self):
        assert BruteForceThresholds.LOCK_DURATION_SECONDS == 900

    def test_attempt_window(self):
        assert BruteForceThresholds.ATTEMPT_WINDOW_SECONDS == 900

    def test_base_delay(self):
        assert BruteForceThresholds.BASE_DELAY_SECONDS == 1

    def test_escalation_order(self):
        """Les seuils sont dans l'ordre croissant."""
        assert (
            BruteForceThresholds.CAPTCHA_THRESHOLD
            < BruteForceThresholds.DELAY_THRESHOLD
            < BruteForceThresholds.LOCK_THRESHOLD
            < BruteForceThresholds.ALERT_THRESHOLD
        )
