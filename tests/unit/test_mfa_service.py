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

Note : MFAService est 100% async. Les tests utilisent la fixture `async_db`
(AsyncSession) pour les appels service. Les fixtures `test_user` /
`test_user_tenant2` (sync, commit réel) seedent Account + TenantMembership
visibles par async_db (même DB physique, connexion distincte).
"""
import json
import time
import pytest
import pyotp
from sqlalchemy import select

from app.services.mfa import MFAService, mfa_service
from app.models.mfa import MFADevice
from app.constants import MFAConfig
from app.core.crypto import decrypt_totp_secret


@pytest.fixture
def svc():
    """Instance fraîche de MFAService (pas le singleton)."""
    return MFAService()


async def _get_device(async_db, user_id):
    """Helper : récupère le MFADevice d'un user via sa membership."""
    from app.models.tenant_membership import TenantMembership

    result = await async_db.execute(
        select(MFADevice)
        .join(TenantMembership, MFADevice.membership_id == TenantMembership.id)
        .filter(TenantMembership.account_id == user_id)
    )
    return result.scalars().first()


async def _get_all_devices(async_db):
    """Helper : récupère tous les MFADevice."""
    result = await async_db.execute(select(MFADevice))
    return result.scalars().all()


# ========== setup_totp ==========

class TestSetupTotp:
    """Tests pour MFAService.setup_totp."""

    async def test_setup_returns_tuple_of_three(self, svc, async_db, test_user):
        """setup_totp retourne (secret, uri, recovery_codes)."""
        secret, uri, codes = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert isinstance(secret, str)
        assert isinstance(uri, str)
        assert isinstance(codes, list)

    async def test_setup_secret_is_base32(self, svc, async_db, test_user):
        """Le secret retourné est un string base32 valide."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        # pyotp.TOTP accepte le secret sans erreur
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert len(code) == 6

    async def test_setup_uri_contains_otpauth(self, svc, async_db, test_user):
        """L'URI de provisioning commence par otpauth://."""
        _, uri, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert uri.startswith("otpauth://totp/")

    async def test_setup_uri_contains_issuer(self, svc, async_db, test_user):
        """L'URI contient le nom de l'issuer (Marveline)."""
        _, uri, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert MFAConfig.ISSUER_NAME in uri

    async def test_setup_generates_correct_number_of_recovery_codes(self, svc, async_db, test_user):
        """Nombre de recovery codes = MFAConfig.RECOVERY_CODE_COUNT."""
        _, _, codes = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert len(codes) == MFAConfig.RECOVERY_CODE_COUNT

    async def test_setup_recovery_codes_are_unique(self, svc, async_db, test_user):
        """Chaque recovery code est unique."""
        _, _, codes = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        assert len(set(codes)) == len(codes)

    async def test_setup_creates_device_in_db(self, svc, async_db, test_user):
        """Un MFADevice est créé en DB (non activé)."""
        await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)
        device = await _get_device(async_db, test_user.id)
        assert device is not None
        assert device.is_enabled is False

    async def test_setup_secret_encrypted_in_db(self, svc, async_db, test_user):
        """Le secret est chiffré en DB (pas en clair)."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        device = await _get_device(async_db, test_user.id)

        # Le champ brut ne contient PAS le secret en clair
        assert secret.encode("utf-8") not in device.encrypted_secret
        # Mais on peut le déchiffrer (envelope encryption v2 : ct + nonce + encrypted_dek)
        assert decrypt_totp_secret(
            device.encrypted_secret,
            device.totp_secret_nonce,
            device.totp_encrypted_dek,
        ) == secret

    async def test_setup_recovery_codes_hashed_in_db(self, svc, async_db, test_user):
        """Les recovery codes sont hashés en DB (pas en clair)."""
        _, _, codes = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        device = await _get_device(async_db, test_user.id)

        hashes = json.loads(device.recovery_codes_hash)
        assert len(hashes) == len(codes)
        # Les hashes commencent par $2b$ (bcrypt)
        for h in hashes:
            assert h.startswith("$2b$")
        # Aucun code en clair dans le JSON
        for code in codes:
            assert code not in device.recovery_codes_hash

    async def test_setup_replaces_pending_device(self, svc, async_db, test_user):
        """Si un device pending existe, il est remplacé."""
        await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)
        # Deuxième setup → doit remplacer le premier
        secret2, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        devices = await _get_all_devices(async_db)
        assert len(devices) == 1
        assert decrypt_totp_secret(
            devices[0].encrypted_secret,
            devices[0].totp_secret_nonce,
            devices[0].totp_encrypted_dek,
        ) == secret2

    async def test_setup_raises_if_mfa_already_enabled(self, svc, async_db, test_user):
        """ValueError si MFA est déjà activé."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        # Activer le device manuellement
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        code = totp.now()
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, code)

        # Deuxième setup doit échouer
        with pytest.raises(ValueError, match="already enabled"):
            await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)


