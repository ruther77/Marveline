"""Tests unitaires pour app.services.mfa — MFAService TOTP.

Vérifie :
    - setup_totp : génération secret, URI, recovery codes, chiffrement DB
    - verify_setup : activation device avec bon code TOTP
    - verify_totp : vérification login avec anti-replay
    - verify_recovery_code : usage unique, décrémentation
    - disable_mfa : suppression device
    - is_mfa_enabled / get_recovery_codes_count
    - create_mfa_session / validate_mfa_session (Redis)
    - Isolation multi-tenant
"""
import json
import time
import pytest
import pyotp

from app.services.mfa import MFAService, mfa_service
from app.models.mfa import MFADevice
from app.constants import MFAConfig
from app.core.crypto import decrypt_totp_secret


@pytest.fixture
def svc():
    """Instance fraîche de MFAService (pas le singleton)."""
    return MFAService()


# ========== setup_totp ==========

class TestSetupTotp:
    """Tests pour MFAService.setup_totp."""

    def test_setup_returns_tuple_of_three(self, svc, test_db, test_user):
        """setup_totp retourne (secret, uri, recovery_codes)."""
        secret, uri, codes = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert isinstance(secret, str)
        assert isinstance(uri, str)
        assert isinstance(codes, list)

    def test_setup_secret_is_base32(self, svc, test_db, test_user):
        """Le secret retourné est un string base32 valide."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        # pyotp.TOTP accepte le secret sans erreur
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert len(code) == 6

    def test_setup_uri_contains_otpauth(self, svc, test_db, test_user):
        """L'URI de provisioning commence par otpauth://."""
        _, uri, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert uri.startswith("otpauth://totp/")

    def test_setup_uri_contains_issuer(self, svc, test_db, test_user):
        """L'URI contient le nom de l'issuer (Marveline)."""
        _, uri, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert MFAConfig.ISSUER_NAME in uri

    def test_setup_generates_correct_number_of_recovery_codes(self, svc, test_db, test_user):
        """Nombre de recovery codes = MFAConfig.RECOVERY_CODE_COUNT."""
        _, _, codes = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert len(codes) == MFAConfig.RECOVERY_CODE_COUNT

    def test_setup_recovery_codes_are_unique(self, svc, test_db, test_user):
        """Chaque recovery code est unique."""
        _, _, codes = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert len(set(codes)) == len(codes)

    def test_setup_creates_device_in_db(self, svc, test_db, test_user):
        """Un MFADevice est créé en DB (non activé)."""
        svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)
        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()
        assert device is not None
        assert device.is_enabled is False

    def test_setup_secret_encrypted_in_db(self, svc, test_db, test_user):
        """Le secret est chiffré en DB (pas en clair)."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()

        # Le champ brut ne contient PAS le secret en clair
        assert secret.encode("utf-8") not in device.encrypted_secret
        # Mais on peut le déchiffrer
        assert decrypt_totp_secret(device.encrypted_secret) == secret

    def test_setup_recovery_codes_hashed_in_db(self, svc, test_db, test_user):
        """Les recovery codes sont hashés en DB (pas en clair)."""
        _, _, codes = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()

        hashes = json.loads(device.recovery_codes_hash)
        assert len(hashes) == len(codes)
        # Les hashes commencent par $2b$ (bcrypt)
        for h in hashes:
            assert h.startswith("$2b$")
        # Aucun code en clair dans le JSON
        for code in codes:
            assert code not in device.recovery_codes_hash

    def test_setup_replaces_pending_device(self, svc, test_db, test_user):
        """Si un device pending existe, il est remplacé."""
        svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)
        # Deuxième setup → doit remplacer le premier
        secret2, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        devices = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).all()
        assert len(devices) == 1
        assert decrypt_totp_secret(devices[0].encrypted_secret) == secret2

    def test_setup_raises_if_mfa_already_enabled(self, svc, test_db, test_user):
        """ValueError si MFA est déjà activé."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        # Activer le device manuellement
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        code = totp.now()
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, code)

        # Deuxième setup doit échouer
        with pytest.raises(ValueError, match="already enabled"):
            svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)


# ========== verify_setup ==========

