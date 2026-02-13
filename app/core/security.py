"""Utilitaires de sécurité : JWT, hashing passwords, validation."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings
from app.constants import Limits, TokenType


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

    Example:
        token = create_access_token({
            "sub": user.id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "role": user.role
        })

    Claims standards:
        - sub: Subject (user_id)
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
        "type": TokenType.ACCESS
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
        - Ne doit contenir que les infos essentielles (user_id, tenant_id)
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
        "type": TokenType.REFRESH
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Décode et valide un JWT token.

    Args:
        token: JWT token à décoder

    Returns:
        Claims du token si valide, None si invalide

    Validation:
        - Signature valide
        - Token non expiré
        - Algorithm correct (HS256)

    Example:
        claims = decode_token(token)
        if claims:
            user_id = claims.get("sub")
            tenant_id = claims.get("tenant_id")
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash.

    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash bcrypt du mot de passe

    Returns:
        True si le mot de passe correspond, False sinon

    Note:
        - Utilise bcrypt avec rounds=12
        - Temps de vérification: ~100-200ms (protection brute-force)
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash un mot de passe avec bcrypt.

    Args:
        password: Mot de passe en clair

    Returns:
        Hash bcrypt du mot de passe

    Note:
        - Utilise bcrypt avec rounds=12 (défini dans settings)
        - Génère un salt aléatoire automatiquement
        - Hash format: $2b$12$... (60 caractères)

    Example:
        hashed = get_password_hash("secretpass123")
        # "$2b$12$Abc...Xyz"
    """
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """Valide la robustesse d'un mot de passe.

    Args:
        password: Mot de passe à valider

    Returns:
        Tuple (is_valid, error_message)

    Rules:
        - Longueur >= 8 caractères
        - Au moins une lettre
        - Au moins un chiffre

    Example:
        is_valid, error = validate_password_strength("weak")
        if not is_valid:
            raise ValueError(error)
    """
    if len(password) < Limits.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {Limits.PASSWORD_MIN_LENGTH} characters long"

    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    return True, None
