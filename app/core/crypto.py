"""Cryptographic utilities — AES-256-GCM for TOTP secret encryption.

Provides symmetric encryption/decryption for sensitive data that must be
stored encrypted at rest (e.g. MFA TOTP secrets in the database).

Key management:
    - Key sourced from settings.ENCRYPTION_KEY (ENV variable)
    - Key MUST be exactly 32 bytes (256 bits) for AES-256
    - If key is shorter, it is zero-padded; if longer, truncated (dev only)
    - In production, use a proper 32-byte random key

Security:
    - AES-256-GCM provides authenticated encryption (confidentiality + integrity)
    - Random 12-byte nonce per encryption (never reused)
    - Ciphertext format: nonce (12B) || ciphertext || tag (16B)
"""
import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


def _derive_key() -> bytes:
    """Derive a 32-byte AES-256 key from the configured ENCRYPTION_KEY.

    Uses SHA-256 to ensure exactly 32 bytes regardless of input length.
    This is deterministic: same input always produces same key.

    Returns:
        32-byte key suitable for AES-256-GCM
    """
    raw = settings.ENCRYPTION_KEY.encode("utf-8")
    return hashlib.sha256(raw).digest()


def encrypt_totp_secret(plaintext: str) -> bytes:
    """Encrypt a TOTP secret using AES-256-GCM.

    Args:
        plaintext: The TOTP secret string to encrypt

    Returns:
        Encrypted bytes: nonce (12B) || ciphertext || tag (16B)

    Raises:
        ValueError: If plaintext is empty
    """
    if not plaintext:
        raise ValueError("Cannot encrypt empty plaintext")

    key = _derive_key()
    aesgcm = AESGCM(key)

    # 12-byte random nonce (recommended for GCM)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # nonce || ciphertext+tag
    return nonce + ciphertext


def decrypt_totp_secret(encrypted: bytes) -> str:
    """Decrypt a TOTP secret encrypted with encrypt_totp_secret().

    Args:
        encrypted: Encrypted bytes (nonce + ciphertext + tag)

    Returns:
        Decrypted TOTP secret string

    Raises:
        ValueError: If encrypted data is too short or tampered with
    """
    if len(encrypted) < 12 + 16:
        raise ValueError("Encrypted data too short (need at least 28 bytes)")

    key = _derive_key()
    aesgcm = AESGCM(key)

    nonce = encrypted[:12]
    ciphertext = encrypted[12:]

    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")
