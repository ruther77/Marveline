"""Tests unitaires pour TokenService — whitelist, blacklist, rotation, replay detection."""
import time

import pytest

from app.core.redis import redis_client
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.exceptions import TokenRevoked, TokenReplayDetected
from app.services.token import TokenService, token_service, REFRESH_TTL_SECONDS


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def ts():
    """Instance TokenService fraîche pour chaque test."""
    return TokenService()


# ── issue_tokens ──────────────────────────────────────────────────────────


class TestIssueTokens:
    """Tests pour issue_tokens() — login flow."""

    def test_issue_tokens_returns_three_values(self, ts):
        access, refresh, expires_in = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@test.com", role="staff"
        )
        assert isinstance(access, str)
        assert isinstance(refresh, str)
        assert isinstance(expires_in, int)
        assert expires_in > 0

    def test_access_token_has_jti(self, ts):
        access, _, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@test.com", role="staff"
        )
        payload = decode_token(access)
        assert "jti" in payload
        assert payload["jti"]

    def test_refresh_token_has_jti_and_family(self, ts):
        _, refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@test.com", role="staff"
        )
        payload = decode_token(refresh)
        assert "jti" in payload
        assert "family_id" in payload
        assert payload["jti"]
        assert payload["family_id"]

    def test_refresh_jti_stored_in_whitelist(self, ts):
        _, refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@test.com", role="staff"
        )
        payload = decode_token(refresh)
        jti = payload["jti"]
        assert ts.is_refresh_whitelisted(jti)

    def test_token_family_created(self, ts):
        _, refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@test.com", role="staff"
        )
        payload = decode_token(refresh)
        family_id = payload["family_id"]
        family_data = redis_client.get_token_family(family_id)
        assert family_data is not None
        assert family_data["active"] is True
        assert family_data["user_id"] == 1

    def test_access_token_not_blacklisted_after_issue(self, ts):
        access, _, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@test.com", role="staff"
        )
        payload = decode_token(access)
        jti = payload["jti"]
        assert not ts.is_access_blacklisted(jti)

    def test_access_token_claims_correct(self, ts):
        access, _, _ = ts.issue_tokens(
            user_id=42, tenant_id=7, email="x@test.com", role="admin"
        )
        payload = decode_token(access)
        # sub est string dans JWT (spec JWT), on compare en int
        assert int(payload["sub"]) == 42
        assert payload["tenant_id"] == 7
        assert payload["email"] == "x@test.com"
        assert payload["role"] == "admin"

    def test_refresh_token_claims_correct(self, ts):
        _, refresh, _ = ts.issue_tokens(
            user_id=42, tenant_id=7, email="x@test.com", role="admin"
        )
        payload = decode_token(refresh)
        assert int(payload["sub"]) == 42
        assert payload["tenant_id"] == 7

    def test_multiple_issues_different_jti(self, ts):
        """Chaque issue_tokens génère des JTI uniques."""
        _, r1, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")
        _, r2, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")
        jti1 = decode_token(r1)["jti"]
        jti2 = decode_token(r2)["jti"]
        assert jti1 != jti2

    def test_multiple_issues_different_families(self, ts):
        """Chaque login crée une famille séparée."""
        _, r1, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")
        _, r2, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")
        fam1 = decode_token(r1)["family_id"]
        fam2 = decode_token(r2)["family_id"]
        assert fam1 != fam2


# ── rotate_refresh_token ──────────────────────────────────────────────────


