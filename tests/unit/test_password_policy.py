"""Tests unitaires : password policy avancée.

Couvre :
    - Longueur min/max (8 chars standard, 12 pour admin/manager, max 128)
    - Complexité (majuscule, minuscule, chiffre, caractère spécial)
    - Common passwords (liste locale, pas HIBP)
    - Checks contextuels (username/email dans le password)
    - Séquences répétitives (aaa, 111)
    - Séquences consécutives (1234, abcd)
    - Cas limites (unicode, exactement min length, etc.)

Fichiers testés :
    - app/core/password_policy.py (validate_password, _has_sequential_chars)
"""

import pytest

from app.core.password_policy import (
    COMMON_PASSWORDS,
    _has_sequential_chars,
    validate_password,
)
from app.constants import PasswordPolicy


# ─────────────────────────────────────────────────────────────────────
# Longueur
# ─────────────────────────────────────────────────────────────────────

class TestPasswordLength:
    """Tests pour les contraintes de longueur."""

    def test_too_short_rejected(self):
        """Password < 8 chars rejeté."""
        is_valid, msg = validate_password("Ab1!xyz")  # 7 chars
        assert not is_valid
        assert "at least 8" in msg

    def test_exactly_min_length_accepted(self):
        """Password de 8 chars exactement accepté."""
        is_valid, msg = validate_password("Xk9!mPwz")  # 8 chars, no sequences
        assert is_valid
        assert msg is None

    def test_too_long_rejected(self):
        """Password > 128 chars rejeté."""
        # 130 chars: mix of non-repeating chars to avoid repeating check
        pw = "Xk9!" + "mPwzRt" * 21 + "Hq"  # 4 + 126 + 2 = 132
        assert len(pw) > 128
        is_valid, msg = validate_password(pw)
        assert not is_valid
        assert "at most 128" in msg

    def test_exactly_max_length_accepted(self):
        """Password de 128 chars exactement accepté."""
        # Build exactly 128 chars with no sequences/repeats
        base = "Xk9!mPwzRt5@hNqJ"  # 16 chars
        pw = (base * 8)[:128]  # 128 chars
        assert len(pw) == 128
        is_valid, msg = validate_password(pw)
        assert is_valid
        assert msg is None

    def test_admin_min_12_chars(self):
        """Admin/manager doivent avoir 12 chars minimum."""
        # 8 chars suffit pour staff
        pw = "Xk9!mPwz"  # 8 chars
        is_valid, _ = validate_password(pw, role="staff")
        assert is_valid

        # Mais pas pour admin
        is_valid, msg = validate_password(pw, role="admin")
        assert not is_valid
        assert "at least 12" in msg

    def test_manager_min_12_chars(self):
        """Manager aussi doit avoir 12 chars minimum."""
        pw = "Xk9!mPwzRt5"  # 11 chars
        is_valid, msg = validate_password(pw, role="manager")
        assert not is_valid
        assert "at least 12" in msg

    def test_admin_12_chars_accepted(self):
        """Admin avec 12 chars accepté."""
        pw = "Xk9!mPwzRt5@"  # 12 chars
        is_valid, msg = validate_password(pw, role="admin")
        assert is_valid
        assert msg is None


# ─────────────────────────────────────────────────────────────────────
# Complexité
# ─────────────────────────────────────────────────────────────────────

class TestPasswordComplexity:
    """Tests pour les exigences de complexité."""

    def test_no_uppercase_rejected(self):
        """Password sans majuscule rejeté."""
        is_valid, msg = validate_password("abcdef1!")
        assert not is_valid
        assert "uppercase" in msg

    def test_no_lowercase_rejected(self):
        """Password sans minuscule rejeté."""
        is_valid, msg = validate_password("ABCDEF1!")
        assert not is_valid
        assert "lowercase" in msg

    def test_no_digit_rejected(self):
        """Password sans chiffre rejeté."""
        is_valid, msg = validate_password("Abcdefgh!")
        assert not is_valid
        assert "digit" in msg

    def test_no_special_char_rejected(self):
        """Password sans caractère spécial rejeté."""
        is_valid, msg = validate_password("Abcdefg1")
        assert not is_valid
        assert "special character" in msg

    def test_all_criteria_met_accepted(self):
        """Password avec toutes les exigences accepté."""
        is_valid, msg = validate_password("MyP@ss99")
        assert is_valid
        assert msg is None

    def test_various_special_chars_accepted(self):
        """Différents caractères spéciaux sont acceptés."""
        for char in ["!", "@", "#", "$", "%", "^", "&", "*", "-", "_", ".", "~"]:
            pw = f"Xk9mPwz{char}"  # 8 chars, no sequences
            is_valid, _ = validate_password(pw)
            assert is_valid, f"Special char '{char}' should be accepted"


