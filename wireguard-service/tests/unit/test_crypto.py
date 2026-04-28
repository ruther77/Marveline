"""Tests unitaires pour app.core.crypto — keygen Curve25519 + AES-256-GCM."""

import base64
import re
from pathlib import Path

import pytest

# Analyse du code source (pas d'import direct, SQLAlchemy 2.0 potentiellement absent)
PROJECT_ROOT = Path(__file__).parent.parent.parent
CRYPTO_FILE = PROJECT_ROOT / "app" / "core" / "crypto.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels (analyse source)
# ---------------------------------------------------------------------------

class TestCryptoSourceStructure:
    """Vérifie la structure du module crypto."""

    def test_generate_keypair_exists(self):
        source = _read_source(CRYPTO_FILE)
        assert "def generate_keypair()" in source

    def test_encrypt_value_exists(self):
        source = _read_source(CRYPTO_FILE)
        assert "def encrypt_value(" in source

    def test_decrypt_value_exists(self):
        source = _read_source(CRYPTO_FILE)
        assert "def decrypt_value(" in source

    def test_generate_preshared_key_exists(self):
        source = _read_source(CRYPTO_FILE)
        assert "def generate_preshared_key()" in source

    def test_derive_public_key_exists(self):
        source = _read_source(CRYPTO_FILE)
        assert "def derive_public_key(" in source

    def test_uses_x25519(self):
        source = _read_source(CRYPTO_FILE)
        assert "X25519PrivateKey" in source

    def test_uses_aesgcm(self):
        source = _read_source(CRYPTO_FILE)
        assert "AESGCM" in source

    def test_nonce_is_12_bytes(self):
        source = _read_source(CRYPTO_FILE)
        assert "os.urandom(12)" in source


# ---------------------------------------------------------------------------
# Tests fonctionnels (nécessitent cryptography installé)
# ---------------------------------------------------------------------------

try:
    from app.core.crypto import (
        decrypt_value,
        derive_public_key,
        encrypt_value,
        generate_keypair,
        generate_preshared_key,
    )
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestGenerateKeypair:
    """Tests de génération de paires de clés Curve25519."""

    def test_returns_tuple_of_two_strings(self):
        private, public = generate_keypair()
        assert isinstance(private, str)
        assert isinstance(public, str)

    def test_keys_are_valid_base64(self):
        private, public = generate_keypair()
        private_bytes = base64.b64decode(private)
        public_bytes = base64.b64decode(public)
        assert len(private_bytes) == 32
        assert len(public_bytes) == 32

    def test_keypairs_are_unique(self):
        pair1 = generate_keypair()
        pair2 = generate_keypair()
        assert pair1[0] != pair2[0]
        assert pair1[1] != pair2[1]

    def test_derive_public_from_private(self):
        private, public = generate_keypair()
        derived = derive_public_key(private)
        assert derived == public


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestPresharedKey:
    """Tests de génération de clé pré-partagée."""

    def test_returns_base64_string(self):
        key = generate_preshared_key()
        decoded = base64.b64decode(key)
        assert len(decoded) == 32

    def test_keys_are_unique(self):
        k1 = generate_preshared_key()
        k2 = generate_preshared_key()
        assert k1 != k2


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestEncryptDecrypt:
    """Tests de chiffrement/déchiffrement AES-256-GCM."""

    VALID_KEY = "a" * 32  # Exactement 32 caractères

    def test_roundtrip(self):
        plaintext = "ma_cle_privee_super_secrete"
        encrypted = encrypt_value(plaintext, self.VALID_KEY)
        decrypted = decrypt_value(encrypted, self.VALID_KEY)
        assert decrypted == plaintext

    def test_encrypted_is_base64(self):
        encrypted = encrypt_value("test", self.VALID_KEY)
        raw = base64.b64decode(encrypted)
        # nonce (12) + ciphertext (>= 4) + tag (16)
        assert len(raw) >= 32

    def test_different_encryptions_differ(self):
        """Deux chiffrements du même texte donnent des résultats différents (nonce aléatoire)."""
        e1 = encrypt_value("same_text", self.VALID_KEY)
        e2 = encrypt_value("same_text", self.VALID_KEY)
        assert e1 != e2

    def test_wrong_key_fails(self):
        encrypted = encrypt_value("secret", self.VALID_KEY)
        wrong_key = "b" * 32
        with pytest.raises(Exception):  # InvalidTag
            decrypt_value(encrypted, wrong_key)

    def test_short_key_raises(self):
        with pytest.raises(ValueError, match="trop courte"):
            encrypt_value("test", "short")

    def test_empty_plaintext(self):
        encrypted = encrypt_value("", self.VALID_KEY)
        decrypted = decrypt_value(encrypted, self.VALID_KEY)
        assert decrypted == ""

    def test_unicode_plaintext(self):
        plaintext = "clé privée avec accents éàü"
        encrypted = encrypt_value(plaintext, self.VALID_KEY)
        decrypted = decrypt_value(encrypted, self.VALID_KEY)
        assert decrypted == plaintext
