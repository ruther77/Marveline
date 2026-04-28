"""Tests intégration — Credential Stuffing (M3) et CAPTCHA (M2).

Couverture (CaroCorp §7.2 NIVEAUX 3-4) :
  M3 — Credential stuffing global :
    - login:blocked → 429 LOGIN_GLOBALLY_BLOCKED (distinct du lockout compte)
    - N failures globales > CAPTCHA_THRESHOLD → captcha:required activé en Redis-SEC
    - N failures globales > BLOCK_THRESHOLD    → login:blocked activé en Redis-SEC

  M2 — CAPTCHA validation serveur (hCaptcha FAIL-CLOSED) :
    - Flag global captcha:required → 400 CAPTCHA_REQUIRED sans X-Captcha-Token
    - Token invalide (mock hCaptcha success=False) → 400 CAPTCHA_REQUIRED
    - Token valide (mock hCaptcha success=True) → CAPTCHA check passé, flow normal
    - Per-user CAPTCHA (3 échecs bf) → 4ème tentative sans token → 400 CAPTCHA_REQUIRED

Note isolation : cleanup_stuffing_keys nettoie les flags non couverts par le conftest
global (captcha:required, login:blocked, credential_stuffing:*).
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.constants import CredentialStuffingThresholds, RedisKeys
from app.core.redis import redis_sec
from app.services.bruteforce import brute_force_service

_SECURITY_KEYS = [RedisKeys.CAPTCHA_REQUIRED, RedisKeys.LOGIN_BLOCKED]


@pytest.fixture(autouse=True)
def cleanup_stuffing_keys():
    """Nettoie les flags credential stuffing avant et après chaque test."""
    def _clean():
        for key in _SECURITY_KEYS:
            redis_sec.client.delete(key)
        for k in redis_sec.client.scan_iter(f"{RedisKeys.CREDENTIAL_STUFFING}*"):
            redis_sec.client.delete(k)

    _clean()
    yield
    _clean()


# ──────────────────────────────────────────────────────────────────────────────
# M3 — Credential Stuffing Global
# ──────────────────────────────────────────────────────────────────────────────

def test_login_globally_blocked_returns_429(client: TestClient):
    """login:blocked → 429 distinct du lockout compte individuel."""
    redis_sec.set_login_blocked(ttl=60)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "any@example.com", "password": "anypassword"},
    )

    assert response.status_code == 429
    assert "Login temporarily blocked" in response.json()["detail"]


def test_login_blocked_is_distinct_from_account_lockout(client: TestClient):
    """login:blocked → 429 même pour email inconnu (blocage global, pas per-user)."""
    redis_sec.set_login_blocked(ttl=60)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent@nowhere.com", "password": "whatever"},
    )

    assert response.status_code == 429


def test_record_global_failure_triggers_captcha_flag():
    """CAPTCHA_THRESHOLD+1 failures globales → captcha:required activé en Redis-SEC."""
    minute_key = (
        f"{RedisKeys.CREDENTIAL_STUFFING}"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    )
    # Pré-positionner le compteur exactement au seuil — l'INCR suivant le dépasse
    redis_sec.client.set(minute_key, CredentialStuffingThresholds.CAPTCHA_THRESHOLD, ex=600)

    brute_force_service.record_global_failure()

    assert redis_sec.is_captcha_required() is True
    assert redis_sec.is_login_blocked() is False  # Pas encore bloqué


def test_record_global_failure_triggers_blocked_flag():
    """BLOCK_THRESHOLD+1 failures globales → login:blocked activé en Redis-SEC."""
    minute_key = (
        f"{RedisKeys.CREDENTIAL_STUFFING}"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    )
    redis_sec.client.set(minute_key, CredentialStuffingThresholds.BLOCK_THRESHOLD, ex=600)

    brute_force_service.record_global_failure()

    assert redis_sec.is_login_blocked() is True


def test_record_global_failure_warning_only_below_captcha_threshold():
    """Failures < CAPTCHA_THRESHOLD → pas de flag activé (seulement WARNING log)."""
    minute_key = (
        f"{RedisKeys.CREDENTIAL_STUFFING}"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    )
    # Au-dessus du WARNING_THRESHOLD (50) mais EN-DESSOUS du CAPTCHA_THRESHOLD (200)
    below_captcha = CredentialStuffingThresholds.CAPTCHA_THRESHOLD - 1
    redis_sec.client.set(minute_key, below_captcha, ex=600)

    brute_force_service.record_global_failure()  # count = CAPTCHA_THRESHOLD → > WARNING mais pas > CAPTCHA

    # Exactement CAPTCHA_THRESHOLD = 200, condition est > 200 → pas activé
    assert redis_sec.is_captcha_required() is False
    assert redis_sec.is_login_blocked() is False


# ──────────────────────────────────────────────────────────────────────────────
# M2 — CAPTCHA Validation Serveur
# ──────────────────────────────────────────────────────────────────────────────

def test_captcha_global_flag_no_token_returns_400(client: TestClient):
    """Flag captcha:required actif + aucun token → 400 CAPTCHA_REQUIRED."""
    redis_sec.set_captcha_required(ttl=60)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "any@example.com", "password": "anypassword"},
    )

    assert response.status_code == 400
    assert "CAPTCHA" in response.json()["detail"]


def test_captcha_global_flag_invalid_token_returns_400(client: TestClient):
    """Flag captcha:required actif + token invalide (hCaptcha success=False) → 400."""
    redis_sec.set_captcha_required(ttl=60)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"success": False}

    with patch("app.services.bruteforce.httpx.post", return_value=mock_resp):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "any@example.com", "password": "anypassword"},
            headers={"X-Captcha-Token": "invalid_token_xyz"},
        )

    assert response.status_code == 400
    assert "CAPTCHA" in response.json()["detail"]


def test_captcha_global_flag_valid_token_bypasses_captcha_check(client: TestClient):
    """Flag captcha:required actif + token valide (hCaptcha success=True) → CAPTCHA passé.

    La requête doit aller jusqu'à la vérification des credentials (pas 400).
    Ici les creds sont invalides → 401, ce qui prouve que le CAPTCHA check n'a pas bloqué.
    """
    redis_sec.set_captcha_required(ttl=60)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"success": True}

    with patch("app.services.bruteforce.httpx.post", return_value=mock_resp):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "any@example.com", "password": "wrongpassword"},
            headers={"X-Captcha-Token": "valid_token_abc"},
        )

    # Le CAPTCHA est passé → flow auth normal → 401 creds invalides (pas 400)
    assert response.status_code == 401
    assert response.json()["detail"] != "CAPTCHA verification required"


def test_per_user_captcha_triggered_after_3_failures(client: TestClient, test_user):
    """3 échecs per-user → 4ème tentative sans X-Captcha-Token → 400 CAPTCHA_REQUIRED."""
    bad_creds = {"username": "test@carocorp.com", "password": "WRONG_PASS_XYZ"}

    # 3 tentatives échouées → incrémentent bf_email et bf_ip
    for _ in range(3):
        client.post("/api/v1/auth/login", data=bad_creds)

    # 4ème tentative — bf_status.captcha_required=True, aucun token → 400
    response = client.post("/api/v1/auth/login", data=bad_creds)

    assert response.status_code == 400
    detail = response.json()["detail"]
    # detail peut être string "CAPTCHA verification required" ou dict
    if isinstance(detail, dict):
        assert detail.get("captcha_required") is True
    else:
        assert "CAPTCHA" in detail


def test_captcha_api_down_fail_closed(client: TestClient):
    """hCaptcha API inaccessible + captcha requis → FAIL-CLOSED → 400 (pas de bypass)."""
    redis_sec.set_captcha_required(ttl=60)

    with patch(
        "app.services.bruteforce.httpx.post",
        side_effect=ConnectionError("hCaptcha unreachable"),
    ):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "any@example.com", "password": "anypassword"},
            headers={"X-Captcha-Token": "any_token"},
        )

    # FAIL-CLOSED : exception → validate_captcha_token retourne False → 400
    assert response.status_code == 400
    assert "CAPTCHA" in response.json()["detail"]
