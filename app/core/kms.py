"""Gestion des cles RSA pour signature JWT (CaroCorp §1.1-1.3).

Deux paires de cles distinctes (CaroCorp §1.1) :
    - access : JWT_ACCESS_{PRIVATE,PUBLIC}_KEY_PATH / KMS_KEY_ACCESS
    - refresh : JWT_REFRESH_{PRIVATE,PUBLIC}_KEY_PATH / KMS_KEY_REFRESH

En dev : chargement depuis fichiers PEM locaux.
En prod : signature via AWS KMS, verification avec cle publique locale.

Usage:
    from app.core.kms import (
        get_access_private_key, get_access_public_key,
        get_refresh_private_key, get_refresh_public_key,
        get_jwks_response,
    )
"""
import base64
import hashlib
import logging
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config import settings

logger = logging.getLogger(__name__)


def _generate_keypair(private_path: str, public_path: str) -> None:
    """Genere une paire RSA 2048 et ecrit les fichiers PEM. Ne fait rien si les fichiers existent."""
    priv = Path(private_path)
    pub = Path(public_path)

    if priv.exists() and pub.exists():
        logger.debug("Dev keypair already exists at %s / %s", private_path, public_path)
        return

    priv.parent.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=settings.JWT_RSA_KEY_SIZE)

    priv.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    logger.info("Generated dev RSA keypair: %s / %s", private_path, public_path)


def generate_dev_keypairs() -> None:
    """Genere les deux paires RSA (access + refresh) pour le developpement local.

    Cree le repertoire keys/ si absent. Ne fait rien pour les paires deja existantes.
    """
    _generate_keypair(
        settings.JWT_ACCESS_PRIVATE_KEY_PATH,
        settings.JWT_ACCESS_PUBLIC_KEY_PATH,
    )
    _generate_keypair(
        settings.JWT_REFRESH_PRIVATE_KEY_PATH,
        settings.JWT_REFRESH_PUBLIC_KEY_PATH,
    )


def _load_private_key(path_str: str) -> RSAPrivateKey:
    """Charge une cle privee RSA depuis un fichier PEM."""
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(
            f"JWT private key not found: {path}. Run generate_dev_keypairs()."
        )
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise ValueError(f"Expected RSA private key, got {type(key).__name__}")
    logger.info("Loaded RSA private key from %s", path)
    return key


def _load_public_key(path_str: str) -> RSAPublicKey:
    """Charge une cle publique RSA depuis un fichier PEM."""
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(
            f"JWT public key not found: {path}. Run generate_dev_keypairs()."
        )
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, RSAPublicKey):
        raise ValueError(f"Expected RSA public key, got {type(key).__name__}")
    logger.info("Loaded RSA public key from %s", path)
    return key


@lru_cache(maxsize=1)
def get_access_private_key() -> RSAPrivateKey:
    """Cle privee pour signer les access tokens (KMS_KEY_ACCESS / §1.1)."""
    return _load_private_key(settings.JWT_ACCESS_PRIVATE_KEY_PATH)


@lru_cache(maxsize=1)
def get_access_public_key() -> RSAPublicKey:
    """Cle publique pour verifier les access tokens."""
    return _load_public_key(settings.JWT_ACCESS_PUBLIC_KEY_PATH)


@lru_cache(maxsize=1)
def get_refresh_private_key() -> RSAPrivateKey:
    """Cle privee pour signer les refresh tokens (KMS_KEY_REFRESH / §1.1)."""
    return _load_private_key(settings.JWT_REFRESH_PRIVATE_KEY_PATH)


@lru_cache(maxsize=1)
def get_refresh_public_key() -> RSAPublicKey:
    """Cle publique pour verifier les refresh tokens."""
    return _load_public_key(settings.JWT_REFRESH_PUBLIC_KEY_PATH)


# Aliases retro-compatibilite (supprimer apres migration complete)
get_private_key = get_access_private_key
get_public_key = get_access_public_key


def _int_to_base64url(n: int) -> str:
    """Convertit un entier en base64url sans padding (format JWK)."""
    byte_length = (n.bit_length() + 7) // 8
    n_bytes = n.to_bytes(byte_length, byteorder="big")
    return base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode("ascii")


def _compute_kid(public_key: RSAPublicKey) -> str:
    """Calcule un kid (Key ID) stable a partir du SHA-256 de la cle publique DER."""
    der_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(der_bytes).digest()
    return base64.urlsafe_b64encode(digest[:16]).rstrip(b"=").decode("ascii")


def get_jwk(public_key: RSAPublicKey) -> dict:
    """Convertit une cle publique RSA en format JWK (RFC 7517).

    Args:
        public_key: Cle publique RSA.

    Returns:
        dict JWK avec kty, use, alg, kid, n, e.
    """
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": _compute_kid(public_key),
        "n": _int_to_base64url(numbers.n),
        "e": _int_to_base64url(numbers.e),
    }


def get_jwks_response() -> dict:
    """Retourne la reponse JWKS complete pour /.well-known/jwks.json.

    Expose les deux cles publiques (access + refresh) conformement a §1.5.

    Returns:
        dict {"keys": [jwk_access, jwk_refresh]}
    """
    return {
        "keys": [
            get_jwk(get_access_public_key()),
            get_jwk(get_refresh_public_key()),
        ]
    }