class TestVerifySetup:
    """Tests pour MFAService.verify_setup."""

    def test_verify_setup_with_valid_code(self, svc, test_db, test_user):
        """Code TOTP valide → True et device activé."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        code = totp.now()

        result = svc.verify_setup(test_db, test_user.id, test_user.tenant_id, code)
        assert result is True

        # Device est maintenant activé
        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()
        assert device.is_enabled is True

    def test_verify_setup_sets_last_totp_window(self, svc, test_db, test_user):
        """Après verify_setup, last_totp_window est renseigné."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, totp.now())

        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()
        assert device.last_totp_window is not None
        assert device.last_totp_window > 0

    def test_verify_setup_invalid_code_raises(self, svc, test_db, test_user):
        """Code TOTP invalide → ValueError."""
        svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)

        with pytest.raises(ValueError, match="Invalid TOTP code"):
            svc.verify_setup(test_db, test_user.id, test_user.tenant_id, "000000")

    def test_verify_setup_no_pending_device_raises(self, svc, test_db, test_user):
        """Pas de device pending → ValueError."""
        with pytest.raises(ValueError, match="No pending MFA setup found"):
            svc.verify_setup(test_db, test_user.id, test_user.tenant_id, "123456")


# ========== verify_totp ==========

class TestVerifyTotp:
    """Tests pour MFAService.verify_totp (login step 2)."""

    def _setup_and_enable(self, svc, db, user):
        """Helper : setup + enable MFA, retourne le secret."""
        secret, _, _ = svc.setup_totp(db, user.id, user.tenant_id, user.email)
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(db, user.id, user.tenant_id, totp.now())
        return secret

    def test_verify_totp_valid_code(self, svc, test_db, test_user):
        """Code TOTP valide → True."""
        secret = self._setup_and_enable(svc, test_db, test_user)

        # Avancer le last_totp_window pour éviter l'anti-replay
        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()
        device.last_totp_window = device.last_totp_window - 2
        test_db.flush()

        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        result = svc.verify_totp(test_db, test_user.id, test_user.tenant_id, totp.now())
        assert result is True

    def test_verify_totp_invalid_code_raises(self, svc, test_db, test_user):
        """Code TOTP invalide → ValueError."""
        self._setup_and_enable(svc, test_db, test_user)

        with pytest.raises(ValueError, match="Invalid TOTP code"):
            svc.verify_totp(test_db, test_user.id, test_user.tenant_id, "000000")

    def test_verify_totp_anti_replay(self, svc, test_db, test_user):
        """Même code réutilisé dans la même fenêtre → anti-replay."""
        secret = self._setup_and_enable(svc, test_db, test_user)

        # Reset last_totp_window pour permettre la première vérification
        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()
        device.last_totp_window = device.last_totp_window - 2
        test_db.flush()

        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        code = totp.now()

        # Premier usage → OK
        svc.verify_totp(test_db, test_user.id, test_user.tenant_id, code)

        # Deuxième usage même fenêtre → anti-replay
        with pytest.raises(ValueError, match="anti-replay"):
            svc.verify_totp(test_db, test_user.id, test_user.tenant_id, code)

    def test_verify_totp_not_enabled_raises(self, svc, test_db, test_user):
        """MFA pas activé → ValueError."""
        with pytest.raises(ValueError, match="not enabled"):
            svc.verify_totp(test_db, test_user.id, test_user.tenant_id, "123456")


# ========== verify_recovery_code ==========

