"""Tests unitaires pour app/core/security.py — JWT, hashing, password validation.

Couvre : create_access_token, create_refresh_token, decode_token,
verify_password, needs_rehash, get_password_hash, DUMMY_HASH,
validate_password_strength, _is_bcrypt_hash, _is_argon2_hash.
"""
import time
import pytest
import bcrypt
from datetime import timedelta
from jose import jwt as jose_jwt

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
)
from app.core.exceptions import TokenExpired, TokenInvalid
from app.core.config import settings
from app.constants import TokenType


# ── JWT Access Token ────────────────────────────────────────────────────


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token({"sub": 1})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_contains_required_claims(self):
        token = create_access_token({"sub": 42, "tenant_id": 1})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "42"  # sub converted to string
        assert payload["tenant_id"] == 1
        assert payload["type"] == TokenType.ACCESS
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_sub_converted_to_string(self):
        token = create_access_token({"sub": 123})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert isinstance(payload["sub"], str)
        assert payload["sub"] == "123"

    def test_sub_string_preserved(self):
        token = create_access_token({"sub": "456"})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "456"

    def test_jti_is_unique(self):
        t1 = create_access_token({"sub": 1})
        t2 = create_access_token({"sub": 1})
        p1 = jose_jwt.decode(t1, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        p2 = jose_jwt.decode(t2, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        assert p1["jti"] != p2["jti"]

    def test_custom_expires_delta(self):
        token = create_access_token({"sub": 1}, expires_delta=timedelta(minutes=5))
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        # exp should be ~5 minutes from iat
        assert payload["exp"] - payload["iat"] == pytest.approx(300, abs=5)

    def test_default_expiry(self):
        token = create_access_token({"sub": 1})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        expected = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert payload["exp"] - payload["iat"] == pytest.approx(expected, abs=5)

    def test_data_not_mutated(self):
        data = {"sub": 1, "extra": "value"}
        original = data.copy()
        create_access_token(data)
        assert data == original


# ── JWT Refresh Token ───────────────────────────────────────────────────


class TestCreateRefreshToken:
    def test_returns_string(self):
        token = create_refresh_token({"sub": 1})
        assert isinstance(token, str)

    def test_contains_refresh_type(self):
        token = create_refresh_token({"sub": 1})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["type"] == TokenType.REFRESH

    def test_has_jti(self):
        token = create_refresh_token({"sub": 1})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert "jti" in payload

    def test_sub_converted_to_string(self):
        token = create_refresh_token({"sub": 99})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        assert payload["sub"] == "99"

    def test_expiry_days(self):
        token = create_refresh_token({"sub": 1})
        payload = jose_jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        expected = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
        assert payload["exp"] - payload["iat"] == pytest.approx(expected, abs=5)


# ── Decode Token ────────────────────────────────────────────────────────


class TestDecodeToken:
    def test_decode_valid_access_token(self):
        token = create_access_token({"sub": 1, "tenant_id": 1})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["tenant_id"] == 1
        assert payload["type"] == TokenType.ACCESS

    def test_decode_valid_refresh_token(self):
        token = create_refresh_token({"sub": 1})
        payload = decode_token(token)
        assert payload["type"] == TokenType.REFRESH

    def test_expired_token_raises_token_expired(self):
        token = create_access_token({"sub": 1}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenExpired):
            decode_token(token)

    def test_invalid_signature_raises_token_invalid(self):
        token = jose_jwt.encode(
            {"sub": "1", "exp": 9999999999},
            "wrong_secret",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(TokenInvalid):
            decode_token(token)

    def test_malformed_token_raises_token_invalid(self):
        with pytest.raises(TokenInvalid):
            decode_token("not.a.valid.token")

    def test_empty_token_raises_token_invalid(self):
        with pytest.raises(TokenInvalid):
            decode_token("")

    def test_wrong_algorithm_raises_token_invalid(self):
        token = jose_jwt.encode(
            {"sub": "1", "exp": 9999999999},
            settings.JWT_SECRET,
            algorithm="HS384",
        )
        with pytest.raises(TokenInvalid):
            decode_token(token)


# ── Hash Detection ──────────────────────────────────────────────────────


class TestHashDetection:
    def test_is_bcrypt_hash(self):
        bcrypt_hash = bcrypt.hashpw(b"test", bcrypt.gensalt()).decode("utf-8")
        assert _is_bcrypt_hash(bcrypt_hash) is True

    def test_is_not_bcrypt_hash(self):
        assert _is_bcrypt_hash("$argon2id$v=19$m=65536") is False
        assert _is_bcrypt_hash("plaintext") is False

    def test_is_argon2_hash(self):
        h = get_password_hash("testpassword")
        assert _is_argon2_hash(h) is True

    def test_is_not_argon2_hash(self):
        assert _is_argon2_hash("$2b$12$somebcrypthash") is False
        assert _is_argon2_hash("plaintext") is False


# ── Password Hashing & Verification ────────────────────────────────────


class TestPasswordHashing:
    def test_get_password_hash_returns_argon2id(self):
        h = get_password_hash("MyPassword123!")
        assert h.startswith("$argon2id$")

    def test_hash_different_each_time(self):
        h1 = get_password_hash("SamePassword!")
        h2 = get_password_hash("SamePassword!")
        assert h1 != h2  # different salts

    def test_verify_argon2id_correct(self):
        h = get_password_hash("Correct!123")
        assert verify_password("Correct!123", h) is True

    def test_verify_argon2id_incorrect(self):
        h = get_password_hash("Correct!123")
        assert verify_password("Wrong!123", h) is False

    def test_verify_bcrypt_correct(self):
        bcrypt_hash = bcrypt.hashpw(
            "Legacy!123".encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        assert verify_password("Legacy!123", bcrypt_hash) is True

    def test_verify_bcrypt_incorrect(self):
        bcrypt_hash = bcrypt.hashpw(
            "Legacy!123".encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        assert verify_password("Wrong!123", bcrypt_hash) is False

    def test_verify_unknown_hash_returns_false(self):
        assert verify_password("password", "plaintext_not_a_hash") is False

    def test_verify_empty_password_returns_false(self):
        h = get_password_hash("NotEmpty!")
        assert verify_password("", h) is False


# ── Needs Rehash ────────────────────────────────────────────────────────


class TestNeedsRehash:
    def test_bcrypt_needs_rehash(self):
        bcrypt_hash = bcrypt.hashpw(
            "test".encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        assert needs_rehash(bcrypt_hash) is True

    def test_current_argon2id_no_rehash(self):
        h = get_password_hash("CurrentParams!")
        assert needs_rehash(h) is False

    def test_unknown_hash_needs_rehash(self):
        assert needs_rehash("unknown_format_hash") is True


# ── DUMMY_HASH ──────────────────────────────────────────────────────────


class TestDummyHash:
    def test_dummy_hash_is_argon2id(self):
        assert DUMMY_HASH.startswith("$argon2id$")

    def test_dummy_hash_is_not_empty(self):
        assert len(DUMMY_HASH) > 20

    def test_dummy_hash_verification_returns_false_for_any_password(self):
        assert verify_password("random_password_attempt", DUMMY_HASH) is False


# ── Password Strength Validation ────────────────────────────────────────


class TestValidatePasswordStrength:
    def test_valid_password(self):
        is_valid, error = validate_password_strength("Str0ng!Pass")
        assert is_valid is True
        assert error is None

    def test_too_short(self):
        is_valid, error = validate_password_strength("Sh0!")
        assert is_valid is False
        assert error is not None

    def test_common_password_rejected(self):
        is_valid, error = validate_password_strength("password123")
        assert is_valid is False

    def test_admin_role_requires_longer(self):
        # 8 chars valid for normal user, not for admin (12 min)
        password = "Xk7m!pQz"  # 8 chars, no sequential chars
        normal_valid, _ = validate_password_strength(password)
        admin_valid, _ = validate_password_strength(password, role="admin")
        # normal should pass (8 >= 8), admin should fail (8 < 12)
        assert normal_valid is True
        assert admin_valid is False

    def test_no_digits_rejected(self):
        is_valid, error = validate_password_strength("NoDigitsHere!")
        assert is_valid is False

    def test_no_special_char_rejected(self):
        is_valid, error = validate_password_strength("NoSpecial123")
        assert is_valid is False