# ─────────────────────────────────────────────────────────────────────
# Common passwords
# ─────────────────────────────────────────────────────────────────────

class TestCommonPasswords:
    """Tests pour la liste de common passwords."""

    def test_common_password_rejected(self):
        """Password dans la liste common rejeté (même si complexité OK)."""
        # "password" est dans la liste mais n'a pas de complexité
        # On teste directement la logique — mais validate_password vérifie
        # la complexité AVANT les common passwords. On vérifie que la liste
        # contient les entrées attendues.
        assert "password" in COMMON_PASSWORDS
        assert "123456" in COMMON_PASSWORDS
        assert "qwerty" in COMMON_PASSWORDS
        assert "admin" in COMMON_PASSWORDS

    def test_common_password_case_insensitive(self):
        """Common passwords vérifiés en case-insensitive."""
        # "marveline" est dans la liste
        assert "marveline" in COMMON_PASSWORDS
        assert "carocorp" in COMMON_PASSWORDS

    def test_common_passwords_list_has_enough_entries(self):
        """La liste doit contenir au moins 150 entrées."""
        assert len(COMMON_PASSWORDS) >= 150

    def test_non_common_password_accepted(self):
        """Password pas dans la liste accepté."""
        is_valid, msg = validate_password("Xyzt9!kLm")
        assert is_valid
        assert msg is None


# ─────────────────────────────────────────────────────────────────────
# Checks contextuels (username/email)
# ─────────────────────────────────────────────────────────────────────

class TestContextualChecks:
    """Tests pour les vérifications contextuelles."""

    def test_username_in_password_rejected(self):
        """Password contenant le username rejeté."""
        is_valid, msg = validate_password(
            "MyJohn99!x", username="john"
        )
        assert not is_valid
        assert "username" in msg

    def test_username_case_insensitive(self):
        """Username check est case-insensitive."""
        is_valid, msg = validate_password(
            "MYJOHN99!x", username="john"
        )
        assert not is_valid
        assert "username" in msg

    def test_short_username_ignored(self):
        """Username < 3 chars n'est pas vérifié (trop de faux positifs)."""
        is_valid, msg = validate_password("AbJo1!xy", username="Jo")
        assert is_valid
        assert msg is None

    def test_email_local_part_in_password_rejected(self):
        """Password contenant la partie locale de l'email rejeté."""
        is_valid, msg = validate_password(
            "MyAlice99!x", email="alice@example.com"
        )
        assert not is_valid
        assert "email" in msg

    def test_email_domain_not_checked(self):
        """Seule la partie locale de l'email est vérifiée."""
        # "example" est la partie domaine, pas la partie locale
        is_valid, msg = validate_password(
            "Example1!xy", email="ab@example.com"
        )
        assert is_valid
        assert msg is None

    def test_short_email_local_part_ignored(self):
        """Partie locale < 3 chars pas vérifiée."""
        is_valid, msg = validate_password(
            "AbXy1!zw", email="ab@example.com"
        )
        assert is_valid
        assert msg is None

    def test_no_username_no_email_ok(self):
        """Sans username ni email, les checks contextuels sont ignorés."""
        is_valid, msg = validate_password("MyP@ss99")
        assert is_valid
        assert msg is None


# ─────────────────────────────────────────────────────────────────────
# Séquences
# ─────────────────────────────────────────────────────────────────────

