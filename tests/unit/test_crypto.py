"""Tests unitaires pour app.core.crypto — envelope encryption v2 AES-256-GCM.

Vérifie :
    - Roundtrip encrypt → decrypt
    - Plaintext vide = erreur
    - Données corrompues = erreur
    - Colonnes envelope manquantes = erreur explicite
    - Dérivation de clé legacy v1 déterministe (migration)
    - Nonce unique à chaque appel (pas de réutilisation)
    - Ciphertext ≠ plaintext (pas de fuite en clair)
"""
import pytest
from unittest.mock import patch

from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret, _derive_key


class TestDeriveKey:
    """Tests pour la dérivation de clé AES-256 legacy v1 (migration)."""

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
    """Tests pour le chiffrement envelope v2 (DEK + KEK, AES-256-GCM)."""

    def test_encrypt_returns_four_tuple(self):
        """Le résultat est un tuple (ciphertext, nonce, encrypted_dek, key_version)."""
        result = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        assert isinstance(result, tuple)
        assert len(result) == 4
        ciphertext, nonce, encrypted_dek, key_version = result
        assert isinstance(ciphertext, bytes)
        assert isinstance(nonce, bytes)
        assert isinstance(encrypted_dek, bytes)
        assert isinstance(key_version, str)

    def test_encrypt_component_sizes(self):
        """Nonce = 12 bytes, encrypted_dek ≥ 28 bytes (12 nonce + 16 tag), ciphertext ≥ 17 bytes (1+16 tag)."""
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret("A")
        assert len(nonce) == 12
        assert len(encrypted_dek) >= 28
        assert len(ciphertext) >= 17  # 1 byte plaintext + 16 bytes GCM tag

    def test_encrypt_empty_plaintext_raises(self):
        """Plaintext vide → ValueError."""
        with pytest.raises(ValueError, match="Cannot encrypt empty plaintext"):
            encrypt_totp_secret("")

    def test_encrypt_none_plaintext_raises(self):
        """Plaintext None → ValueError."""
        with pytest.raises(ValueError):
            encrypt_totp_secret(None)

    def test_encrypt_produces_different_ciphertext_each_time(self):
        """Deux chiffrements du même plaintext → ciphertexts différents (DEK + nonce aléatoires)."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ct1, n1, d1, _ = encrypt_totp_secret(plaintext)
        ct2, n2, d2, _ = encrypt_totp_secret(plaintext)
        # DEK différent → ciphertext différent ; nonce différent ; encrypted_dek différent
        assert ct1 != ct2
        assert n1 != n2
        assert d1 != d2

    def test_ciphertext_does_not_contain_plaintext(self):
        """Le ciphertext ne contient pas le plaintext en clair."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext, _, _, _ = encrypt_totp_secret(plaintext)
        assert plaintext.encode("utf-8") not in ciphertext


class TestDecryptTotpSecret:
    """Tests pour le déchiffrement envelope v2."""

    def test_roundtrip(self):
        """Encrypt → decrypt = plaintext original."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(plaintext)
        decrypted = decrypt_totp_secret(ciphertext, nonce, encrypted_dek)
        assert decrypted == plaintext

    def test_roundtrip_various_lengths(self):
        """Roundtrip fonctionne pour différentes longueurs de secret."""
        for secret in ["A", "AB", "SHORT", "JBSWY3DPEHPK3PXP", "A" * 100]:
            ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(secret)
            assert decrypt_totp_secret(ciphertext, nonce, encrypted_dek) == secret

    def test_roundtrip_special_characters(self):
        """Roundtrip fonctionne avec des caractères spéciaux."""
        secret = "ABC+/=123éàü"
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(secret)
        assert decrypt_totp_secret(ciphertext, nonce, encrypted_dek) == secret

    def test_decrypt_missing_nonce_raises(self):
        """Colonne nonce absente (None/empty) → ValueError explicite."""
        ciphertext, _, encrypted_dek, _ = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        with pytest.raises(ValueError, match="envelope encryption"):
            decrypt_totp_secret(ciphertext, b"", encrypted_dek)

    def test_decrypt_missing_encrypted_dek_raises(self):
        """Colonne encrypted_dek absente (None/empty) → ValueError explicite."""
        ciphertext, nonce, _, _ = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        with pytest.raises(ValueError, match="envelope encryption"):
            decrypt_totp_secret(ciphertext, nonce, b"")

    def test_decrypt_encrypted_dek_too_short_raises(self):
        """encrypted_dek < 28 bytes → ValueError (taille minimum 12 nonce + 16 tag)."""
        ciphertext, nonce, _, _ = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
        with pytest.raises(ValueError, match="trop court"):
            decrypt_totp_secret(ciphertext, nonce, b"short")

    def test_decrypt_tampered_ciphertext_raises(self):
        """Ciphertext corrompu (bit flip) → erreur InvalidTag."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(plaintext)

        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises(Exception):  # InvalidTag
            decrypt_totp_secret(tampered, nonce, encrypted_dek)

    def test_decrypt_tampered_nonce_raises(self):
        """Nonce corrompu → erreur InvalidTag (mauvais IV)."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(plaintext)

        tampered_nonce = bytearray(nonce)
        tampered_nonce[0] ^= 0xFF
        tampered_nonce = bytes(tampered_nonce)

        with pytest.raises(Exception):  # InvalidTag
            decrypt_totp_secret(ciphertext, tampered_nonce, encrypted_dek)

    def test_decrypt_wrong_kek_raises(self):
        """Déchiffrement avec un KEK différent (TOTP_DEV_MASTER_KEY modifié) → erreur."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(plaintext)

        with patch("app.core.crypto.settings") as mock_settings:
            mock_settings.TOTP_DEV_MASTER_KEY = "completely_different_master_key_for_testing_999"
            with pytest.raises(Exception):  # InvalidTag (DEK decrypt échoue)
                decrypt_totp_secret(ciphertext, nonce, encrypted_dek)

    def test_decrypt_truncated_ciphertext_raises(self):
        """Ciphertext tronqué → erreur InvalidTag."""
        plaintext = "JBSWY3DPEHPK3PXP"
        ciphertext, nonce, encrypted_dek, _ = encrypt_totp_secret(plaintext)

        truncated = ciphertext[:5]
        with pytest.raises(Exception):
            decrypt_totp_secret(truncated, nonce, encrypted_dek)
