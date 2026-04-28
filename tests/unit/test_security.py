"""Tests unitaires pour app/core/security.py — JWT RS256, hashing, validation.

Couvre :
    - create_access_token / create_refresh_token (RS256, claims v3)
    - decode_token (signature, expiry, HS256 rejet)
    - _prepare_password (SHA-256 + HMAC-SHA256 pepper)
    - get_password_hash / verify_password (Argon2id + bcrypt legacy + fallback)
    - DUMMY_HASH, needs_rehash, validate_password_strength
"""
import hashlib
import hmac
import time
import pytest
import bcrypt
import jwt as pyjwt
from datetime import timedelta
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    needs_rehash,
    get_password_hash,
    DUMMY_HASH,
    validate_password_strength,
    _is_bcrypt_hash,
    _is_argon2_hash,
    _prepare_password,
)
from app.core.exceptions import TokenExpired, TokenInvalid
from app.core.config import settings
from app.constants import TokenType


# ── Fixtures RSA ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_test_keys():
    """Paire RSA 2048 temporaire (générée une seule fois par module)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def mock_jwt_keys(rsa_test_keys):
    """Patch les clés JWT pour tous les tests — évite la dépendance aux fichiers PEM."""
    private_key, public_key = rsa_test_keys
    with patch("app.core.security._get_private_key", return_value=private_key), \
         patch("app.core.security._get_public_key", return_value=public_key):
        yield private_key, public_key


# ── JWT Access Token ──────────────────────────────────────────────────────

class TestCreateAccessToken:

    def test_returns_valid_jwt_string(self):
        token = create_access_token({"sub": "42"})
        assert isinstance(token, str)
        assert token.count(".") == 2  # header.payload.signature

    def test_claims_v3_present(self):
        token = create_access_token({
            "sub": "42", "tid": "1", "did": "dev1", "sid": "sess1", "scopes": ["users:read"]
        })
        payload = decode_token(token)
        # Claims applicatifs v3
        assert payload["sub"] == "42"
        assert payload["tid"] == "1"
        assert payload["did"] == "dev1"
        assert payload["sid"] == "sess1"
        assert payload["scopes"] == ["users:read"]
        # Claims standards
        assert payload["iss"] == settings.JWT_ISSUER
        assert payload["type"] == TokenType.ACCESS
        for claim in ("jti", "exp", "nbf", "iat"):
            assert claim in payload

    def test_sub_coerced_to_string(self):
        token = create_access_token({"sub": 99})
        payload = decode_token(token)
        assert payload["sub"] == "99"
        assert isinstance(payload["sub"], str)

    def test_tenant_id_coerced_to_string(self):
        token = create_access_token({"sub": "1", "tenant_id": 42})
        payload = decode_token(token)
        assert payload["tenant_id"] == "42"

    def test_unique_jti_per_call(self):
        t1 = create_access_token({"sub": "1"})
        t2 = create_access_token({"sub": "1"})
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]

    def test_custom_expiry(self):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(hours=1))
        payload = decode_token(token)
        assert 3550 <= (payload["exp"] - payload["iat"]) <= 3660

    def test_default_expiry_15min(self):
        before = int(time.time())
        token = create_access_token({"sub": "1"})
        after = int(time.time())
        exp = decode_token(token)["exp"]
        expected = settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS
        assert before + expected - 5 <= exp <= after + expected + 5

    def test_algorithm_rs256(self):
        token = create_access_token({"sub": "1"})
        assert pyjwt.get_unverified_header(token)["alg"] == "RS256"


# ── JWT Refresh Token ─────────────────────────────────────────────────────

class TestCreateRefreshToken:

    def test_type_is_refresh(self):
        token = create_refresh_token({"sub": "1"})
        assert decode_token(token)["type"] == TokenType.REFRESH

    def test_no_audience_claim(self):
        token = create_refresh_token({"sub": "1"})
        payload = decode_token(token)
        assert "aud" not in payload

    def test_v3_claims_preserved(self):
        token = create_refresh_token({
            "sub": "42", "tid": "7", "did": "d1", "sid": "s1", "fid": "fam-123"
        })
        payload = decode_token(token)
        assert payload["fid"] == "fam-123"
        assert payload["did"] == "d1"
        assert payload["sid"] == "s1"
        assert payload["tid"] == "7"

    def test_default_expiry_7days(self):
        before = int(time.time())
        token = create_refresh_token({"sub": "1"})
        after = int(time.time())
        exp = decode_token(token)["exp"]
        expected = settings.JWT_REFRESH_TOKEN_EXPIRE_SECONDS
        assert before + expected - 5 <= exp <= after + expected + 5


# ── decode_token ──────────────────────────────────────────────────────────

class TestDecodeToken:

    def test_expired_raises_token_expired(self):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-100))
        with pytest.raises(TokenExpired):
            decode_token(token)

    def test_invalid_signature_raises_token_invalid(self):
        """Token signé avec une autre clé RSA → signature invalide."""
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time.time())
        fake_token = pyjwt.encode(
            {"sub": "1", "iss": settings.JWT_ISSUER, "jti": "jti1",
             "exp": now + 900, "iat": now, "nbf": now},
            other_key,
            algorithm="RS256",
        )
        with pytest.raises(TokenInvalid):
            decode_token(fake_token)

    def test_hs256_token_rejected(self):
        """Un token HS256 doit être rejeté — algo incorrect."""
        hs256_token = pyjwt.encode(
            {"sub": "1", "exp": int(time.time()) + 900},
            "secret",
            algorithm="HS256",
        )
        with pytest.raises(TokenInvalid):
            decode_token(hs256_token)

    def test_tampered_payload_raises_token_invalid(self):
        token = create_access_token({"sub": "1"})
        parts = token.split(".")
        tampered = ".".join([parts[0], parts[1] + "TAMPERED", parts[2]])
        with pytest.raises(TokenInvalid):
            decode_token(tampered)

    def test_requires_sub_claim(self, mock_jwt_keys):
        """Token sans sub → TokenInvalid (require: ['sub', ...])."""
        private_key, _ = mock_jwt_keys
        now = int(time.time())
        bad_token = pyjwt.encode(
            {"iss": settings.JWT_ISSUER, "jti": "jti1",
             "exp": now + 900, "iat": now, "nbf": now},
            private_key,
            algorithm="RS256",
        )
        with pytest.raises(TokenInvalid):
            decode_token(bad_token)

    def test_requires_jti_claim(self, mock_jwt_keys):
        """Token sans jti → TokenInvalid."""
        private_key, _ = mock_jwt_keys
        now = int(time.time())
        bad_token = pyjwt.encode(
            {"sub": "1", "iss": settings.JWT_ISSUER,
             "exp": now + 900, "iat": now, "nbf": now},
            private_key,
            algorithm="RS256",
        )
        with pytest.raises(TokenInvalid):
            decode_token(bad_token)

    def test_round_trip_preserves_custom_claims(self):
        data = {"sub": "7", "tid": "3", "did": "dev7", "scopes": ["a:b"]}
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload["tid"] == "3"
        assert payload["did"] == "dev7"
        assert payload["scopes"] == ["a:b"]


# ── _prepare_password ─────────────────────────────────────────────────────

class TestPreparePassword:

    def test_deterministic(self):
        assert _prepare_password("my_password") == _prepare_password("my_password")

    def test_different_inputs_different_outputs(self):
        assert _prepare_password("password1") != _prepare_password("password2")

    def test_returns_32_bytes(self):
        result = _prepare_password("test")
        assert isinstance(result, bytes)
        assert len(result) == 32  # SHA-256 output

    def test_uses_pepper_correctly(self):
        """Vérifie manuellement : SHA-256(pass) → HMAC-SHA256(pepper, sha256)."""
        password = "test_pass"
        sha = hashlib.sha256(password.encode("utf-8")).digest()
        pepper = settings.PASSWORD_PEPPER.encode("utf-8")
        expected = hmac.new(pepper, sha, hashlib.sha256).digest()
        assert _prepare_password(password) == expected


# ── get_password_hash / verify_password ──────────────────────────────────

class TestGetPasswordHash:

    def test_returns_argon2id_hash(self):
        h = get_password_hash("MyPassword123!")
        assert _is_argon2_hash(h)
        assert not _is_bcrypt_hash(h)

    def test_random_salt_each_call(self):
        """Argon2id génère un salt aléatoire → hashes différents."""
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2


class TestVerifyPassword:

    def test_correct_password_argon2(self):
        h = get_password_hash("correct_pass")
        assert verify_password("correct_pass", h) is True

    def test_wrong_password_argon2(self):
        h = get_password_hash("correct_pass")
        assert verify_password("wrong_pass", h) is False

    def test_correct_password_bcrypt_with_pepper(self):
        """Bcrypt pepper v3 : hash du mot de passe préparé (SHA-256 + HMAC)."""
        import bcrypt as bcrypt_lib
        prepared = _prepare_password("my_password")
        h = bcrypt_lib.hashpw(prepared, bcrypt_lib.gensalt(rounds=4)).decode("utf-8")
        assert verify_password("my_password", h) is True

    def test_bcrypt_legacy_without_pepper_fallback(self):
        """Bcrypt legacy (hash du mot de passe brut) → fallback sans pepper."""
        h = bcrypt.hashpw(b"my_password", bcrypt.gensalt(rounds=4)).decode("utf-8")
        assert verify_password("my_password", h) is True

    def test_argon2_legacy_without_pepper_fallback(self):
        """Hash Argon2id créé sans pepper (pré-v3) → fallback sans pepper."""
        import argon2
        hasher = argon2.PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
        h = hasher.hash("my_password")  # hash sans pepper
        assert verify_password("my_password", h) is True

    def test_unknown_hash_format_returns_false(self):
        assert verify_password("any_password", "not_a_valid_hash") is False

    def test_dummy_hash_verifiable_with_pepper(self):
        """DUMMY_HASH (généré avec pepper au démarrage) est vérifiable."""
        assert verify_password("__dummy_startup_password__", DUMMY_HASH) is True

    def test_wrong_password_bcrypt(self):
        h = bcrypt.hashpw(b"correct", bcrypt.gensalt(rounds=4)).decode("utf-8")
        assert verify_password("wrong", h) is False


# ── needs_rehash ──────────────────────────────────────────────────────────

class TestNeedsRehash:

    def test_current_argon2_no_rehash(self):
        h = get_password_hash("test_pass")
        assert needs_rehash(h) is False

    def test_bcrypt_needs_rehash(self):
        h = bcrypt.hashpw(b"test", bcrypt.gensalt(rounds=4)).decode("utf-8")
        assert needs_rehash(h) is True

    def test_unknown_format_needs_rehash(self):
        assert needs_rehash("totally_unknown_hash_format") is True


# ── Hash format detection ─────────────────────────────────────────────────

class TestHashDetection:

    def test_argon2id_detected(self):
        h = get_password_hash("test")
        assert _is_argon2_hash(h) is True
        assert _is_bcrypt_hash(h) is False

    def test_bcrypt_detected(self):
        h = bcrypt.hashpw(b"test", bcrypt.gensalt(rounds=4)).decode("utf-8")
        assert _is_bcrypt_hash(h) is True
        assert _is_argon2_hash(h) is False

    def test_random_string_neither(self):
        assert _is_bcrypt_hash("random_string") is False
        assert _is_argon2_hash("random_string") is False


# ── validate_password_strength ────────────────────────────────────────────

class TestValidatePasswordStrength:

    def test_strong_password_valid(self):
        ok, msg = validate_password_strength("MyStr0ng!Pass")
        assert ok is True
        assert msg is None

    def test_too_short(self):
        ok, msg = validate_password_strength("Ab1!")
        assert ok is False
        assert msg is not None

    def test_no_uppercase(self):
        ok, msg = validate_password_strength("mystr0ng!pass")
        assert ok is False

    def test_no_digit(self):
        ok, msg = validate_password_strength("MyStrong!Pass")
        assert ok is False

    def test_no_special_char(self):
        ok, msg = validate_password_strength("MyStr0ngPass")
        assert ok is False
