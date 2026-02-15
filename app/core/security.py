"""Utilitaires de sécurité : JWT, hashing passwords, validation."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import ExpiredSignatureError, jwt
import argon2
import bcrypt
import uuid
from app.core.config import settings
from app.core.exceptions import TokenExpired, TokenInvalid
from app.constants import Argon2Params, Limits, TokenType

logger = logging.getLogger(__name__)

# Argon2id hasher — initialisé une fois au démarrage du module
_argon2_hasher = argon2.PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
    hash_len=Argon2Params.HASH_LENGTH,
    salt_len=Argon2Params.SALT_LENGTH,
)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Crée un JWT access token.

    Args:
        data: Données à encoder dans le token (claims)
        expires_delta: Durée de validité (défaut: JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        JWT token encodé

    Claims standards:
        - sub: Subject (user_id)
        - jti: JWT ID unique (pour revocation)
        - exp: Expiration timestamp
        - iat: Issued at timestamp
    """
    to_encode = data.copy()

    # JWT spec: "sub" claim MUST be a string (not int)
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": TokenType.ACCESS,
        "jti": str(uuid.uuid4()),
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    """Crée un JWT refresh token (longue durée).

    Args:
        data: Données à encoder dans le token (claims)

    Returns:
        JWT refresh token encodé

    Note:
        - Durée de validité: JWT_REFRESH_TOKEN_EXPIRE_DAYS (7 jours)
        - Contient un JTI unique pour whitelist Redis
    """
    to_encode = data.copy()

    # JWT spec: "sub" claim MUST be a string (not int)
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])

    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": TokenType.REFRESH,
        "jti": str(uuid.uuid4()),
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Décode et valide un JWT token.

    Args:
        token: JWT token à décoder

    Returns:
        Claims du token si valide

    Raises:
        TokenExpired: Si le token a expiré
        TokenInvalid: Si le token est invalide (signature, format, etc.)
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except ExpiredSignatureError:
        raise TokenExpired()
    except Exception:
        raise TokenInvalid()


def _is_bcrypt_hash(hashed: str) -> bool:
    """Détecte si un hash est au format bcrypt."""
    return hashed.startswith(Argon2Params.BCRYPT_PREFIX)


def _is_argon2_hash(hashed: str) -> bool:
    """Détecte si un hash est au format Argon2id."""
    return hashed.startswith(Argon2Params.ARGON2ID_PREFIX)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash (Argon2id ou bcrypt).

    Auto-détection de l'algorithme via le préfixe du hash :
        - $argon2id$ → vérification Argon2id
        - $2b$ → vérification bcrypt (legacy, migration transparente)

    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash Argon2id ou bcrypt

    Returns:
        True si le mot de passe correspond, False sinon
    """
    if _is_argon2_hash(hashed_password):
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except argon2.exceptions.VerifyMismatchError:
            return False
        except argon2.exceptions.VerificationError:
            return False

    if _is_bcrypt_hash(hashed_password):
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    return False


def needs_rehash(hashed_password: str) -> bool:
    """Vérifie si un hash doit être re-hashé en Argon2id.

    Retourne True si :
        - Le hash est bcrypt (migration vers Argon2id)
        - Le hash est Argon2id mais avec des paramètres obsolètes

    Args:
        hashed_password: Hash existant

    Returns:
        True si rehash nécessaire
    """
    if _is_bcrypt_hash(hashed_password):
        return True

    if _is_argon2_hash(hashed_password):
        return _argon2_hasher.check_needs_rehash(hashed_password)

    return True


def get_password_hash(password: str) -> str:
    """Hash un mot de passe avec Argon2id.

    Args:
        password: Mot de passe en clair

    Returns:
        Hash Argon2id du mot de passe
    """
    return _argon2_hasher.hash(password)


# DUMMY_HASH: hash généré dynamiquement au démarrage du module (Argon2id).
# Utilisé pour timing-safe login : on vérifie verify_password même si
# l'utilisateur n'existe pas, afin que le temps de réponse soit constant.
DUMMY_HASH: str = get_password_hash("__dummy_startup_password__")


def validate_password_strength(password: str, role: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Valide la robustesse d'un mot de passe.

    Délègue à password_policy si disponible, sinon applique les règles basiques.

    Args:
        password: Mot de passe à valider
        role: Rôle de l'utilisateur (optionnel, pour longueur min adaptée)

    Returns:
        Tuple (is_valid, error_message). error_message est None si valide.
    """
    # Import lazy pour éviter import circulaire au module load
    try:
        from app.core.password_policy import validate_password
        return validate_password(password, role=role)
    except ImportError:
        pass

    # Fallback basique (sera remplacé par Feature 8)
    if len(password) < Limits.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {Limits.PASSWORD_MIN_LENGTH} characters long"

    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c in "!@#$%^&*()-_=+[]{}|;:',.<>?/~`" for c in password):
        return False, "Password must contain at least one special character"

    return True, None
