"""Utilitaires de securite : JWT RS256, hashing passwords, validation.

Migration v3 (CaroCorp §1.1-1.4) :
    - Signature RS256 via cle privee PEM (dev) / KMS (prod)
    - Verification via cle publique RSA
    - Claims standards : iss, aud (access only), nbf, iat, exp, jti
    - Clock skew ±30s sur exp et nbf
"""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError, InvalidTokenError
import argon2
import bcrypt
import uuid
from app.core.config import settings
from app.core.exceptions import TokenExpired, TokenInvalid
from app.constants import Argon2Params, Limits, TokenType

logger = logging.getLogger(__name__)

# Argon2id hasher — initialise une fois au demarrage du module
_argon2_hasher = argon2.PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
    hash_len=Argon2Params.HASH_LENGTH,
    salt_len=Argon2Params.SALT_LENGTH,
)


def _get_private_key():
    """Cle privee access RSA (lazy import — evite import circulaire)."""
    from app.core.kms import get_access_private_key
    return get_access_private_key()


def _get_public_key():
    """Cle publique access RSA (lazy import — evite import circulaire)."""
    from app.core.kms import get_access_public_key
    return get_access_public_key()


def _get_refresh_private_key():
    """Cle privee refresh RSA (lazy import — evite import circulaire)."""
    from app.core.kms import get_refresh_private_key
    return get_refresh_private_key()


def _get_refresh_public_key():
    """Cle publique refresh RSA (lazy import — evite import circulaire)."""
    from app.core.kms import get_refresh_public_key
    return get_refresh_public_key()


def compute_client_binding_hash(ip: str, user_agent: str) -> str:
    """Hash IP subnet /24 + User-Agent pour token binding (M-02).

    Le subnet /24 tolere les changements d'IP dans le meme reseau local
    (NAT mobile, DHCP). IPv6 utilise /48.
    """
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv4Address):
            subnet = str(ipaddress.IPv4Network(f"{ip}/24", strict=False))
        else:
            subnet = str(ipaddress.IPv6Network(f"{ip}/48", strict=False))
    except ValueError:
        subnet = ip
    raw = f"{subnet}|{user_agent}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    audience: Optional[str] = None,
) -> str:
    """Cree un JWT access token signe en RS256 (CaroCorp §1.2).

    Args:
        data: Claims applicatifs (sub, tenant_id, role, etc.)
              Peut inclure 'cbh' (client binding hash) pour le token binding.
        expires_delta: Duree de validite (defaut: JWT_ACCESS_TOKEN_EXPIRE_SECONDS)

    Returns:
        JWT token encode RS256

    Claims ajoutes automatiquement:
        iss, aud, exp, nbf, iat, jti, type
    """
    now = datetime.now(timezone.utc)
    to_encode = data.copy()

    # RFC 7519: sub MUST be string
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    if "tenant_id" in to_encode and not isinstance(to_encode["tenant_id"], str):
        to_encode["tenant_id"] = str(to_encode["tenant_id"])

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS)

    to_encode.update({
        "iss": settings.JWT_ISSUER,
        "aud": audience or settings.JWT_AUDIENCE,
        "exp": expire,
        "nbf": now,
        "iat": now,
        "type": TokenType.ACCESS,
        "jti": str(uuid.uuid4()),
    })

    from app.core.kms import _compute_kid
    kid = _compute_kid(_get_public_key())
    return jwt.encode(
        to_encode,
        _get_private_key(),
        algorithm=settings.JWT_ALGORITHM,
        headers={"kid": kid},
    )


def create_refresh_token(
    data: dict[str, Any],
    audience: Optional[str] = None,
) -> str:
    """Cree un JWT refresh token signe en RS256 (CaroCorp §1.3).

    Args:
        data: Claims applicatifs (sub, tenant_id, family_id, etc.)

    Returns:
        JWT refresh token encode RS256

    Note:
        - TTL: JWT_REFRESH_TOKEN_EXPIRE_SECONDS (604800s = 7 jours)
        - Claim 'aud' = '{JWT_AUDIENCE}:refresh' (audience distincte de l'access token)
        - Contient un JTI unique pour whitelist Redis
    """
    now = datetime.now(timezone.utc)
    to_encode = data.copy()

    # RFC 7519: sub MUST be string
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    if "tenant_id" in to_encode and not isinstance(to_encode["tenant_id"], str):
        to_encode["tenant_id"] = str(to_encode["tenant_id"])

    expire = now + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRE_SECONDS)

    base_aud = audience or settings.JWT_AUDIENCE
    to_encode.update({
        "iss": settings.JWT_ISSUER,
        "aud": f"{base_aud}:refresh",
        "exp": expire,
        "nbf": now,
        "iat": now,
        "type": TokenType.REFRESH,
        "jti": str(uuid.uuid4()),
    })

    from app.core.kms import _compute_kid, get_refresh_public_key as _get_refresh_pub
    kid = _compute_kid(_get_refresh_pub())
    return jwt.encode(
        to_encode,
        _get_refresh_private_key(),
        algorithm=settings.JWT_ALGORITHM,
        headers={"kid": kid},
    )