class TestVerifyRecoveryCode:
    """Tests pour MFAService.verify_recovery_code."""

    def _setup_and_enable(self, svc, db, user):
        """Helper : setup + enable MFA, retourne (secret, recovery_codes)."""
        secret, _, codes = svc.setup_totp(db, user.id, user.tenant_id, user.email)
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(db, user.id, user.tenant_id, totp.now())
        return secret, codes

    def test_recovery_code_valid(self, svc, test_db, test_user):
        """Recovery code valide → True."""
        _, codes = self._setup_and_enable(svc, test_db, test_user)
        result = svc.verify_recovery_code(
            test_db, test_user.id, test_user.tenant_id, codes[0]
        )
        assert result is True

    def test_recovery_code_single_use(self, svc, test_db, test_user):
        """Un recovery code ne peut être utilisé qu'une fois."""
        _, codes = self._setup_and_enable(svc, test_db, test_user)
        svc.verify_recovery_code(test_db, test_user.id, test_user.tenant_id, codes[0])

        with pytest.raises(ValueError, match="Invalid recovery code"):
            svc.verify_recovery_code(test_db, test_user.id, test_user.tenant_id, codes[0])

    def test_recovery_code_decrements_count(self, svc, test_db, test_user):
        """Utiliser un code décrémente le compteur."""
        _, codes = self._setup_and_enable(svc, test_db, test_user)
        initial_count = svc.get_recovery_codes_count(
            test_db, test_user.id, test_user.tenant_id
        )
        svc.verify_recovery_code(test_db, test_user.id, test_user.tenant_id, codes[0])
        new_count = svc.get_recovery_codes_count(
            test_db, test_user.id, test_user.tenant_id
        )
        assert new_count == initial_count - 1

    def test_recovery_code_invalid_raises(self, svc, test_db, test_user):
        """Recovery code invalide → ValueError."""
        self._setup_and_enable(svc, test_db, test_user)

        with pytest.raises(ValueError, match="Invalid recovery code"):
            svc.verify_recovery_code(
                test_db, test_user.id, test_user.tenant_id, "not_a_real_code"
            )

    def test_all_recovery_codes_work(self, svc, test_db, test_user):
        """Tous les recovery codes générés sont valides (un par un)."""
        _, codes = self._setup_and_enable(svc, test_db, test_user)
        for code in codes:
            result = svc.verify_recovery_code(
                test_db, test_user.id, test_user.tenant_id, code
            )
            assert result is True

        # Après tous les codes, aucun ne reste
        assert svc.get_recovery_codes_count(
            test_db, test_user.id, test_user.tenant_id
        ) == 0

    def test_no_recovery_codes_raises(self, svc, test_db, test_user):
        """Plus de recovery codes → ValueError."""
        _, codes = self._setup_and_enable(svc, test_db, test_user)
        # Consommer tous les codes
        for code in codes:
            svc.verify_recovery_code(test_db, test_user.id, test_user.tenant_id, code)

        with pytest.raises(ValueError, match="No recovery codes available"):
            svc.verify_recovery_code(
                test_db, test_user.id, test_user.tenant_id, "any_code"
            )

    def test_recovery_code_mfa_not_enabled_raises(self, svc, test_db, test_user):
        """MFA pas activé → ValueError."""
        with pytest.raises(ValueError, match="not enabled"):
            svc.verify_recovery_code(
                test_db, test_user.id, test_user.tenant_id, "any_code"
            )


# ========== disable_mfa ==========

class TestDisableMfa:
    """Tests pour MFAService.disable_mfa."""

    def test_disable_removes_device(self, svc, test_db, test_user):
        """disable_mfa supprime le device de la DB."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, totp.now())

        result = svc.disable_mfa(test_db, test_user.id, test_user.tenant_id)
        assert result is True

        device = test_db.query(MFADevice).filter(
            MFADevice.user_id == test_user.id
        ).first()
        assert device is None

    def test_disable_no_device_raises(self, svc, test_db, test_user):
        """Pas de device → ValueError."""
        with pytest.raises(ValueError, match="not enabled"):
            svc.disable_mfa(test_db, test_user.id, test_user.tenant_id)

    def test_disable_pending_device_also_works(self, svc, test_db, test_user):
        """disable_mfa supprime aussi un device pending (non activé)."""
        svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)
        result = svc.disable_mfa(test_db, test_user.id, test_user.tenant_id)
        assert result is True


# ========== is_mfa_enabled / get_recovery_codes_count ==========

class TestMfaStatus:
    """Tests pour is_mfa_enabled et get_recovery_codes_count."""

    def test_is_mfa_enabled_false_by_default(self, svc, test_db, test_user):
        """Pas de device → False."""
        assert svc.is_mfa_enabled(test_db, test_user.id, test_user.tenant_id) is False

    def test_is_mfa_enabled_false_for_pending(self, svc, test_db, test_user):
        """Device pending (non activé) → False."""
        svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)
        assert svc.is_mfa_enabled(test_db, test_user.id, test_user.tenant_id) is False

    def test_is_mfa_enabled_true_after_verify(self, svc, test_db, test_user):
        """Device activé → True."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, totp.now())

        assert svc.is_mfa_enabled(test_db, test_user.id, test_user.tenant_id) is True

    def test_recovery_count_zero_by_default(self, svc, test_db, test_user):
        """Pas de device → 0 codes."""
        assert svc.get_recovery_codes_count(
            test_db, test_user.id, test_user.tenant_id
        ) == 0

    def test_recovery_count_after_setup(self, svc, test_db, test_user):
        """Après setup + activation → RECOVERY_CODE_COUNT codes."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, totp.now())

        assert svc.get_recovery_codes_count(
            test_db, test_user.id, test_user.tenant_id
        ) == MFAConfig.RECOVERY_CODE_COUNT


# ========== MFA Session Tokens (Redis) ==========

class TestMfaSession:
    """Tests pour create_mfa_session / validate_mfa_session (Redis)."""

    def test_create_returns_token_string(self, svc):
        """create_mfa_session retourne un string non vide."""
        token = svc.create_mfa_session(
            user_id=1, tenant_id=1, email="test@test.com",
            role="staff", ip_address="127.0.0.1"
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_validate_returns_data(self, svc):
        """validate_mfa_session retourne les données de l'utilisateur."""
        token = svc.create_mfa_session(
            user_id=42, tenant_id=1, email="mfa@test.com",
            role="admin", ip_address="10.0.0.1"
        )
        data = svc.validate_mfa_session(token)
        assert data is not None
        assert data["user_id"] == 42
        assert data["tenant_id"] == 1
        assert data["email"] == "mfa@test.com"
        assert data["role"] == "admin"
        assert data["ip_address"] == "10.0.0.1"

    def test_validate_single_use(self, svc):
        """Le token est consommé après la première validation (single-use)."""
        token = svc.create_mfa_session(
            user_id=1, tenant_id=1, email="test@test.com",
            role="staff", ip_address="127.0.0.1"
        )
        # Première utilisation → OK
        data = svc.validate_mfa_session(token)
        assert data is not None

        # Deuxième utilisation → None (consommé)
        data2 = svc.validate_mfa_session(token)
        assert data2 is None

    def test_validate_invalid_token(self, svc):
        """Token inexistant → None."""
        data = svc.validate_mfa_session("nonexistent_token_xyz")
        assert data is None

    def test_each_token_is_unique(self, svc):
        """Deux appels create_mfa_session → tokens différents."""
        t1 = svc.create_mfa_session(
            user_id=1, tenant_id=1, email="a@b.com",
            role="staff", ip_address="1.1.1.1"
        )
        t2 = svc.create_mfa_session(
            user_id=1, tenant_id=1, email="a@b.com",
            role="staff", ip_address="1.1.1.1"
        )
        assert t1 != t2


