"""Tests d'intégration pour les endpoints MFA TOTP.

Couvre:
    - POST /mfa/setup (génère secret + QR URI + recovery codes)
    - POST /mfa/verify-setup (active MFA après vérification code)
    - POST /mfa/verify (step 2 du login : mfa_session_token → JWT tokens)
    - GET /mfa/status (statut MFA de l'utilisateur)
    - DELETE /mfa (désactive MFA)
    - Flow complet login 2 étapes avec MFA
    - Recovery codes (usage unique)
    - Anti-cross-tenant
"""
import pyotp
import pytest
from fastapi.testclient import TestClient

from app.models.mfa import MFADevice


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _login(client: TestClient, email: str = "test@carocorp.com", password: str = "testpass123"):
    """Login helper — retourne la réponse JSON."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    return resp


def _get_auth_headers(client: TestClient, email: str = "test@carocorp.com", password: str = "testpass123"):
    """Login + retourne headers Authorization + CSRF token."""
    resp = _login(client, email, password)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data, f"Expected access_token, got: {data}"
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    # Obtenir token CSRF pour les requêtes modifiantes (POST, DELETE)
    csrf_resp = client.get("/api/v1/auth/csrf", headers=headers)
    assert csrf_resp.status_code == 200
    headers["X-CSRF-Token"] = csrf_resp.json()["csrf_token"]

    return headers


def _setup_and_enable_mfa(client: TestClient, test_db, email="test@carocorp.com", password="testpass123"):
    """Helper complet: login → setup MFA → verify-setup → reset anti-replay.

    Returns:
        Tuple (secret, recovery_codes, auth_headers)
    """
    headers = _get_auth_headers(client, email, password)

    # Setup MFA
    setup_resp = client.post("/api/v1/mfa/setup", headers=headers)
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    secret = setup_data["secret"]
    recovery_codes = setup_data["recovery_codes"]

    # Générer code TOTP valide
    totp = pyotp.TOTP(secret)
    code = totp.now()

    # Verify setup (active MFA)
    verify_resp = client.post(
        "/api/v1/mfa/verify-setup",
        json={"totp_code": code},
        headers=headers,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["enabled"] is True

    # Reset anti-replay pour permettre d'utiliser le même window dans les tests suivants
    device = (
        test_db.query(MFADevice)
        .filter(MFADevice.is_enabled == True)  # noqa: E712
        .first()
    )
    if device:
        device.last_totp_window = 0
        test_db.commit()

    return secret, recovery_codes, headers


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests Setup MFA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMFASetup:
    """Tests pour POST /mfa/setup."""

    def test_setup_returns_secret_and_uri(self, client: TestClient, test_user):
        """Setup retourne secret, URI et recovery codes."""
        headers = _get_auth_headers(client)
        resp = client.post("/api/v1/mfa/setup", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "recovery_codes" in data
        assert data["provisioning_uri"].startswith("otpauth://totp/")
        assert len(data["recovery_codes"]) == 8
        # Secret doit être base32 valide
        assert len(data["secret"]) >= 16

    def test_setup_without_auth_returns_401(self, client: TestClient):
        """Setup sans JWT → 401."""
        resp = client.post("/api/v1/mfa/setup")
        assert resp.status_code == 401

    def test_setup_twice_replaces_pending(self, client: TestClient, test_user):
        """Deux setups consécutifs (sans verify) remplacent le pending."""
        headers = _get_auth_headers(client)

        resp1 = client.post("/api/v1/mfa/setup", headers=headers)
        assert resp1.status_code == 200
        secret1 = resp1.json()["secret"]

        resp2 = client.post("/api/v1/mfa/setup", headers=headers)
        assert resp2.status_code == 200
        secret2 = resp2.json()["secret"]

        # Secrets différents (nouveau device créé)
        assert secret1 != secret2

    def test_setup_after_enable_returns_400(self, client: TestClient, test_user, test_db):
        """Setup après MFA activé → 400."""
        _, _, headers = _setup_and_enable_mfa(client, test_db)
        resp = client.post("/api/v1/mfa/setup", headers=headers)

        assert resp.status_code == 400
        assert "already enabled" in resp.json()["detail"].lower()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests Verify Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMFAVerifySetup:
    """Tests pour POST /mfa/verify-setup."""

    def test_verify_setup_valid_code(self, client: TestClient, test_user):
        """Verify-setup avec code valide active le MFA."""
        headers = _get_auth_headers(client)

        # Setup
        setup_resp = client.post("/api/v1/mfa/setup", headers=headers)
        secret = setup_resp.json()["secret"]

        # Générer code TOTP
        totp = pyotp.TOTP(secret)
        code = totp.now()

        # Verify
        resp = client.post(
            "/api/v1/mfa/verify-setup",
            json={"totp_code": code},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

    def test_verify_setup_invalid_code(self, client: TestClient, test_user):
        """Verify-setup avec code invalide → 400."""
        headers = _get_auth_headers(client)

        client.post("/api/v1/mfa/setup", headers=headers)

        resp = client.post(
            "/api/v1/mfa/verify-setup",
            json={"totp_code": "000000"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_verify_setup_no_pending(self, client: TestClient, test_user):
        """Verify-setup sans setup préalable → 400."""
        headers = _get_auth_headers(client)

        resp = client.post(
            "/api/v1/mfa/verify-setup",
            json={"totp_code": "123456"},
            headers=headers,
        )
        assert resp.status_code == 400


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests Login Flow 2 étapes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMFALoginFlow:
    """Tests pour le flow login 2 étapes avec MFA."""

    def test_login_with_mfa_returns_mfa_session_token(self, client: TestClient, test_user, test_db):
        """Login avec MFA activé retourne mfa_session_token au lieu de JWT."""
        _setup_and_enable_mfa(client, test_db)

        # Re-login
        resp = _login(client)
        assert resp.status_code == 200
        data = resp.json()

        assert data["mfa_required"] is True
        assert "mfa_session_token" in data
        assert data["token_type"] == "mfa_session"
        # Pas de access_token ni refresh_token
        assert "access_token" not in data

    def test_mfa_verify_with_totp_code(self, client: TestClient, test_user, test_db):
        """Flow complet: login → mfa_session_token → /mfa/verify → JWT tokens."""
        secret, _, _ = _setup_and_enable_mfa(client, test_db)

        # Step 1: Login (password) → mfa_session_token
        login_resp = _login(client)
        assert login_resp.status_code == 200
        mfa_data = login_resp.json()
        assert mfa_data["mfa_required"] is True
        mfa_token = mfa_data["mfa_session_token"]

        # Step 2: Verify MFA → JWT tokens
        totp = pyotp.TOTP(secret)
        code = totp.now()

        verify_resp = client.post(
            "/api/v1/mfa/verify",
            json={
                "mfa_session_token": mfa_token,
                "totp_code": code,
            },
        )
        assert verify_resp.status_code == 200
        tokens = verify_resp.json()
        assert "access_token" in tokens
        assert "refresh_token" in verify_resp.cookies  # httpOnly cookie
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] > 0

    def test_mfa_verify_with_recovery_code(self, client: TestClient, test_user, test_db):
        """Flow complet avec recovery code au lieu de TOTP."""
        _, recovery_codes, _ = _setup_and_enable_mfa(client, test_db)

        # Step 1: Login → mfa_session_token
        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]

        # Step 2: Verify avec recovery code
        verify_resp = client.post(
            "/api/v1/mfa/verify",
            json={
                "mfa_session_token": mfa_token,
                "recovery_code": recovery_codes[0],
            },
        )
        assert verify_resp.status_code == 200
        assert "access_token" in verify_resp.json()

    def test_recovery_code_single_use(self, client: TestClient, test_user, test_db):
        """Recovery code ne peut être utilisé qu'une fois."""
        _, recovery_codes, _ = _setup_and_enable_mfa(client, test_db)
        used_code = recovery_codes[0]

        # Premier usage — OK
        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]
        resp1 = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token, "recovery_code": used_code},
        )
        assert resp1.status_code == 200

        # Deuxième usage — même code réutilisé
        login_resp2 = _login(client)
        mfa_token2 = login_resp2.json()["mfa_session_token"]
        resp2 = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token2, "recovery_code": used_code},
        )
        assert resp2.status_code == 401

    def test_mfa_verify_invalid_session_token(self, client: TestClient, test_user, test_db):
        """MFA verify avec token de session invalide → 401."""
        _setup_and_enable_mfa(client, test_db)

        totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
        resp = client.post(
            "/api/v1/mfa/verify",
            json={
                "mfa_session_token": "totally_invalid_token_here",
                "totp_code": totp.now(),
            },
        )
        assert resp.status_code == 401

    def test_mfa_session_token_single_use(self, client: TestClient, test_user, test_db):
        """MFA session token ne peut être utilisé qu'une fois (supprimé après lecture)."""
        secret, _, _ = _setup_and_enable_mfa(client, test_db)

        # Login → mfa_session_token
        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]

        # Premier usage — OK
        totp = pyotp.TOTP(secret)
        code = totp.now()
        resp1 = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token, "totp_code": code},
        )
        assert resp1.status_code == 200

        # Deuxième usage du même mfa_session_token — doit échouer
        resp2 = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token, "totp_code": code},
        )
        assert resp2.status_code == 401

    def test_mfa_verify_wrong_totp_code(self, client: TestClient, test_user, test_db):
        """MFA verify avec mauvais code TOTP → 401."""
        _setup_and_enable_mfa(client, test_db)

        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]

        resp = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token, "totp_code": "000000"},
        )
        assert resp.status_code == 401

    def test_mfa_verify_both_codes_returns_400(self, client: TestClient, test_user, test_db):
        """MFA verify avec totp_code ET recovery_code → 400."""
        secret, recovery_codes, _ = _setup_and_enable_mfa(client, test_db)

        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]

        totp = pyotp.TOTP(secret)
        resp = client.post(
            "/api/v1/mfa/verify",
            json={
                "mfa_session_token": mfa_token,
                "totp_code": totp.now(),
                "recovery_code": recovery_codes[0],
            },
        )
        assert resp.status_code == 400

    def test_mfa_verify_no_code_returns_400(self, client: TestClient, test_user, test_db):
        """MFA verify sans aucun code → 400."""
        _setup_and_enable_mfa(client, test_db)

        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]

        resp = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token},
        )
        assert resp.status_code == 400

    def test_tokens_from_mfa_verify_are_usable(self, client: TestClient, test_user, test_db):
        """Les tokens JWT obtenus après /mfa/verify sont fonctionnels."""
        secret, _, _ = _setup_and_enable_mfa(client, test_db)

        # Login 2 steps
        login_resp = _login(client)
        mfa_token = login_resp.json()["mfa_session_token"]

        totp = pyotp.TOTP(secret)
        verify_resp = client.post(
            "/api/v1/mfa/verify",
            json={"mfa_session_token": mfa_token, "totp_code": totp.now()},
        )
        tokens = verify_resp.json()

        # Utiliser l'access token pour un endpoint protégé
        me_resp = client.get(
            "/api/v1/mfa/status",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["mfa_enabled"] is True

    def test_login_without_mfa_returns_tokens_directly(self, client: TestClient, test_user):
        """Login sans MFA activé retourne directement les tokens JWT."""
        resp = _login(client)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in resp.cookies  # httpOnly cookie
        assert "mfa_required" not in data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests MFA Status
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMFAStatus:
    """Tests pour GET /mfa/status."""

    def test_status_mfa_disabled(self, client: TestClient, test_user):
        """Status sans MFA activé."""
        headers = _get_auth_headers(client)
        resp = client.get("/api/v1/mfa/status", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_enabled"] is False
        assert data["recovery_codes_remaining"] == 0

    def test_status_mfa_enabled(self, client: TestClient, test_user, test_db):
        """Status avec MFA activé."""
        _, _, headers = _setup_and_enable_mfa(client, test_db)

        resp = client.get("/api/v1/mfa/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_enabled"] is True
        assert data["recovery_codes_remaining"] == 8

    def test_status_without_auth_returns_401(self, client: TestClient):
        """Status sans JWT → 401."""
        resp = client.get("/api/v1/mfa/status")
        assert resp.status_code == 401


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests Disable MFA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMFADisable:
    """Tests pour DELETE /mfa."""

    def test_disable_mfa(self, client: TestClient, test_user, test_db):
        """Désactive le MFA avec succès."""
        _, _, headers = _setup_and_enable_mfa(client, test_db)

        resp = client.delete("/api/v1/mfa", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["disabled"] is True

        # Vérifier que MFA est bien désactivé
        status_resp = client.get("/api/v1/mfa/status", headers=headers)
        assert status_resp.json()["mfa_enabled"] is False

    def test_disable_when_not_enabled(self, client: TestClient, test_user):
        """Désactivation MFA quand pas activé → 400."""
        headers = _get_auth_headers(client)
        resp = client.delete("/api/v1/mfa", headers=headers)

        assert resp.status_code == 400

    def test_login_after_disable_returns_tokens(self, client: TestClient, test_user, test_db):
        """Login après désactivation MFA retourne directement les tokens."""
        _, _, headers = _setup_and_enable_mfa(client, test_db)

        # Disable MFA
        client.delete("/api/v1/mfa", headers=headers)

        # Re-login — devrait retourner tokens directement (plus de MFA)
        login_resp = _login(client)
        assert login_resp.status_code == 200
        data = login_resp.json()
        assert "access_token" in data
        assert "mfa_required" not in data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tests Cross-Tenant
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMFACrossTenant:
    """Tests d'isolation multi-tenant pour MFA."""

    def test_mfa_setup_isolated_per_tenant(self, client: TestClient, test_user, test_user_tenant2, test_db):
        """MFA de tenant 1 ne voit pas le device de tenant 2."""
        # Setup MFA pour user tenant 1
        _setup_and_enable_mfa(client, test_db, email="test@carocorp.com")

        # User tenant 2 devrait voir MFA disabled
        headers_t2 = _get_auth_headers(client, email="test@tenant2.com")
        resp = client.get("/api/v1/mfa/status", headers=headers_t2)
        assert resp.status_code == 200
        assert resp.json()["mfa_enabled"] is False