def decode_token(
    token: str,
    expected_audience: Optional[str] = None,
) -> dict[str, Any]:
    """Decode et valide un JWT token RS256 (CaroCorp §1.6).

    Verification :
        - Signature RSA via cle publique
        - Claims exp, nbf avec tolerance ±30s (JWT_CLOCK_SKEW_SECONDS)
        - Issuer (iss)
        - Audience (aud) — optionnel (absent dans refresh tokens)

    Args:
        token: JWT token a decoder

    Returns:
        Claims du token si valide

    Raises:
        TokenExpired: Si le token a expire
        TokenInvalid: Si le token est invalide (signature, format, etc.)
    """
    # P0-03 : inspecter le claim 'type' sans verifier la signature pour
    # selectionner la cle publique correcte (defense-in-depth §1.1).
    # Un refresh token soumis a un endpoint access sera rejete immediatement.
    try:
        unverified = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=[settings.JWT_ALGORITHM],
        )
        token_type = unverified.get("type")
    except InvalidTokenError:
        raise TokenInvalid()

    if token_type == TokenType.ACCESS:
        pub_keys = [_get_public_key()]
    elif token_type == TokenType.REFRESH:
        pub_keys = [_get_refresh_public_key()]
    else:
        # Type absent ou inconnu — tenter les deux cles (tokens legacy)
        pub_keys = [_get_public_key(), _get_refresh_public_key()]

    _decode_kwargs = dict(
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        leeway=timedelta(seconds=settings.JWT_CLOCK_SKEW_SECONDS),
        options={
            "require": ["exp", "iat", "jti", "sub", "iss"],
            "verify_aud": False,
        },
    )
    for pub_key in pub_keys:
        try:
            payload = jwt.decode(token, pub_key, **_decode_kwargs)
        except ExpiredSignatureError:
            raise TokenExpired()
        except InvalidSignatureError:
            continue  # Mauvaise cle — essayer la suivante
        except InvalidTokenError:
            raise TokenInvalid()

        # P1-10 : validation audience post-decode selon le type
        # ISO-APP-01 : si expected_audience fourni, on le compare au lieu du global JWT_AUDIENCE.
        # Sinon l'audience du token doit être dans JWT_AUDIENCES (toute app valide) pour
        # rester rétro-compatible avec les tokens legacy aud=JWT_AUDIENCE.
        actual_type = payload.get("type")
        actual_aud = payload.get("aud")
        valid_access_auds = set(settings.JWT_AUDIENCES.values()) | {settings.JWT_AUDIENCE}
        valid_refresh_auds = {f"{a}:refresh" for a in valid_access_auds}
        if actual_type == TokenType.ACCESS:
            if expected_audience is not None:
                if actual_aud != expected_audience:
                    raise TokenInvalid("Access token audience mismatch")
            elif actual_aud not in valid_access_auds:
                raise TokenInvalid("Access token audience mismatch")
        elif actual_type == TokenType.REFRESH:
            if expected_audience is not None:
                if actual_aud != f"{expected_audience}:refresh":
                    raise TokenInvalid("Refresh token audience mismatch")
            elif actual_aud not in valid_refresh_auds:
                raise TokenInvalid("Refresh token audience mismatch")
        return payload
    raise TokenInvalid()


def decode_access_token(
    token: str,
    expected_audience: Optional[str] = None,
) -> dict[str, Any]:
    """Décode un access token et vérifie l'audience (spec §01-CRYPTO-JWT §1.6).

    Appelle decode_token() puis valide le claim 'aud'.
    - Si `expected_audience` fourni : aud doit matcher exactement (enforcement app).
    - Sinon : aud doit être dans settings.JWT_AUDIENCES (toute app valide).

    Les refresh tokens n'ont pas de claim 'aud' — utiliser decode_token() à leur place.

    Args:
        token: JWT access token à décoder
        expected_audience: ISO-APP-01 — audience strict attendu (ex: "marveline-api").
                           Si None, accepte toute app connue.

    Returns:
        Claims du token si valide

    Raises:
        TokenExpired: Si le token a expiré
        TokenInvalid: Si le token est invalide ou si l'audience ne correspond pas
    """
    payload = decode_token(token, expected_audience=expected_audience)
    actual_aud = payload.get("aud")
    if expected_audience is not None:
        if actual_aud != expected_audience:
            raise TokenInvalid()
    else:
        valid_auds = set(settings.JWT_AUDIENCES.values()) | {settings.JWT_AUDIENCE}
        if actual_aud not in valid_auds:
            raise TokenInvalid()
    return payload


