"""Politique de mots de passe avancée.

Règles :
    - Longueur min 8 chars (12 pour admin/manager)
    - Au moins 1 majuscule, 1 minuscule, 1 chiffre, 1 caractère spécial
    - Pas dans la liste des common passwords (locale, pas de HTTP)
    - Pas de username/email dans le password
    - Pas de séquences triviales (aaa, 123, abc)
    - Max 128 chars

Fichiers liés :
    - app/constants/security.py (PasswordPolicy)
    - app/core/security.py (validate_password_strength délègue ici)
"""

import re
from typing import Optional

from app.constants import PasswordPolicy


# ─────────────────────────────────────────────────────────────────────
# Liste locale de common passwords (pas d'appel HTTP HIBP)
# Sources : SecLists top-200, OWASP, NCSC
# ─────────────────────────────────────────────────────────────────────

COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "shadow", "123456789", "1234567890", "passw0rd",
    "password1", "password123", "admin", "welcome", "welcome1", "p@ssw0rd",
    "p@ssword", "football", "login", "hello", "charlie", "donald", "qwerty123",
    "mustang", "access", "flower", "michael", "superman", "hottie", "loveme",
    "princess", "starwars", "batman", "soccer", "monkey123", "jennifer",
    "ginger", "killer", "george", "pepper", "zxcvbn", "121212",
    "696969", "654321", "jordan", "hunter", "amanda", "harley",
    "ranger", "thomas", "robert", "daniel", "andrea", "joshua",
    "pokemon", "whatever", "computer", "secret", "matrix", "summer",
    "freedom", "thunder", "internet", "jessica", "samantha", "chicken",
    "orange", "hannah", "nicole", "heather", "dakota", "diamond",
    "maggie", "cookie", "hockey", "jackson", "sparky", "buster",
    "tigger", "jasmine", "william", "austin", "michelle", "ferrari",
    "victoria", "panther", "phoenix", "chester", "martin", "corvette",
    "midnight", "compaq", "blahblah", "marina", "jasper", "cassie",
    "merlin", "wizard", "carlos", "maverick", "yankees", "testing",
    "bandit", "dallas", "sophie", "gandalf", "nothing", "creative",
    "anthony", "silver", "rosebud", "bonnie", "camaro", "butter",
    "marvin", "enter", "arsenal", "animal", "champion", "qazwsx",
    "lucky", "falcon", "genesis", "matrix1", "warrior", "winner",
    "1q2w3e", "1q2w3e4r", "1qaz2wsx", "zaq1zaq1", "abcdef",
    "abcdefg", "abcd1234", "aaaaaa", "111111", "000000", "123123",
    "654321", "asdfgh", "asdfghjkl", "qwertyuiop", "987654321",
    "password2", "password12", "passpass", "test", "test1", "test123",
    "changeme", "changeme1", "admin123", "admin1", "administrator",
    "root", "toor", "guest", "default", "letmein1", "master1",
    "trustno1", "abc1234", "baseball1", "dragon1", "shadow1",
    "qwerty1", "monkey1", "iloveyou1", "sunshine1", "princess1",
    "football1", "soccer1", "batman1", "superman1",
    "corvette1", "ferrari1", "mustang1", "harley1",
    "hockey1", "ranger1", "hunter1", "jordan1",
    "welcome123", "letmein123", "passw0rd1",
    "azerty", "azerty123", "motdepasse", "soleil",
    "carocorp", "marveline",
})

# Patterns de séquences triviales
_REPEATING_PATTERN = re.compile(r"(.)\1{2,}")  # aaa, 111, etc.
_SEQUENTIAL_DIGITS = "0123456789"
_SEQUENTIAL_ALPHA = "abcdefghijklmnopqrstuvwxyz"


def _has_sequential_chars(password: str, min_length: int = 4) -> bool:
    """Détecte les séquences de caractères consécutifs (abc, 123, etc.)."""
    pw_lower = password.lower()
    for seq in (_SEQUENTIAL_DIGITS, _SEQUENTIAL_ALPHA):
        for i in range(len(seq) - min_length + 1):
            if seq[i:i + min_length] in pw_lower:
                return True
    return False


def validate_password(
    password: str,
    role: Optional[str] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Valide un mot de passe selon la politique avancée.

    Args:
        password: Mot de passe à valider
        role: Rôle de l'utilisateur (admin/manager → min 12 chars)
        username: Nom d'utilisateur (ne doit pas être dans le password)
        email: Email (la partie locale ne doit pas être dans le password)

    Returns:
        Tuple (is_valid, error_message). error_message est None si valide.
    """
    # ── Longueur max ──
    if len(password) > PasswordPolicy.MAX_LENGTH:
        return False, f"Password must be at most {PasswordPolicy.MAX_LENGTH} characters long"

    # ── Longueur min (dépend du rôle) ──
    min_length = PasswordPolicy.MIN_LENGTH
    if role and role in PasswordPolicy.ELEVATED_ROLES:
        min_length = PasswordPolicy.ADMIN_MIN_LENGTH

    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"

    # ── Complexité : majuscule, minuscule, chiffre, spécial ──
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    if not any(not c.isalnum() for c in password):
        return False, "Password must contain at least one special character"

    # ── Common passwords ──
    if password.lower() in COMMON_PASSWORDS:
        return False, "This password is too common and easily guessable"

    # ── Contexte : username dans le password ──
    if username and len(username) >= 3:
        if username.lower() in password.lower():
            return False, "Password must not contain your username"

    # ── Contexte : partie locale de l'email dans le password ──
    if email and "@" in email:
        local_part = email.split("@")[0].lower()
        if len(local_part) >= 3 and local_part in password.lower():
            return False, "Password must not contain your email address"

    # ── Séquences répétitives (aaa, 111) ──
    if _REPEATING_PATTERN.search(password):
        return False, "Password must not contain repeating characters (e.g., aaa, 111)"

    # ── Séquences consécutives (1234, abcd) ──
    if _has_sequential_chars(password):
        return False, "Password must not contain sequential characters (e.g., 1234, abcd)"

    return True, None