# ========== verify_setup ==========

class TestVerifySetup:
    """Tests pour MFAService.verify_setup."""

    async def test_verify_setup_with_valid_code(self, svc, async_db, test_user):
        """Code TOTP valide → True et device activé."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        code = totp.now()

        result = await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, code)
        assert result is True

        # Device est maintenant activé
        device = await _get_device(async_db, test_user.id)
        assert device.is_enabled is True

    async def test_verify_setup_sets_last_totp_window(self, svc, async_db, test_user):
        """Après verify_setup, last_totp_window est renseigné."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, totp.now())

        device = await _get_device(async_db, test_user.id)
        assert device.last_totp_window is not None
        assert device.last_totp_window > 0

    async def test_verify_setup_invalid_code_raises(self, svc, async_db, test_user):
        """Code TOTP invalide → ValueError."""
        await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)

        with pytest.raises(ValueError, match="Invalid TOTP code"):
            await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, "000000")

    async def test_verify_setup_no_pending_device_raises(self, svc, async_db, test_user):
        """Pas de device pending → ValueError."""
        with pytest.raises(ValueError, match="No pending MFA setup found"):
            await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, "123456")


# ========== verify_totp ==========

class TestVerifyTotp:
    """Tests pour MFAService.verify_totp (login step 2)."""

    async def _setup_and_enable(self, svc, db, user):
        """Helper : setup + enable MFA, retourne le secret."""
        secret, _, _ = await svc.setup_totp(db, user.id, user.tenant_id, user.email)
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(db, user.id, user.tenant_id, totp.now())
        return secret

    async def test_verify_totp_valid_code(self, svc, async_db, test_user):
        """Code TOTP valide → True."""
        secret = await self._setup_and_enable(svc, async_db, test_user)

        # Avancer le last_totp_window pour éviter l'anti-replay
        device = await _get_device(async_db, test_user.id)
        device.last_totp_window = device.last_totp_window - 2
        await async_db.flush()

        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        result = await svc.verify_totp(async_db, test_user.id, test_user.tenant_id, totp.now())
        assert result is True

    async def test_verify_totp_invalid_code_raises(self, svc, async_db, test_user):
        """Code TOTP invalide → ValueError."""
        await self._setup_and_enable(svc, async_db, test_user)

        with pytest.raises(ValueError, match="Invalid TOTP code"):
            await svc.verify_totp(async_db, test_user.id, test_user.tenant_id, "000000")

    async def test_verify_totp_anti_replay(self, svc, async_db, test_user):
        """Même code réutilisé dans la même fenêtre → anti-replay."""
        secret = await self._setup_and_enable(svc, async_db, test_user)

        # Reset last_totp_window pour permettre la première vérification
        device = await _get_device(async_db, test_user.id)
        device.last_totp_window = device.last_totp_window - 2
        await async_db.flush()

        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        code = totp.now()

        # Premier usage → OK
        await svc.verify_totp(async_db, test_user.id, test_user.tenant_id, code)

        # Deuxième usage même fenêtre → anti-replay
        with pytest.raises(ValueError, match="anti-replay"):
            await svc.verify_totp(async_db, test_user.id, test_user.tenant_id, code)

    async def test_verify_totp_not_enabled_raises(self, svc, async_db, test_user):
        """MFA pas activé → ValueError."""
        with pytest.raises(ValueError, match="not enabled"):
            await svc.verify_totp(async_db, test_user.id, test_user.tenant_id, "123456")


# ========== verify_recovery_code ==========

