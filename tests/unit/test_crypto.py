"""Tests unitaires pour app.core.crypto — AES-256-GCM encrypt/decrypt.

Vérifie :
    - Roundtrip encrypt → decrypt
    - Plaintext vide = erreur
    - Données corrompues = erreur
    - Données trop courtes = erreur
    - Dérivation de clé déterministe
    - Nonce unique à chaque appel (pas de réutilisation)
    - Ciphertext ≠ plaintext (pas de fuite en clair)
"""
import pytest
from unittest.mock import patch

from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret, _derive_key


class TestDeriveKey:
    """Tests pour la dérivation de clé AES-256."""

    def test_derive_key_returns_32_bytes(self):
        """La clé dérivée fait exactement 32 bytes (AES-256)."""
        key = _derive_key()
        assert len(key) == 32

    def test_derive_key_deterministic(self):
        """Même ENCRYPTION_KEY → même clé dérivée."""
        key1 = _derive_key()
        key2 = _derive_key()
        assert key1 == key2

    def test_derive_key_changes_with_different_config(self):
        """Clé différente si ENCRYPTION_KEY change."""
        key1 = _derive_key()
        with patch("app.core.crypto.settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = "totally_different_key_for_testing"
            key2 = _derive_key()
        assert key1 != key2


class TestEncryptTotpSecret:
    """Tests pour le chiffrement AES-256-GCM."""

    def test_encrypt_returns_bytes(self):
        """Le résultat est de type bytes."""
        result = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        assert isinstance(result, bytes)

    def test_encrypt_minimum_length(self):
        """Le résultat fait au moins 28 bytes (12 nonce + 16 tag)."""
        result = encrypt_totp_secret("A")
        assert len(result) >= 28

    def test_encrypt_empty_plaintext_raises(self):
        """Plaintext vide → ValueError."""
        with pytest.raises(ValueError, match="Cannot encrypt empty plaintext"):
            encrypt_totp_secret("")

    def test_encrypt_none_plaintext_raises(self):
        """Plaintext None → ValueError."""
        with pytest.raises(ValueError):
            encrypt_totp_secret(None)

    def test_encrypt_produces_different_ciphertext_each_time(self):
        """Deux chiffrements du même plaintext → ciphertexts différents (nonce aléatoire)."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ct1 = encrypt_totp_secret(plaintext)
        ct2 = encrypt_totp_secret(plaintext)
        assert ct1 != ct2  # nonce différent → ciphertext différent

    def test_ciphertext_does_not_contain_plaintext(self):
        """Le ciphertext ne contient pas le plaintext en clair."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ct = encrypt_totp_secret(plaintext)
        assert plaintext.encode("utf-8") not in ct


class TestDecryptTotpSecret:
    """Tests pour le déchiffrement AES-256-GCM."""

    def test_roundtrip(self):
        """Encrypt → decrypt = plaintext original."""
        plaintext = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_totp_secret(plaintext)
        decrypted = decrypt_totp_secret(encrypted)
        assert decrypted == plaintext

    def test_roundtrip_various_lengths(self):
        """Roundtrip fonctionne pour différentes longueurs de secret."""
        for secret in ["A", "AB", "SHORT", "JBSWY3DPEHPK3PXP", "A" * 100]:
            encrypted = encrypt_totp_secret(secret)
            assert decrypt_totp_secret(encrypted) == secret

    def test_roundtrip_special_characters(self):
        """Roundtrip fonctionne avec des caractères spéciaux."""
        secret = "ABC+/=123éàü"
        encrypted = encrypt_totp_secret(secret)
        assert decrypt_totp_secret(encrypted) == secret

    def test_decrypt_too_short_raises(self):
        """Données trop courtes (< 28 bytes) → ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decrypt_totp_secret(b"short")

    def test_decrypt_empty_raises(self):
        """Données vides → ValueError."""
        with pytest.raises(ValueError, match="too short"):
            decrypt_totp_secret(b"")

    def test_decrypt_tampered_data_raises(self):
        """Données corrompues (bit flip) → erreur de déchiffrement."""
        plaintext = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_totp_secret(plaintext)

        # Corrompre un byte au milieu du ciphertext (après le nonce)
        tampered = bytearray(encrypted)
        tampered[15] ^= 0xFF  # flip tous les bits du byte 15
        tampered = bytes(tampered)

        with pytest.raises(Exception):  # InvalidTag ou similaire
            decrypt_totp_secret(tampered)

    def test_decrypt_wrong_key_raises(self):
        """Déchiffrement avec une clé différente → erreur."""
        plaintext = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_totp_secret(plaintext)

        with patch("app.core.crypto.settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = "completely_different_key_999"
            with pytest.raises(Exception):  # InvalidTag
                decrypt_totp_secret(encrypted)

    def test_decrypt_truncated_ciphertext_raises(self):
        """Ciphertext tronqué (nonce ok mais ciphertext coupé) → erreur."""
        plaintext = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_totp_secret(plaintext)

        # Garder le nonce + seulement quelques bytes
        truncated = encrypted[:20]
        with pytest.raises(Exception):
            decrypt_totp_secret(truncated)