# ========== Isolation multi-tenant ==========

class TestMultiTenantIsolation:
    """Tests d'isolation multi-tenant pour MFA."""

    def test_setup_isolated_per_tenant(self, svc, test_db, test_user, test_user_tenant2):
        """Chaque tenant a son propre MFA device."""
        svc.setup_totp(test_db, test_user.id, test_user.tenant_id, test_user.email)
        svc.setup_totp(
            test_db, test_user_tenant2.id, test_user_tenant2.tenant_id,
            test_user_tenant2.email
        )

        devices = test_db.query(MFADevice).all()
        assert len(devices) == 2

    def test_verify_totp_wrong_tenant_raises(self, svc, test_db, test_user, test_user_tenant2):
        """Vérification TOTP avec le mauvais tenant_id → erreur."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, totp.now())

        # Tenter verify_totp avec tenant_id=2 → MFA pas activé pour ce tenant
        with pytest.raises(ValueError, match="not enabled"):
            svc.verify_totp(
                test_db, test_user.id, test_user_tenant2.tenant_id, totp.now()
            )

    def test_is_mfa_enabled_cross_tenant(self, svc, test_db, test_user, test_user_tenant2):
        """is_mfa_enabled ne voit pas les devices d'un autre tenant."""
        secret, _, _ = svc.setup_totp(
            test_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        svc.verify_setup(test_db, test_user.id, test_user.tenant_id, totp.now())

        # Tenant 1 → True
        assert svc.is_mfa_enabled(test_db, test_user.id, test_user.tenant_id) is True
        # Tenant 2 pour le même user_id → False
        assert svc.is_mfa_enabled(test_db, test_user.id, test_user_tenant2.tenant_id) is False


# ========== Singleton ==========

class TestSingleton:
    """Tests pour le singleton mfa_service."""

    def test_singleton_exists(self):
        """Le singleton mfa_service est une instance de MFAService."""
        assert isinstance(mfa_service, MFAService)

    def test_no_class_variables_leak(self):
        """MFAService n'a pas de variables de classe mutables (fix ancien bug)."""
        # Vérifier qu'il n'y a pas de _memory_attempts, _attempts, etc.
        class_attrs = {
            k: v for k, v in MFAService.__dict__.items()
            if not k.startswith("__") and not callable(v)
        }
        # Seules les méthodes et staticmethod doivent exister
        for name, val in class_attrs.items():
            assert not isinstance(val, (list, dict, set)), (
                f"MFAService a une variable de classe mutable: {name}"
            )