class TestVerifyRecoveryCode:
    """Tests pour MFAService.verify_recovery_code."""

    async def _setup_and_enable(self, svc, db, user):
        """Helper : setup + enable MFA, retourne (secret, recovery_codes)."""
        secret, _, codes = await svc.setup_totp(db, user.id, user.tenant_id, user.email)
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(db, user.id, user.tenant_id, totp.now())
        return secret, codes

    async def test_recovery_code_valid(self, svc, async_db, test_user):
        """Recovery code valide → True."""
        _, codes = await self._setup_and_enable(svc, async_db, test_user)
        result = await svc.verify_recovery_code(
            async_db, test_user.id, test_user.tenant_id, codes[0]
        )
        assert result is True

    async def test_recovery_code_single_use(self, svc, async_db, test_user):
        """Un recovery code ne peut être utilisé qu'une fois."""
        _, codes = await self._setup_and_enable(svc, async_db, test_user)
        await svc.verify_recovery_code(async_db, test_user.id, test_user.tenant_id, codes[0])

        with pytest.raises(ValueError, match="Invalid recovery code"):
            await svc.verify_recovery_code(async_db, test_user.id, test_user.tenant_id, codes[0])

    async def test_recovery_code_decrements_count(self, svc, async_db, test_user):
        """Utiliser un code décrémente le compteur."""
        _, codes = await self._setup_and_enable(svc, async_db, test_user)
        initial_count = await svc.get_recovery_codes_count(
            async_db, test_user.id, test_user.tenant_id
        )
        await svc.verify_recovery_code(async_db, test_user.id, test_user.tenant_id, codes[0])
        new_count = await svc.get_recovery_codes_count(
            async_db, test_user.id, test_user.tenant_id
        )
        assert new_count == initial_count - 1

    async def test_recovery_code_invalid_raises(self, svc, async_db, test_user):
        """Recovery code invalide → ValueError."""
        await self._setup_and_enable(svc, async_db, test_user)

        with pytest.raises(ValueError, match="Invalid recovery code"):
            await svc.verify_recovery_code(
                async_db, test_user.id, test_user.tenant_id, "not_a_real_code"
            )

    async def test_all_recovery_codes_work(self, svc, async_db, test_user):
        """Tous les recovery codes générés sont valides (un par un)."""
        _, codes = await self._setup_and_enable(svc, async_db, test_user)
        for code in codes:
            result = await svc.verify_recovery_code(
                async_db, test_user.id, test_user.tenant_id, code
            )
            assert result is True

        # Après tous les codes, aucun ne reste
        assert await svc.get_recovery_codes_count(
            async_db, test_user.id, test_user.tenant_id
        ) == 0

    async def test_no_recovery_codes_raises(self, svc, async_db, test_user):
        """Plus de recovery codes → ValueError."""
        _, codes = await self._setup_and_enable(svc, async_db, test_user)
        # Consommer tous les codes
        for code in codes:
            await svc.verify_recovery_code(async_db, test_user.id, test_user.tenant_id, code)

        with pytest.raises(ValueError, match="No recovery codes available"):
            await svc.verify_recovery_code(
                async_db, test_user.id, test_user.tenant_id, "any_code"
            )

    async def test_recovery_code_mfa_not_enabled_raises(self, svc, async_db, test_user):
        """MFA pas activé → ValueError."""
        with pytest.raises(ValueError, match="not enabled"):
            await svc.verify_recovery_code(
                async_db, test_user.id, test_user.tenant_id, "any_code"
            )


# ========== disable_mfa ==========

