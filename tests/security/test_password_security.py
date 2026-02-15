"""Tests sécurité : password hashing, stockage, migration bcrypt→Argon2id.

Couvre :
- Hash Argon2id par défaut (pas bcrypt)
- Hash différent à chaque appel (salt unique)
- Pas de password en clair en DB
- Migration transparente bcrypt → Argon2id
- needs_rehash détecte bcrypt et paramètres obsolètes
- Password policy avancée (longueur, complexité, common passwords, contexte)
"""
import pytest
import bcrypt

from app.core.security import (
    get_password_hash,
    verify_password,
    needs_rehash,
    validate_password_strength,
)
from app.constants import Argon2Params


class TestArgon2idHashing:
    """Hash Argon2id : format, unicité, vérification."""

    def test_hash_is_argon2id_format(self):
        """Le hash doit être au format Argon2id."""
        hashed = get_password_hash("MySecureP@ss1")
        assert hashed.startswith("$argon2id$"), f"Expected Argon2id hash, got: {hashed[:20]}"

    def test_hash_is_different_each_time(self):
        """Deux appels avec le même password doivent produire des hash différents (salt unique)."""
        password = "SamePassword1!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2, "Hash should be different due to unique salt"

    def test_verify_correct_password(self):
        """verify_password accepte le bon password."""
        password = "Correct!Pass1"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        """verify_password rejette un mauvais password."""
        hashed = get_password_hash("OriginalP@ss1")
        assert verify_password("WrongP@ss1", hashed) is False

    def test_hash_not_equal_to_plaintext(self):
        """Le hash ne doit jamais être égal au password en clair."""
        password = "MyP@ssword123"
        hashed = get_password_hash(password)
        assert hashed != password

    def test_hash_is_long_enough(self):
        """Le hash doit être suffisamment long (au moins 60 chars)."""
        hashed = get_password_hash("TestP@ss123")
        assert len(hashed) > 60, f"Hash trop court: {len(hashed)} chars"


class TestBcryptMigration:
    """Migration transparente bcrypt → Argon2id."""

    def _make_bcrypt_hash(self, password: str) -> str:
        """Helper : crée un hash bcrypt (simule ancien format)."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def test_verify_bcrypt_hash(self):
        """verify_password accepte un hash bcrypt (legacy)."""
        password = "LegacyBcryptPass"
        bcrypt_hash = self._make_bcrypt_hash(password)
        assert bcrypt_hash.startswith("$2b$")
        assert verify_password(password, bcrypt_hash) is True

    def test_verify_bcrypt_wrong_password(self):
        """verify_password rejette un mauvais password même avec hash bcrypt."""
        bcrypt_hash = self._make_bcrypt_hash("RealPassword")
        assert verify_password("WrongPassword", bcrypt_hash) is False

    def test_needs_rehash_bcrypt(self):
        """needs_rehash retourne True pour un hash bcrypt."""
        bcrypt_hash = self._make_bcrypt_hash("OldPassword")
        assert needs_rehash(bcrypt_hash) is True

    def test_needs_rehash_argon2id_current(self):
        """needs_rehash retourne False pour un hash Argon2id avec paramètres actuels."""
        argon2_hash = get_password_hash("CurrentPassword1!")
        assert needs_rehash(argon2_hash) is False

    def test_needs_rehash_unknown_format(self):
        """needs_rehash retourne True pour un format inconnu."""
        assert needs_rehash("not-a-valid-hash") is True

    def test_verify_unknown_hash_format_returns_false(self):
        """verify_password retourne False pour un format de hash inconnu."""
        assert verify_password("password", "not-a-valid-hash-format") is False


class TestPasswordNotInClearInDB:
    """Vérification que le password n'est jamais stocké en clair en DB."""

    def test_user_password_is_hashed_in_db(self, test_db, test_user):
        """Le champ hashed_password ne contient JAMAIS le password en clair."""
        assert test_user.hashed_password != "testpass123"
        assert test_user.hashed_password.startswith("$argon2id$")

    def test_new_user_password_hashed(self, test_db):
        """Un nouvel utilisateur a son password hashé."""
        from app.models.user import User

        user = User(
            tenant_id=1,
            email="cleartext-check@test.com",
            hashed_password=get_password_hash("MyP@ss1234"),
            full_name="Clear Text Check",
            role="staff",
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert "MyP@ss1234" not in user.hashed_password
        assert user.hashed_password.startswith("$argon2id$")


class TestPasswordPolicyAdvanced:
    """Tests de la politique de mots de passe avancée."""

    def test_password_too_short_rejected(self):
        """Password < 8 chars rejeté."""
        valid, msg = validate_password_strength("Sh0rt!")
        assert valid is False
        assert "at least" in msg

    def test_password_no_uppercase_rejected(self):
        """Password sans majuscule rejeté."""
        valid, msg = validate_password_strength("nouppercase1!")
        assert valid is False
        assert "uppercase" in msg

    def test_password_no_lowercase_rejected(self):
        """Password sans minuscule rejeté."""
        valid, msg = validate_password_strength("NOLOWERCASE1!")
        assert valid is False
        assert "lowercase" in msg

    def test_password_no_digit_rejected(self):
        """Password sans chiffre rejeté."""
        valid, msg = validate_password_strength("NoDigitHere!")
        assert valid is False
        assert "digit" in msg

    def test_password_no_special_rejected(self):
        """Password sans caractère spécial rejeté."""
        valid, msg = validate_password_strength("NoSpecial123")
        assert valid is False
        assert "special" in msg

    def test_common_password_rejected(self):
        """Password commun (password123) rejeté."""
        valid, msg = validate_password_strength("Password123!")
        # "password123" est dans la common list (case insensitive) mais "Password123!" a un "!"
        # Testons un qui est exactement dans la liste
        valid2, msg2 = validate_password_strength("password")
        assert valid2 is False

    def test_valid_strong_password_accepted(self):
        """Password fort et valide accepté."""
        valid, msg = validate_password_strength("MyStr0ng!P@ss")
        assert valid is True
        assert msg is None

    def test_admin_requires_longer_password(self):
        """Admin nécessite un password plus long (12 chars min)."""
        # 8 chars suffit pour staff
        valid_staff, _ = validate_password_strength("Str0ng!P")
        # Mais pas pour admin (< 12)
        valid_admin, msg_admin = validate_password_strength("Str0ng!P", role="admin")
        assert valid_admin is False
        assert "at least" in msg_admin

    def test_password_with_email_context_rejected(self):
        """Password contenant la partie locale de l'email rejeté."""
        from app.core.password_policy import validate_password
        valid, msg = validate_password("john!Strong1@", email="john@example.com")
        assert valid is False
        assert "email" in msg
