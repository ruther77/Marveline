"""Fonctions cryptographiques pour le service WireGuard.

- Génération de paires de clés Curve25519 (WireGuard)
- Chiffrement/déchiffrement AES-256-GCM pour les clés privées en DB
"""

import base64
import os
import secrets

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_keypair() -> tuple[str, str]:
    """Génère une paire de clés WireGuard (Curve25519).

    Returns:
        Tuple (private_key_b64, public_key_b64) encodées en base64.
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes_raw()
    public_bytes = public_key.public_bytes_raw()

    private_b64 = base64.b64encode(private_bytes).decode("ascii")
    public_b64 = base64.b64encode(public_bytes).decode("ascii")

    return private_b64, public_b64


def generate_preshared_key() -> str:
    """Génère une clé pré-partagée WireGuard (32 bytes random, base64).

    Returns:
        Clé pré-partagée encodée en base64.
    """
    key_bytes = secrets.token_bytes(32)
    return base64.b64encode(key_bytes).decode("ascii")


def derive_public_key(private_key_b64: str) -> str:
    """Dérive la clé publique depuis une clé privée WireGuard.

    Args:
        private_key_b64: Clé privée encodée en base64.

    Returns:
        Clé publique encodée en base64.
    """
    private_bytes = base64.b64decode(private_key_b64)
    private_key = X25519PrivateKey.from_private_bytes(private_bytes)
    public_bytes = private_key.public_key().public_bytes_raw()
    return base64.b64encode(public_bytes).decode("ascii")


def _get_aes_key(encryption_key: str) -> bytes:
    """Convertit la clé de chiffrement string en 32 bytes pour AES-256.

    Utilise les 32 premiers bytes UTF-8 de la clé.
    En production, la clé doit faire exactement 32 caractères ASCII.
    """
    key_bytes = encryption_key.encode("utf-8")[:32]
    if len(key_bytes) < 32:
        raise ValueError(
            f"ENCRYPTION_KEY trop courte ({len(key_bytes)} bytes, minimum 32)."
        )
    return key_bytes


def encrypt_value(plaintext: str, encryption_key: str) -> str:
    """Chiffre une valeur avec AES-256-GCM.

    Format de sortie : base64(nonce || ciphertext || tag)

    Args:
        plaintext: Valeur en clair à chiffrer.
        encryption_key: Clé de chiffrement (min 32 caractères).

    Returns:
        Valeur chiffrée encodée en base64.
    """
    key = _get_aes_key(encryption_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce pour AES-GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # nonce (12) + ciphertext + tag (16) concaténés
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_value(encrypted_b64: str, encryption_key: str) -> str:
    """Déchiffre une valeur chiffrée avec AES-256-GCM.

    Args:
        encrypted_b64: Valeur chiffrée en base64 (format: nonce || ciphertext || tag).
        encryption_key: Clé de chiffrement (min 32 caractères).

    Returns:
        Valeur en clair.

    Raises:
        cryptography.exceptions.InvalidTag: Si la clé est incorrecte ou les données corrompues.
    """
    key = _get_aes_key(encryption_key)
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted_b64)
    nonce = raw[:12]
    ciphertext = raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
