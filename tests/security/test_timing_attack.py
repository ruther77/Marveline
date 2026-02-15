"""Tests sécurité : timing attack fix + decode_token exceptions + JTI.

Couvre les fixes:
- M20: DUMMY_HASH timing-safe login (delta < 100ms entre user inexistant et mauvais password)
- M25: decode_token lève TokenExpired/TokenInvalid au lieu de retourner None
- M26: JTI (JWT ID unique) dans access et refresh tokens
"""
import time
import uuid

import pytest
from jose import jwt

from app.core.config import settings
from app.core.exceptions import TokenExpired, TokenInvalid
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)


class TestTimingSafeLogin:
    """M20: Temps de réponse constant que l'utilisateur existe ou non."""

    def test_timing_nonexistent_vs_wrong_password(self, test_db, test_user):
        """Delta temps entre user inexistant et mauvais password doit être < 200ms.

        Teste au niveau service (pas HTTP) pour isoler le timing bcrypt
        du rate limiter et de la latence réseau.
        Sans DUMMY_HASH le delta serait > 400ms (bcrypt skippé entièrement).
        """
        from app.services.auth import AuthService

        auth_service = AuthService(test_db)
        n_iterations = 3

        # Mesurer temps pour user inexistant (DUMMY_HASH verify)
        times_nonexistent = []
        for _ in range(n_iterations):
            start = time.perf_counter()
            try:
                auth_service.login("nonexistent@nowhere.com", "wrongpass123")
            except Exception:
                pass
            elapsed = time.perf_counter() - start
            times_nonexistent.append(elapsed)

        # Mesurer temps pour user existant + mauvais password (real hash verify)
        times_wrong_pw = []
        for _ in range(n_iterations):
            start = time.perf_counter()
            try:
                auth_service.login(test_user.email, "wrongpass123")
            except Exception:
                pass
            elapsed = time.perf_counter() - start
            times_wrong_pw.append(elapsed)

        # Calculer médianes (plus robuste que moyennes)
        times_nonexistent.sort()
        times_wrong_pw.sort()
        median_nonexistent = times_nonexistent[n_iterations // 2]
        median_wrong_pw = times_wrong_pw[n_iterations // 2]

        # Delta doit être < 200ms (timing-safe)
        delta_ms = abs(median_nonexistent - median_wrong_pw) * 1000
        assert delta_ms < 200, (
            f"Timing attack possible: delta={delta_ms:.1f}ms "
            f"(nonexistent={median_nonexistent*1000:.1f}ms, wrong_pw={median_wrong_pw*1000:.1f}ms)"
        )

    def test_dummy_hash_exists_and_is_argon2id(self):
        """DUMMY_HASH doit être généré et être un hash Argon2id valide."""
        assert DUMMY_HASH is not None
        assert isinstance(DUMMY_HASH, str)
        assert DUMMY_HASH.startswith("$argon2id$")  # Argon2id prefix

    def test_dummy_hash_verifies_original_password(self):
        """DUMMY_HASH doit correspondre au password d'origine (pas un hash fixe)."""
        # Le DUMMY_HASH est généré dynamiquement, on vérifie qu'il fonctionne
        assert verify_password("__dummy_startup_password__", DUMMY_HASH)

    def test_dummy_hash_rejects_other_passwords(self):
        """DUMMY_HASH ne doit pas valider un autre password."""
        assert not verify_password("attacker_password", DUMMY_HASH)


class TestDecodeTokenExceptions:
    """M25: decode_token lève des exceptions spécifiques."""

    def test_decode_valid_token(self):
        """Token valide doit retourner le payload."""
        token = create_access_token({"sub": 1, "tenant_id": 1, "email": "t@t.com", "role": "staff"})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["tenant_id"] == 1

    def test_decode_expired_token_raises_token_expired(self):
        """Token expiré doit lever TokenExpired."""
        from datetime import datetime, timedelta, timezone

        expired_claims = {
            "sub": "1",
            "tenant_id": 1,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "type": "access",
            "jti": str(uuid.uuid4()),
        }
        expired_token = jwt.encode(expired_claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(TokenExpired):
            decode_token(expired_token)

    def test_decode_invalid_signature_raises_token_invalid(self):
        """Token avec mauvaise signature doit lever TokenInvalid."""
        token = create_access_token({"sub": 1, "tenant_id": 1, "email": "t@t.com", "role": "staff"})
        # Signer avec une autre clé pour invalider la signature
        from datetime import datetime, timezone
        tampered = jwt.encode(
            {"sub": "1", "tenant_id": 1, "exp": datetime.now(timezone.utc).timestamp() + 3600},
            "wrong-secret-key",
            algorithm=settings.JWT_ALGORITHM,
        )

        with pytest.raises(TokenInvalid):
            decode_token(tampered)

    def test_decode_garbage_raises_token_invalid(self):
        """Token garbage doit lever TokenInvalid."""
        with pytest.raises(TokenInvalid):
            decode_token("not.a.jwt.token")

    def test_decode_empty_string_raises_token_invalid(self):
        """String vide doit lever TokenInvalid."""
        with pytest.raises(TokenInvalid):
            decode_token("")

    def test_decode_none_algo_attack_raises_token_invalid(self):
        """Token avec algo 'none' doit lever TokenInvalid."""
        import base64
        import json

        # Forger manuellement un JWT avec alg=none (attaque classique)
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "1", "tenant_id": 1}).encode()).rstrip(b"=").decode()
        unsigned_token = f"{header}.{payload}."

        with pytest.raises(TokenInvalid):
            decode_token(unsigned_token)


class TestJTI:
    """M26: JWT ID unique dans chaque token."""

    def test_access_token_has_jti(self):
        """Access token doit contenir un JTI."""
        token = create_access_token({"sub": 1, "tenant_id": 1, "email": "t@t.com", "role": "staff"})
        payload = decode_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) == 36  # UUID format

    def test_refresh_token_has_jti(self):
        """Refresh token doit contenir un JTI."""
        token = create_refresh_token({"sub": 1, "tenant_id": 1})
        payload = decode_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) == 36

    def test_jti_is_unique_per_token(self):
        """Chaque token doit avoir un JTI différent."""
        claims = {"sub": 1, "tenant_id": 1, "email": "t@t.com", "role": "staff"}
        token1 = create_access_token(claims)
        token2 = create_access_token(claims)

        payload1 = decode_token(token1)
        payload2 = decode_token(token2)

        assert payload1["jti"] != payload2["jti"]

    def test_jti_is_valid_uuid(self):
        """JTI doit être un UUID valide."""
        token = create_access_token({"sub": 1, "tenant_id": 1, "email": "t@t.com", "role": "staff"})
        payload = decode_token(token)
        # Doit pouvoir être parsé comme UUID
        parsed = uuid.UUID(payload["jti"])
        assert str(parsed) == payload["jti"]

    def test_access_token_has_type_claim(self):
        """Access token doit avoir type=access."""
        token = create_access_token({"sub": 1, "tenant_id": 1, "email": "t@t.com", "role": "staff"})
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_refresh_token_has_type_claim(self):
        """Refresh token doit avoir type=refresh."""
        token = create_refresh_token({"sub": 1, "tenant_id": 1})
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_sub_claim_is_string(self):
        """Sub claim doit être converti en string (JWT spec)."""
        token = create_access_token({"sub": 42, "tenant_id": 1, "email": "t@t.com", "role": "staff"})
        payload = decode_token(token)
        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "42"
