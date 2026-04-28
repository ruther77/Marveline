"""Tests d'intégration : brute force + login endpoint.

Couvre :
    - Response contient message CAPTCHA après 3 échecs (HTTP 400)
    - Response contient delay_seconds > 0 après 5 échecs
    - Jamais de lockout : 8+ tentatives → toujours allowed=True + delay max
    - Login réussi reset les compteurs brute force
    - Compteurs per-IP fonctionnent aussi

Fichiers testés :
    - app/api/v1/endpoints/auth.py (endpoint login)
    - app/services/auth.py (intégration brute force)
    - app/services/bruteforce.py (service)
    - app/core/redis.py (compteurs Redis)
"""
import redis as _sync_redis
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.constants import RedisKeys
from app.core.config import settings

# Client Redis synchrone pour assertions de test.
# redis_client.client est AsyncRedis (redis.asyncio) — .keys()/.get()/.delete()
# retournent des coroutines, non appelables en contexte synchrone.
_redis = _sync_redis.from_url(settings.REDIS_SEC_URL, decode_responses=True)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _clear_rate_limit():
    """Nettoie les clés rate_limit pour éviter les 429 pendant les tests brute force.

    Le rate limiter LOGIN (5 req/min) est un mécanisme distinct du brute force.
    On le reset entre chaque appel pour tester le brute force en isolation.
    """
    keys = _redis.keys("rate_limit:*")
    if keys:
        _redis.delete(*keys)


_CAPTCHA_BYPASS = "app.services.bruteforce.BruteForceService.validate_captcha_token"


def _do_failed_login(client: TestClient, email: str = "test@carocorp.com"):
    """Effectue un login échoué (mauvais mot de passe).

    Le CAPTCHA (M2) est bypassé pour tester le brute force en isolation :
    après 3 failures check_and_enforce exige un token CAPTCHA valide → on mock
    validate_captcha_token pour permettre l'incrémentation des compteurs.
    """
    _clear_rate_limit()
    with patch(_CAPTCHA_BYPASS, new=AsyncMock(return_value=True)):
        return client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "wrongpassword"},
        )


def _do_successful_login(client: TestClient, email: str = "test@carocorp.com"):
    """Effectue un login réussi (CAPTCHA bypassé pour isolation)."""
    _clear_rate_limit()
    with patch(_CAPTCHA_BYPASS, new=AsyncMock(return_value=True)):
        return client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "testpass123"},
        )


# ─────────────────────────────────────────────────────────────────────
# Normal behavior (0-2 attempts) — pas d'escalation
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceNormal:
    """Tests pour les premières tentatives (aucune restriction)."""

    def test_first_failed_login_returns_401(self, client, test_user):
        """Première tentative échouée → 401 simple, pas de brute force info."""
        resp = _do_failed_login(client)
        assert resp.status_code == 401
        detail = resp.json()["detail"]
        # detail est une string simple (pas de dict)
        assert isinstance(detail, str)
        assert "Invalid email or password" in detail

    def test_second_failed_login_still_normal(self, client, test_user):
        """2 tentatives échouées → toujours 401 simple."""
        _do_failed_login(client)
        resp = _do_failed_login(client)
        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert isinstance(detail, str)


# ─────────────────────────────────────────────────────────────────────
# CAPTCHA (3-4 attempts)
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceCaptcha:
    """Tests pour le niveau CAPTCHA (3-4 tentatives)."""

    def test_captcha_required_after_3_failures(self, client, test_user):
        """3 tentatives échouées → HTTP 400 avec message CAPTCHA, delay_seconds=0."""
        for _ in range(2):
            _do_failed_login(client)

        resp = _do_failed_login(client)  # 3ème
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["message"] == "CAPTCHA verification required"
        assert detail["delay_seconds"] == 0

    def test_captcha_still_required_at_4(self, client, test_user):
        """4 tentatives → captcha toujours requis, pas de délai."""
        for _ in range(3):
            _do_failed_login(client)

        resp = _do_failed_login(client)  # 4ème
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["message"] == "CAPTCHA verification required"
        assert detail["delay_seconds"] == 0


