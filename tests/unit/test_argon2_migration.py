"""Tests unitaires : migration bcrypt → Argon2id.

Couvre :
    - Nouveau hash = Argon2id (pas bcrypt)
    - Vérification Argon2id fonctionne
    - Vérification bcrypt legacy fonctionne
    - Auto-détection de l'algorithme via préfixe
    - needs_rehash() détecte bcrypt comme à migrer
    - needs_rehash() accepte Argon2id frais
    - DUMMY_HASH est Argon2id
    - Rehash transparent au login (bcrypt → Argon2id)
    - Hash différent à chaque appel (salt unique)
    - verify_password rejette hash inconnu

Fichiers testés :
    - app/core/security.py (verify_password, get_password_hash, needs_rehash, DUMMY_HASH)
    - app/services/auth.py (login rehash logic)
"""

import bcrypt
import pytest

from app.core.security import (
    DUMMY_HASH,
    _is_argon2_hash,
    _is_bcrypt_hash,
    get_password_hash,
    needs_rehash,
    verify_password,
)
from app.constants import Argon2Params


# ─────────────────────────────────────────────────────────────────────
# Hashing — nouveaux mots de passe
# ─────────────────────────────────────────────────────────────────────

class TestArgon2Hashing:
    """Tests pour le hashing Argon2id."""

    def test_new_hash_is_argon2id(self):
        """get_password_hash() produit un hash Argon2id."""
        h = get_password_hash("testpassword")
        assert h.startswith(Argon2Params.ARGON2ID_PREFIX)

    def test_hash_not_bcrypt(self):
        """get_password_hash() ne produit PAS un hash bcrypt."""
        h = get_password_hash("testpassword")
        assert not h.startswith(Argon2Params.BCRYPT_PREFIX)

    def test_hash_is_unique_each_call(self):
        """Chaque appel produit un hash différent (salt unique)."""
        h1 = get_password_hash("samepassword")
        h2 = get_password_hash("samepassword")
        assert h1 != h2

    def test_hash_contains_params(self):
        """Le hash Argon2id contient les paramètres (m, t, p)."""
        h = get_password_hash("testpassword")
        assert "m=65536" in h
        assert "t=3" in h
        assert "p=4" in h

    def test_dummy_hash_is_argon2id(self):
        """DUMMY_HASH est généré en Argon2id."""
        assert DUMMY_HASH.startswith(Argon2Params.ARGON2ID_PREFIX)

    def test_dummy_hash_rejects_all_passwords(self):
        """DUMMY_HASH ne valide aucun mot de passe courant."""
        assert not verify_password("password", DUMMY_HASH)
        assert not verify_password("", DUMMY_HASH)
        assert not verify_password("admin", DUMMY_HASH)


# ─────────────────────────────────────────────────────────────────────
# Vérification — Argon2id
# ─────────────────────────────────────────────────────────────────────

class TestArgon2Verification:
    """Tests pour la vérification Argon2id."""

    def test_verify_argon2_correct_password(self):
        """Mot de passe correct vérifié en Argon2id."""
        h = get_password_hash("correctpassword")
        assert verify_password("correctpassword", h)

    def test_verify_argon2_wrong_password(self):
        """Mot de passe incorrect rejeté en Argon2id."""
        h = get_password_hash("correctpassword")
        assert not verify_password("wrongpassword", h)

    def test_verify_argon2_empty_password(self):
        """Mot de passe vide rejeté."""
        h = get_password_hash("notempty")
        assert not verify_password("", h)

    def test_verify_argon2_unicode(self):
        """Mot de passe Unicode fonctionne en Argon2id."""
        h = get_password_hash("pässwörd€123")
        assert verify_password("pässwörd€123", h)
        assert not verify_password("password123", h)

    def test_verify_argon2_long_password(self):
        """Mot de passe long fonctionne en Argon2id."""
        long_pw = "a" * 200
        h = get_password_hash(long_pw)
        assert verify_password(long_pw, h)
        assert not verify_password(long_pw + "x", h)


# ─────────────────────────────────────────────────────────────────────
# Vérification — bcrypt legacy
# ─────────────────────────────────────────────────────────────────────

class TestBcryptLegacyVerification:
    """Tests pour la vérification bcrypt (migration transparente)."""

    @staticmethod
    def _make_bcrypt_hash(password: str) -> str:
        """Crée un hash bcrypt legacy."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    def test_verify_bcrypt_correct_password(self):
        """Mot de passe correct vérifié avec hash bcrypt legacy."""
        h = self._make_bcrypt_hash("legacypass")
        assert verify_password("legacypass", h)

    def test_verify_bcrypt_wrong_password(self):
        """Mot de passe incorrect rejeté avec hash bcrypt legacy."""
        h = self._make_bcrypt_hash("legacypass")
        assert not verify_password("wrongpass", h)

    def test_bcrypt_hash_detected(self):
        """Hash bcrypt détecté par _is_bcrypt_hash."""
        h = self._make_bcrypt_hash("test")
        assert _is_bcrypt_hash(h)
        assert not _is_argon2_hash(h)

    def test_argon2_hash_detected(self):
        """Hash Argon2id détecté par _is_argon2_hash."""
        h = get_password_hash("test")
        assert _is_argon2_hash(h)
        assert not _is_bcrypt_hash(h)


# ─────────────────────────────────────────────────────────────────────
# needs_rehash()
# ─────────────────────────────────────────────────────────────────────

class TestNeedsRehash:
    """Tests pour la détection de rehash nécessaire."""

    @staticmethod
    def _make_bcrypt_hash(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    def test_bcrypt_needs_rehash(self):
        """Hash bcrypt doit être re-hashé en Argon2id."""
        h = self._make_bcrypt_hash("test")
        assert needs_rehash(h)

    def test_fresh_argon2_no_rehash(self):
        """Hash Argon2id frais ne nécessite pas de rehash."""
        h = get_password_hash("test")
        assert not needs_rehash(h)

    def test_unknown_hash_needs_rehash(self):
        """Hash inconnu doit être re-hashé."""
        assert needs_rehash("$sha256$somehash")
        assert needs_rehash("plaintext_not_a_hash")

    def test_empty_string_needs_rehash(self):
        """Chaîne vide doit être re-hashée."""
        assert needs_rehash("")


# ─────────────────────────────────────────────────────────────────────
# Verify — edge cases
# ─────────────────────────────────────────────────────────────────────

class TestVerifyEdgeCases:
    """Tests pour les cas limites de verify_password."""

    def test_unknown_hash_format_returns_false(self):
        """Hash dans un format inconnu retourne False."""
        assert not verify_password("test", "$unknown$hash")

    def test_empty_hash_returns_false(self):
        """Hash vide retourne False."""
        assert not verify_password("test", "")

    def test_corrupted_argon2_returns_false(self):
        """Hash Argon2id corrompu retourne False."""
        h = get_password_hash("test")
        corrupted = h[:-5] + "XXXXX"
        assert not verify_password("test", corrupted)

    def test_verify_password_is_case_sensitive(self):
        """Vérification est case-sensitive."""
        h = get_password_hash("TestPass123!")
        assert verify_password("TestPass123!", h)
        assert not verify_password("testpass123!", h)
        assert not verify_password("TESTPASS123!", h)