def _is_bcrypt_hash(hashed: str) -> bool:
    """Detecte si un hash est au format bcrypt."""
    return hashed.startswith(Argon2Params.BCRYPT_PREFIX)


def _is_argon2_hash(hashed: str) -> bool:
    """Detecte si un hash est au format Argon2id."""
    return hashed.startswith(Argon2Params.ARGON2ID_PREFIX)


def _prepare_password(plain_password: str) -> bytes:
    """SHA-256 prehash + HMAC-SHA256 pepper avant hachage (CaroCorp §13.5).

    SHA-256 prehash : normalise la longueur, contourne la limite bcrypt 72 bytes.
    HMAC-SHA256 pepper : defense en profondeur si la DB est compromise.

    Args:
        plain_password: Mot de passe en clair

    Returns:
        32 bytes prepares, prets pour Argon2id ou bcrypt
    """
    password_bytes = hashlib.sha256(plain_password.encode("utf-8")).digest()
    pepper = settings.PASSWORD_PEPPER.encode("utf-8")
    return hmac.new(pepper, password_bytes, hashlib.sha256).digest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifie un mot de passe contre son hash (Argon2id ou bcrypt).

    Auto-detection de l'algorithme via le prefixe du hash :
        - $argon2id$ → verification Argon2id
        - $2b$ → verification bcrypt (legacy, migration transparente)

    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash Argon2id ou bcrypt

    Returns:
        True si le mot de passe correspond, False sinon
    """
    prepared = _prepare_password(plain_password)

    if _is_argon2_hash(hashed_password):
        # Essayer avec pepper (hashs v3)
        try:
            if _argon2_hasher.verify(hashed_password, prepared):
                return True
        except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError):
            pass
        # Fallback sans pepper (migration transparente hashs pre-v3)
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError):
            return False

    if _is_bcrypt_hash(hashed_password):
        hashed_bytes = hashed_password.encode("utf-8")
        # Essayer avec pepper (hashs durcis)
        if bcrypt.checkpw(prepared, hashed_bytes):
            return True
        # Fallback sans pepper (legacy)
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_bytes)

    return False


def needs_rehash(hashed_password: str) -> bool:
    """Verifie si un hash doit etre re-hashe en Argon2id.

    Retourne True si :
        - Le hash est bcrypt (migration vers Argon2id)
        - Le hash est Argon2id mais avec des parametres obsoletes

    Args:
        hashed_password: Hash existant

    Returns:
        True si rehash necessaire
    """
    if _is_bcrypt_hash(hashed_password):
        return True

    if _is_argon2_hash(hashed_password):
        return _argon2_hasher.check_needs_rehash(hashed_password)

    return True


def get_password_hash(password: str) -> str:
    """Hash un mot de passe avec Argon2id + pepper (CaroCorp §13.5).

    Applique SHA-256 prehash + HMAC-SHA256 pepper avant de hasher en Argon2id.

    Args:
        password: Mot de passe en clair

    Returns:
        Hash Argon2id du mot de passe prepare
    """
    prepared = _prepare_password(password)
    return _argon2_hasher.hash(prepared)


# DUMMY_HASH: hash genere dynamiquement au demarrage du module (Argon2id).
# Utilise pour timing-safe login : on verifie verify_password meme si
# l'utilisateur n'existe pas, afin que le temps de reponse soit constant.
DUMMY_HASH: str = get_password_hash("__dummy_startup_password__")


def validate_password_strength(password: str, role: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Valide la robustesse d'un mot de passe.

    Delegue a password_policy si disponible, sinon applique les regles basiques.

    Args:
        password: Mot de passe a valider
        role: Role de l'utilisateur (optionnel, pour longueur min adaptee)

    Returns:
        Tuple (is_valid, error_message). error_message est None si valide.
    """
    # Import lazy pour eviter import circulaire au module load
    try:
        from app.core.password_policy import validate_password
        return validate_password(password, role=role)
    except ImportError:
        pass

    # Fallback basique
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