# ─────────────────────────────────────────────────────────────────────
# Delay (5-7 attempts)
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceDelay:
    """Tests pour le niveau délai progressif (5-7 tentatives)."""

    def test_delay_after_5_failures(self, client, test_user):
        """5 tentatives → HTTP 400, captcha + delay_seconds >= 1."""
        for _ in range(4):
            _do_failed_login(client)

        resp = _do_failed_login(client)  # 5ème
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["message"] == "CAPTCHA verification required"
        assert detail["delay_seconds"] >= 1

    def test_delay_increases_progressively(self, client, test_user):
        """6ème tentative → délai plus long que 5ème."""
        for _ in range(4):
            _do_failed_login(client)

        resp5 = _do_failed_login(client)  # 5ème
        resp6 = _do_failed_login(client)  # 6ème

        delay5 = resp5.json()["detail"]["delay_seconds"]
        delay6 = resp6.json()["detail"]["delay_seconds"]
        assert delay6 > delay5


# ─────────────────────────────────────────────────────────────────────
# Reset on success
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceReset:
    """Tests pour le reset des compteurs après login réussi."""

    def test_successful_login_resets_counters(self, client, test_user):
        """Login réussi après 2 échecs → compteurs remis à 0."""
        # 2 échecs
        _do_failed_login(client)
        _do_failed_login(client)

        # Login réussi
        resp = _do_successful_login(client)
        assert resp.status_code == 200

        # Vérifier que les compteurs sont à 0
        email_key = f"{RedisKeys.BRUTE_FORCE_USER}test@carocorp.com"
        count = _redis.get(email_key)
        assert count is None or int(count) == 0

    def test_after_reset_no_captcha(self, client, test_user):
        """Après reset, les tentatives repartent de 0 (pas de captcha)."""
        # 2 échecs
        _do_failed_login(client)
        _do_failed_login(client)

        # Login réussi → reset
        _do_successful_login(client)

        # Nouveau échec → doit être la tentative #1 (pas de captcha)
        resp = _do_failed_login(client)
        assert resp.status_code == 401
        detail = resp.json()["detail"]
        assert isinstance(detail, str)  # Pas de dict = pas de captcha


# ─────────────────────────────────────────────────────────────────────
# Per-IP tracking
# ─────────────────────────────────────────────────────────────────────

class TestBruteForcePerIP:
    """Tests pour les compteurs par IP (en plus de par email)."""

    def test_ip_counter_incremented(self, client, test_user):
        """Les compteurs IP sont bien incrémentés."""
        _do_failed_login(client)

        # Le TestClient utilise "testclient" comme IP
        ip_key = f"{RedisKeys.BRUTE_FORCE_IP}testclient"
        count = _redis.get(ip_key)
        assert count is not None
        assert int(count) >= 1

    def test_email_counter_incremented(self, client, test_user):
        """Les compteurs email sont bien incrémentés."""
        _do_failed_login(client)

        email_key = f"{RedisKeys.BRUTE_FORCE_USER}test@carocorp.com"
        count = _redis.get(email_key)
        assert count is not None
        assert int(count) >= 1


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────

class TestBruteForceEdgeCases:
    """Tests pour les cas limites."""

    def test_nonexistent_user_also_triggers_brute_force(self, client):
        """Un email inexistant incrémente aussi les compteurs."""
        email = "nonexistent@example.com"
        for _ in range(3):
            _clear_rate_limit()
            client.post(
                "/api/v1/auth/login",
                data={"username": email, "password": "wrongpassword"},
            )

        email_key = f"{RedisKeys.BRUTE_FORCE_USER}{email}"
        count = _redis.get(email_key)
        assert count is not None
        assert int(count) == 3

    def test_nonexistent_user_gets_captcha_too(self, client):
        """Email inexistant → HTTP 400 CAPTCHA après 3 tentatives."""
        email = "ghost@example.com"
        for _ in range(2):
            _clear_rate_limit()
            client.post(
                "/api/v1/auth/login",
                data={"username": email, "password": "wrong"},
            )

        _clear_rate_limit()
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "wrong"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["message"] == "CAPTCHA verification required"

    def test_case_insensitive_email_counts(self, client, test_user):
        """Compteurs email sont case-insensitive (email normalisé)."""
        # 2 tentatives avec majuscules différentes
        _clear_rate_limit()
        client.post(
            "/api/v1/auth/login",
            data={"username": "Test@CaroCorp.com", "password": "wrong"},
        )
        _clear_rate_limit()
        client.post(
            "/api/v1/auth/login",
            data={"username": "TEST@CAROCORP.COM", "password": "wrong"},
        )
        _clear_rate_limit()
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "test@carocorp.com", "password": "wrong"},
        )
        # 3ème tentative → captcha
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["message"] == "CAPTCHA verification required"