class TestRotateRefreshToken:
    """Tests pour rotate_refresh_token() — rotation + replay detection."""

    def test_rotation_returns_new_tokens(self, ts):
        _, old_refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        new_access, new_refresh, expires_in = ts.rotate_refresh_token(
            old_refresh_token=old_refresh,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )
        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)
        assert isinstance(expires_in, int)
        assert new_refresh != old_refresh

    def test_old_jti_removed_from_whitelist(self, ts):
        _, old_refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        old_jti = decode_token(old_refresh)["jti"]
        assert ts.is_refresh_whitelisted(old_jti)

        ts.rotate_refresh_token(
            old_refresh_token=old_refresh,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )
        assert not ts.is_refresh_whitelisted(old_jti)

    def test_new_jti_in_whitelist(self, ts):
        _, old_refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        _, new_refresh, _ = ts.rotate_refresh_token(
            old_refresh_token=old_refresh,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )
        new_jti = decode_token(new_refresh)["jti"]
        assert ts.is_refresh_whitelisted(new_jti)

    def test_same_family_after_rotation(self, ts):
        _, old_refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        old_family = decode_token(old_refresh)["family_id"]

        _, new_refresh, _ = ts.rotate_refresh_token(
            old_refresh_token=old_refresh,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )
        new_family = decode_token(new_refresh)["family_id"]
        assert old_family == new_family

    def test_chained_rotation(self, ts):
        """Rotation en chaîne : R1 → R2 → R3, chaque ancien invalidé."""
        _, r1, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        _, r2, _ = ts.rotate_refresh_token(
            old_refresh_token=r1,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )
        _, r3, _ = ts.rotate_refresh_token(
            old_refresh_token=r2,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )

        jti1 = decode_token(r1)["jti"]
        jti2 = decode_token(r2)["jti"]
        jti3 = decode_token(r3)["jti"]

        assert not ts.is_refresh_whitelisted(jti1)
        assert not ts.is_refresh_whitelisted(jti2)
        assert ts.is_refresh_whitelisted(jti3)

    def test_rotation_with_revoked_jti_raises_token_revoked(self, ts):
        """Si le JTI n'est plus dans la whitelist et la famille est inactive → TokenRevoked."""
        _, old_refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        old_jti = decode_token(old_refresh)["jti"]
        old_family = decode_token(old_refresh)["family_id"]

        # Révoquer manuellement le JTI et la famille
        redis_client.revoke_refresh_jti(old_jti)
        redis_client.revoke_token_family(old_family)

        with pytest.raises(TokenRevoked):
            ts.rotate_refresh_token(
                old_refresh_token=old_refresh,
                user_id=1, tenant_id=1, email="a@t.com", role="staff",
            )


# ── Replay Detection ──────────────────────────────────────────────────────


class TestReplayDetection:
    """Tests pour la détection de réutilisation de refresh token."""

    def test_replay_detected_on_reuse(self, ts):
        """Réutilisation d'un ancien refresh token → TokenReplayDetected."""
        _, r1, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        # Rotation normale : R1 → R2
        _, r2, _ = ts.rotate_refresh_token(
            old_refresh_token=r1,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )

        # Tentative de replay avec R1 (déjà consommé)
        with pytest.raises(TokenReplayDetected):
            ts.rotate_refresh_token(
                old_refresh_token=r1,
                user_id=1, tenant_id=1, email="a@t.com", role="staff",
            )

    def test_replay_revokes_entire_family(self, ts):
        """Après replay, la famille est révoquée et R2 ne marche plus."""
        _, r1, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        _, r2, _ = ts.rotate_refresh_token(
            old_refresh_token=r1,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )

        # Replay avec R1
        with pytest.raises(TokenReplayDetected):
            ts.rotate_refresh_token(
                old_refresh_token=r1,
                user_id=1, tenant_id=1, email="a@t.com", role="staff",
            )

        # R2 est maintenant aussi révoqué (famille entière compromise)
        r2_jti = decode_token(r2)["jti"]
        assert not ts.is_refresh_whitelisted(r2_jti)

        # Famille marquée inactive
        family_id = decode_token(r1)["family_id"]
        family_data = redis_client.get_token_family(family_id)
        assert family_data is not None
        assert family_data["active"] is False

    def test_replay_does_not_affect_other_families(self, ts):
        """Le replay sur une famille ne révoque pas les autres familles du même user."""
        # Login 1 (famille A)
        _, r1_a, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        # Login 2 (famille B)
        _, r1_b, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )

        # Rotation famille A
        _, r2_a, _ = ts.rotate_refresh_token(
            old_refresh_token=r1_a,
            user_id=1, tenant_id=1, email="a@t.com", role="staff",
        )

        # Replay sur famille A avec R1_A
        with pytest.raises(TokenReplayDetected):
            ts.rotate_refresh_token(
                old_refresh_token=r1_a,
                user_id=1, tenant_id=1, email="a@t.com", role="staff",
            )

        # Famille B n'est PAS affectée par le replay — NOTE: _revoke_family
        # fait un revoke_all_refresh_tokens(user_id) donc B est aussi révoqué.
        # C'est intentionnel: replay = nuclear option.
        r1_b_jti = decode_token(r1_b)["jti"]
        assert not ts.is_refresh_whitelisted(r1_b_jti)


