"""Cryptographic utilities — AES-256-GCM envelope encryption for TOTP secrets.

Architecture v2 (spec §05-MFA-TOTP §5.4 — envelope encryption) :
    - DEK (Data Encryption Key) : 32 bytes random per operation
    - KEK (Key Encryption Key) : HMAC-SHA256(TOTP_DEV_MASTER_KEY) en dev,
                                  AWS KMS GenerateDataKey en prod
    - Colonnes DB séparées : ciphertext, nonce, encrypted_dek, key_version

Architecture v1 (legacy — migration uniquement) :
    - Ciphertext format : nonce (12B) || ciphertext || tag (16B)
    - Clé : SHA-256(settings.ENCRYPTION_KEY)
    - _derive_key() conservée pour la migration de données uniquement

Key management:
    - TOTP_DEV_MASTER_KEY : variable d'environnement (≥ 32 chars)
    - En production, remplacer par AWS KMS / Azure Key Vault
"""
import hashlib
import hmac
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


# ======= Legacy v1 — migration uniquement =======

def _derive_key() -> bytes:
    """Dérive une clé AES-256 depuis ENCRYPTION_KEY (v1 — migration uniquement).

    Déterministe : même input → même clé. Ne pas utiliser pour nouveau chiffrement.
    """
    raw = settings.ENCRYPTION_KEY.encode("utf-8")
    return hashlib.sha256(raw).digest()


# ======= Envelope encryption v2 =======

def _get_kek_dev() -> bytes:
    """Dérive le KEK depuis TOTP_DEV_MASTER_KEY (mode dev).

    Prod : remplacer par AWS KMS GenerateDataKey / decrypt.
    """
    master = settings.TOTP_DEV_MASTER_KEY.encode("utf-8")
    return hmac.new(master, b"totp-kek-v1", hashlib.sha256).digest()


def _encrypt_dek(dek: bytes, kek: bytes) -> bytes:
    """Chiffre le DEK avec le KEK. Retourne nonce_12b + ct_dek_tag."""
    nonce = os.urandom(12)
    return nonce + AESGCM(kek).encrypt(nonce, dek, None)


def _decrypt_dek(encrypted_dek: bytes, kek: bytes) -> bytes:
    """Déchiffre le DEK. Format attendu : nonce_12b + ct_dek_tag."""
    if len(encrypted_dek) < 12 + 16:
        raise ValueError("encrypted_dek trop court (minimum 28 bytes)")
    nonce, ct = encrypted_dek[:12], encrypted_dek[12:]
    return AESGCM(kek).decrypt(nonce, ct, None)


def encrypt_totp_secret(plaintext: str) -> tuple[bytes, bytes, bytes, str]:
    """Chiffre un secret TOTP via envelope encryption v2 (spec §05-MFA-TOTP §5.4).

    Un DEK aléatoire 256 bits est généré par opération et chiffré avec le KEK.
    Le secret est chiffré avec le DEK (AES-256-GCM).

    Args:
        plaintext: Secret TOTP en clair (base32)

    Returns:
        (ciphertext, nonce, encrypted_dek, key_version) :
        - ciphertext   : bytes → colonne encrypted_secret (sans nonce)
        - nonce        : bytes 12 → colonne totp_secret_nonce
        - encrypted_dek: bytes → colonne totp_encrypted_dek
        - key_version  : str → colonne totp_key_version

    Raises:
        ValueError: Si plaintext est vide
    """
    if not plaintext:
        raise ValueError("Cannot encrypt empty plaintext")

    dek = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), None)

    kek = _get_kek_dev()
    encrypted_dek = _encrypt_dek(dek, kek)

    return ciphertext, nonce, encrypted_dek, "dev-v1"


def decrypt_totp_secret(ciphertext: bytes, nonce: bytes, encrypted_dek: bytes) -> str:
    """Déchiffre un secret TOTP via envelope encryption v2 (spec §05-MFA-TOTP §5.4).

    Args:
        ciphertext   : Ciphertext + GCM tag (colonne encrypted_secret)
        nonce        : GCM nonce 12 bytes (colonne totp_secret_nonce)
        encrypted_dek: DEK chiffré par KEK (colonne totp_encrypted_dek)

    Returns:
        Secret TOTP en clair (base32)

    Raises:
        ValueError: Si colonnes manquantes ou données corrompues
    """
    if not nonce or not encrypted_dek:
        raise ValueError(
            "Colonnes envelope encryption manquantes (totp_secret_nonce / "
            "totp_encrypted_dek) — migration alembic requise"
        )

    kek = _get_kek_dev()
    dek = _decrypt_dek(encrypted_dek, kek)
    return AESGCM(dek).decrypt(nonce, ciphertext, None).decode("utf-8")