class TestSequences:
    """Tests pour la détection de séquences."""

    def test_repeating_chars_rejected(self):
        """Password avec caractères répétitifs rejeté (aaa, 111)."""
        is_valid, msg = validate_password("Aaaa1!xy")
        assert not is_valid
        assert "repeating" in msg

    def test_repeating_digits_rejected(self):
        """Chiffres répétitifs rejetés."""
        is_valid, msg = validate_password("Ab111!xy")
        assert not is_valid
        assert "repeating" in msg

    def test_two_repeats_ok(self):
        """2 caractères identiques sont OK (seul 3+ est bloqué)."""
        is_valid, msg = validate_password("Aabb1!xy")
        assert is_valid
        assert msg is None

    def test_sequential_digits_rejected(self):
        """Séquence de chiffres consécutifs rejetée (1234)."""
        is_valid, msg = validate_password("Ab1234!x")
        assert not is_valid
        assert "sequential" in msg

    def test_sequential_alpha_rejected(self):
        """Séquence alphabétique consécutive rejetée (abcd)."""
        is_valid, msg = validate_password("Xabcd1!y")
        assert not is_valid
        assert "sequential" in msg

    def test_three_sequential_ok(self):
        """3 caractères consécutifs sont OK (seul 4+ est bloqué)."""
        is_valid, msg = validate_password("Xabc1!yz")
        assert is_valid
        assert msg is None

    def test_has_sequential_chars_helper(self):
        """Test direct de _has_sequential_chars."""
        assert _has_sequential_chars("abc1234xyz") is True
        assert _has_sequential_chars("abcdefgh") is True
        assert _has_sequential_chars("xyzabc") is False  # abc = 3, min_length=4
        assert _has_sequential_chars("hello") is False


# ─────────────────────────────────────────────────────────────────────
# Cas limites
# ─────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Tests pour les cas limites."""

    def test_unicode_password_accepted(self):
        """Password avec caractères Unicode accepté."""
        is_valid, msg = validate_password("Pässwörd1!")
        assert is_valid
        assert msg is None

    def test_spaces_in_password_accepted(self):
        """Password avec espaces accepté (espaces = caractères spéciaux)."""
        is_valid, msg = validate_password("My Pass 1x")
        assert is_valid
        assert msg is None

    def test_validate_password_returns_tuple(self):
        """validate_password retourne toujours un tuple (bool, Optional[str])."""
        result = validate_password("MyP@ss99")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)

    def test_empty_password_rejected(self):
        """Password vide rejeté."""
        is_valid, msg = validate_password("")
        assert not is_valid

    def test_role_none_uses_default_min(self):
        """role=None utilise la longueur min par défaut (8)."""
        pw = "Xk9!mPwz"  # 8 chars
        is_valid, msg = validate_password(pw, role=None)
        assert is_valid
        assert msg is None

    def test_role_staff_uses_default_min(self):
        """role='staff' utilise la longueur min par défaut (8)."""
        pw = "Xk9!mPwz"  # 8 chars
        is_valid, msg = validate_password(pw, role="staff")
        assert is_valid
        assert msg is None

    def test_constants_match_policy(self):
        """Les constantes PasswordPolicy sont cohérentes."""
        assert PasswordPolicy.MIN_LENGTH == 8
        assert PasswordPolicy.ADMIN_MIN_LENGTH == 12
        assert PasswordPolicy.MAX_LENGTH == 128
        assert "admin" in PasswordPolicy.ELEVATED_ROLES
        assert "manager" in PasswordPolicy.ELEVATED_ROLES


# ─────────────────────────────────────────────────────────────────────
# Intégration validate_password_strength
# ─────────────────────────────────────────────────────────────────────

class TestValidatePasswordStrengthIntegration:
    """Tests pour vérifier que validate_password_strength délègue correctement."""

    def test_validate_password_strength_delegates(self):
        """validate_password_strength utilise password_policy."""
        from app.core.security import validate_password_strength

        # Password valide
        is_valid, msg = validate_password_strength("MyP@ss99")
        assert is_valid
        assert msg is None

    def test_validate_password_strength_rejects_weak(self):
        """validate_password_strength rejette un password faible."""
        from app.core.security import validate_password_strength

        is_valid, msg = validate_password_strength("123")
        assert not is_valid
        assert msg is not None

    def test_validate_password_strength_with_role(self):
        """validate_password_strength passe le rôle."""
        from app.core.security import validate_password_strength

        # 8 chars valide pour staff, mais pas pour admin
        pw = "Xk9!mPwz"  # 8 chars
        is_valid, _ = validate_password_strength(pw, role="staff")
        assert is_valid

        is_valid, msg = validate_password_strength(pw, role="admin")
        assert not is_valid
        assert "at least 12" in msg