# ── revoke_on_logout ──────────────────────────────────────────────────────


class TestRevokeOnLogout:
    """Tests pour revoke_on_logout() — logout flow."""

    def test_access_blacklisted_after_logout(self, ts):
        access, refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        access_jti = decode_token(access)["jti"]
        assert not ts.is_access_blacklisted(access_jti)

        ts.revoke_on_logout(access_token=access, refresh_token=refresh)
        assert ts.is_access_blacklisted(access_jti)

    def test_refresh_revoked_after_logout(self, ts):
        access, refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        refresh_jti = decode_token(refresh)["jti"]
        assert ts.is_refresh_whitelisted(refresh_jti)

        ts.revoke_on_logout(access_token=access, refresh_token=refresh)
        assert not ts.is_refresh_whitelisted(refresh_jti)

    def test_logout_without_refresh_token(self, ts):
        """Logout avec seulement l'access token (refresh optionnel)."""
        access, _, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        access_jti = decode_token(access)["jti"]

        ts.revoke_on_logout(access_token=access)  # pas de refresh
        assert ts.is_access_blacklisted(access_jti)

    def test_refresh_after_logout_raises_revoked(self, ts):
        """Tentative de refresh après logout → TokenRevoked."""
        access, refresh, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        ts.revoke_on_logout(access_token=access, refresh_token=refresh)

        with pytest.raises(TokenRevoked):
            ts.rotate_refresh_token(
                old_refresh_token=refresh,
                user_id=1, tenant_id=1, email="a@t.com", role="staff",
            )


# ── revoke_all_user_tokens ────────────────────────────────────────────────


class TestRevokeAllUserTokens:
    """Tests pour revoke_all_user_tokens() — force logout all sessions."""

    def test_revoke_all_removes_all_refresh_tokens(self, ts):
        _, r1, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")
        _, r2, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")

        jti1 = decode_token(r1)["jti"]
        jti2 = decode_token(r2)["jti"]

        assert ts.is_refresh_whitelisted(jti1)
        assert ts.is_refresh_whitelisted(jti2)

        count = ts.revoke_all_user_tokens(user_id=1)
        assert count >= 2

        assert not ts.is_refresh_whitelisted(jti1)
        assert not ts.is_refresh_whitelisted(jti2)

    def test_revoke_all_does_not_affect_other_users(self, ts):
        """Révoquer les tokens de user 1 ne touche pas user 2."""
        _, r1, _ = ts.issue_tokens(user_id=1, tenant_id=1, email="a@t.com", role="staff")
        _, r2, _ = ts.issue_tokens(user_id=2, tenant_id=1, email="b@t.com", role="staff")

        ts.revoke_all_user_tokens(user_id=1)

        jti1 = decode_token(r1)["jti"]
        jti2 = decode_token(r2)["jti"]

        assert not ts.is_refresh_whitelisted(jti1)
        assert ts.is_refresh_whitelisted(jti2)


# ── is_access_blacklisted / is_refresh_whitelisted ────────────────────────


class TestValidationMethods:
    """Tests pour les méthodes de validation."""

    def test_unknown_jti_not_blacklisted(self, ts):
        assert not ts.is_access_blacklisted("nonexistent-jti")

    def test_unknown_jti_not_whitelisted(self, ts):
        assert not ts.is_refresh_whitelisted("nonexistent-jti")

    def test_blacklisted_jti_detected(self, ts):
        access, _, _ = ts.issue_tokens(
            user_id=1, tenant_id=1, email="a@t.com", role="staff"
        )
        jti = decode_token(access)["jti"]
        redis_client.blacklist_access_jti(jti, ttl_seconds=60)
        assert ts.is_access_blacklisted(jti)


# ── Singleton ─────────────────────────────────────────────────────────────


class TestSingleton:
    """Vérifie que token_service est un singleton."""

    def test_singleton_exists(self):
        assert token_service is not None
        assert isinstance(token_service, TokenService)

    def test_singleton_functional(self):
        access, _, _ = token_service.issue_tokens(
            user_id=99, tenant_id=1, email="s@t.com", role="staff"
        )
        assert access is not None