class TestDisableMfa:
    """Tests pour MFAService.disable_mfa."""

    async def test_disable_removes_device(self, svc, async_db, test_user):
        """disable_mfa supprime le device de la DB."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, totp.now())

        result = await svc.disable_mfa(async_db, test_user.id, test_user.tenant_id)
        assert result is True

        device = await _get_device(async_db, test_user.id)
        assert device is None

    async def test_disable_no_device_raises(self, svc, async_db, test_user):
        """Pas de device → ValueError."""
        with pytest.raises(ValueError, match="not enabled"):
            await svc.disable_mfa(async_db, test_user.id, test_user.tenant_id)

    async def test_disable_pending_device_also_works(self, svc, async_db, test_user):
        """disable_mfa supprime aussi un device pending (non activé)."""
        await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)
        result = await svc.disable_mfa(async_db, test_user.id, test_user.tenant_id)
        assert result is True


# ========== is_mfa_enabled / get_recovery_codes_count ==========

class TestMfaStatus:
    """Tests pour is_mfa_enabled et get_recovery_codes_count."""

    async def test_is_mfa_enabled_false_by_default(self, svc, async_db, test_user):
        """Pas de device → False."""
        assert await svc.is_mfa_enabled(async_db, test_user.id, test_user.tenant_id) is False

    async def test_is_mfa_enabled_false_for_pending(self, svc, async_db, test_user):
        """Device pending (non activé) → False."""
        await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)
        assert await svc.is_mfa_enabled(async_db, test_user.id, test_user.tenant_id) is False

    async def test_is_mfa_enabled_true_after_verify(self, svc, async_db, test_user):
        """Device activé → True."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, totp.now())

        assert await svc.is_mfa_enabled(async_db, test_user.id, test_user.tenant_id) is True

    async def test_recovery_count_zero_by_default(self, svc, async_db, test_user):
        """Pas de device → 0 codes."""
        assert await svc.get_recovery_codes_count(
            async_db, test_user.id, test_user.tenant_id
        ) == 0

    async def test_recovery_count_after_setup(self, svc, async_db, test_user):
        """Après setup + activation → RECOVERY_CODE_COUNT codes."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, totp.now())

        assert await svc.get_recovery_codes_count(
            async_db, test_user.id, test_user.tenant_id
        ) == MFAConfig.RECOVERY_CODE_COUNT


# ========== MFA Session Tokens (Redis) ==========

class TestMfaSession:
    """Tests pour create_mfa_session / validate_mfa_session (Redis)."""

    async def test_create_returns_token_string(self, svc):
        """create_mfa_session retourne un string non vide."""
        token = await svc.create_mfa_session(
            user_id=1, tenant_id=1, email="test@test.com",
            role="staff", ip_address="127.0.0.1"
        )
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_validate_returns_data(self, svc):
        """validate_mfa_session retourne les données de l'utilisateur."""
        token = await svc.create_mfa_session(
            user_id=42, tenant_id=1, email="mfa@test.com",
            role="admin", ip_address="10.0.0.1"
        )
        data = await svc.validate_mfa_session(token)
        assert data is not None
        assert data["user_id"] == 42
        assert data["tenant_id"] == 1
        assert data["email"] == "mfa@test.com"
        assert data["role"] == "admin"
        assert data["ip_address"] == "10.0.0.1"

    async def test_validate_single_use(self, svc):
        """Le token est consommé après la première validation (single-use)."""
        token = await svc.create_mfa_session(
            user_id=1, tenant_id=1, email="test@test.com",
            role="staff", ip_address="127.0.0.1"
        )
        # Première utilisation → OK
        data = await svc.validate_mfa_session(token)
        assert data is not None

        # Deuxième utilisation → None (consommé)
        data2 = await svc.validate_mfa_session(token)
        assert data2 is None

    async def test_validate_invalid_token(self, svc):
        """Token inexistant → None."""
        data = await svc.validate_mfa_session("nonexistent_token_xyz")
        assert data is None

    async def test_each_token_is_unique(self, svc):
        """Deux appels create_mfa_session → tokens différents."""
        t1 = await svc.create_mfa_session(
            user_id=1, tenant_id=1, email="a@b.com",
            role="staff", ip_address="1.1.1.1"
        )
        t2 = await svc.create_mfa_session(
            user_id=1, tenant_id=1, email="a@b.com",
            role="staff", ip_address="1.1.1.1"
        )
        assert t1 != t2


# ========== Isolation multi-tenant ==========

class TestMultiTenantIsolation:
    """Tests d'isolation multi-tenant pour MFA."""

    async def test_setup_isolated_per_tenant(self, svc, async_db, test_user, test_user_tenant2):
        """Chaque tenant a son propre MFA device."""
        await svc.setup_totp(async_db, test_user.id, test_user.tenant_id, test_user.email)
        await svc.setup_totp(
            async_db, test_user_tenant2.id, test_user_tenant2.tenant_id,
            test_user_tenant2.email
        )

        devices = await _get_all_devices(async_db)
        assert len(devices) == 2

    async def test_verify_totp_wrong_tenant_raises(self, svc, async_db, test_user, test_user_tenant2):
        """Vérification TOTP avec le mauvais tenant_id → erreur."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, totp.now())

        # Tenter verify_totp avec tenant_id=2 → MFA pas activé pour ce tenant
        with pytest.raises(ValueError, match="No active membership|not enabled"):
            await svc.verify_totp(
                async_db, test_user.id, test_user_tenant2.tenant_id, totp.now()
            )

    async def test_is_mfa_enabled_cross_tenant(self, svc, async_db, test_user, test_user_tenant2):
        """is_mfa_enabled ne voit pas les devices d'un autre tenant."""
        secret, _, _ = await svc.setup_totp(
            async_db, test_user.id, test_user.tenant_id, test_user.email
        )
        totp = pyotp.TOTP(secret, digits=MFAConfig.TOTP_DIGITS, interval=MFAConfig.TOTP_PERIOD)
        await svc.verify_setup(async_db, test_user.id, test_user.tenant_id, totp.now())

        # Tenant 1 → True
        assert await svc.is_mfa_enabled(async_db, test_user.id, test_user.tenant_id) is True
        # Tenant 2 pour le même user_id → pas de membership dans tenant 2 → ValueError OU False
        # (selon si l'user a un membership tenant 2 ou non).
        # test_user est créé tenant 1 uniquement → _resolve_membership_id lève ValueError.
        with pytest.raises(ValueError, match="No active membership"):
            await svc.is_mfa_enabled(async_db, test_user.id, test_user_tenant2.tenant_id)


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
