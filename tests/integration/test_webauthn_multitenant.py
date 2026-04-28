"""S1.T11 — Tests F368/WEBAUTHN-RPID-MULTITENANT-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L2028-2175 (Story S1.T11).

Avant ce sprint : `RP_ID = settings.JWT_ISSUER.replace("www.", "")` au module-level
de `app/services/webauthn.py` -> credential WebAuthn liee cryptographiquement a
"marveline.com", impossible d'enroler/auth depuis splendid.events ou
epicerie.carocorp.fr -> bloque la demo Splendid 28/04.

Apres : `WebAuthnService(db, tenant)` lit `tenant.rp_id` / `tenant.frontend_url`
avec fallback settings.* si NULL ou tenant absent.
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.models.tenant import Tenant
from app.services.webauthn import WebAuthnService


def _mk_tenant(rp_id=None, frontend_url=None, name="Test Tenant"):
    """Helper : Tenant non-persiste avec uniquement les attributs lus par WebAuthnService."""
    tenant = MagicMock(spec=Tenant)
    tenant.rp_id = rp_id
    tenant.frontend_url = frontend_url
    tenant.name = name
    return tenant


# ----------------------------------------------------------------------------
# __init__ : calcul rp_id / expected_origin / rp_name
# ----------------------------------------------------------------------------

def test_webauthn_service_uses_tenant_rp_id_when_set():
    """F368 fix : tenant.rp_id renseigne -> svc.rp_id = tenant.rp_id (Splendid)."""
    tenant = _mk_tenant(
        rp_id="splendid.events",
        frontend_url="https://splendid.events",
        name="Splendid Events",
    )
    svc = WebAuthnService(MagicMock(), tenant)

    assert svc.rp_id == "splendid.events"
    assert svc.rp_id != "marveline.com"  # Critique : pas de leak du global Marveline
    assert svc.expected_origin == "https://splendid.events"
    assert svc.rp_name == "Splendid Events"


def test_webauthn_service_falls_back_settings_when_tenant_none():
    """Compat : tenant=None (legacy/tests) -> fallback total sur settings.*"""
    svc = WebAuthnService(MagicMock(), None)

    assert svc.rp_id == settings.JWT_ISSUER.replace("www.", "")
    assert svc.expected_origin == settings.FRONTEND_URL
    assert svc.rp_name == settings.APP_NAME


def test_webauthn_service_falls_back_when_tenant_rp_id_null():
    """Backfill non encore applique : tenant.rp_id=NULL -> fallback settings, mais
    rp_name = tenant.name (le tenant existe, son nom est connu)."""
    tenant = _mk_tenant(rp_id=None, frontend_url=None, name="Legacy Tenant")
    svc = WebAuthnService(MagicMock(), tenant)

    assert svc.rp_id == settings.JWT_ISSUER.replace("www.", "")
    assert svc.expected_origin == settings.FRONTEND_URL
    assert svc.rp_name == "Legacy Tenant"


def test_webauthn_service_isolates_two_tenants_rp_id():
    """Anti-cross-tenant : 2 services instancies sur 2 tenants -> 2 rp_id et
    2 expected_origin distincts. Garantit qu'une credential enrolee sur Splendid
    ne pourra pas etre utilisee sur Marveline (verification cryptographique
    cote py_webauthn echoue avec InvalidRpIdError)."""
    splendid = _mk_tenant(
        rp_id="splendid.events",
        frontend_url="https://splendid.events",
        name="Splendid",
    )
    marveline = _mk_tenant(
        rp_id="marveline.com",
        frontend_url="https://marveline.com",
        name="Marveline",
    )

    svc_splendid = WebAuthnService(MagicMock(), splendid)
    svc_marveline = WebAuthnService(MagicMock(), marveline)

    assert svc_splendid.rp_id == "splendid.events"
    assert svc_marveline.rp_id == "marveline.com"
    assert svc_splendid.rp_id != svc_marveline.rp_id
    assert svc_splendid.expected_origin == "https://splendid.events"
    assert svc_marveline.expected_origin == "https://marveline.com"
    assert svc_splendid.expected_origin != svc_marveline.expected_origin


# ----------------------------------------------------------------------------
# generate_registration_options : rp.id dans la response
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_options_returns_tenant_rp_id_in_response():
    """End-to-end service : generate_registration_options renvoie rp.id = tenant.rp_id."""
    tenant = _mk_tenant(
        rp_id="splendid.events",
        frontend_url="https://splendid.events",
        name="Splendid",
    )
    svc = WebAuthnService(MagicMock(), tenant)

    with patch.object(svc, "_list_credentials", new=AsyncMock(return_value=[])):
        with patch("app.services.webauthn.redis_sec") as redis_mock:
            redis_mock.client.setex = AsyncMock()
            options = await svc.generate_registration_options(
                account_id=42,
                email="user@splendid.events",
                device_name="YubiKey",
            )

    assert options["rp"]["id"] == "splendid.events"
    assert options["rp"]["id"] != "marveline.com"
    assert options["rp"]["name"] == "Splendid"


@pytest.mark.asyncio
async def test_authenticate_options_returns_tenant_rp_id_in_response():
    """authenticate_options renvoie rpId = tenant.rp_id (step-up MFA per-tenant)."""
    tenant = _mk_tenant(
        rp_id="epicerie.carocorp.fr",
        frontend_url="https://epicerie.carocorp.fr",
        name="Epicerie",
    )
    svc = WebAuthnService(MagicMock(), tenant)

    fake_cred = MagicMock()
    fake_cred.credential_id = b"fake_credential_bytes"

    with patch.object(svc, "_list_credentials", new=AsyncMock(return_value=[fake_cred])):
        with patch("app.services.webauthn.redis_sec") as redis_mock:
            redis_mock.client.setex = AsyncMock()
            options = await svc.generate_authentication_options(account_id=42)

    assert options["rpId"] == "epicerie.carocorp.fr"
    assert options["rpId"] != "marveline.com"


# ----------------------------------------------------------------------------
# Verify : expected_rp_id transmis a verify_registration_response
# ----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_verify_passes_tenant_rp_id_and_origin_to_py_webauthn():
    """verify_registration appelle py_webauthn avec expected_rp_id=tenant.rp_id
    et expected_origin=tenant.frontend_url."""
    tenant = _mk_tenant(
        rp_id="splendid.events",
        frontend_url="https://splendid.events",
        name="Splendid",
    )
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    svc = WebAuthnService(db, tenant)

    fake_verification = MagicMock()
    fake_verification.credential_id = b"cred_id_bytes"
    fake_verification.credential_public_key = b"pubkey_bytes"
    fake_verification.sign_count = 0
    fake_verification.aaguid = None

    # `verify_registration_response` est importe en local dans la methode (try/except).
    # py_webauthn n'est pas necessairement installe dans l'env de test : on injecte
    # un faux module dans sys.modules pour intercepter l'import et capturer les kwargs.
    fake_webauthn = MagicMock()
    fake_webauthn.verify_registration_response = MagicMock(return_value=fake_verification)
    fake_structs = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "webauthn": fake_webauthn,
            "webauthn.helpers": MagicMock(),
            "webauthn.helpers.structs": fake_structs,
        },
    ):
        with patch("app.services.webauthn.redis_sec") as redis_mock:
            redis_mock.client.getdel = AsyncMock(return_value=b"Y2hhbGxlbmdl")  # "challenge"
            await svc.verify_registration(
                account_id=42,
                credential_id_b64="Y3JlZA",
                client_data_json_b64="Y2RhdGE",
                attestation_object_b64="YXR0",
                device_name="YubiKey",
            )

    fake_webauthn.verify_registration_response.assert_called_once()
    kwargs = fake_webauthn.verify_registration_response.call_args.kwargs
    assert kwargs["expected_rp_id"] == "splendid.events"
    assert kwargs["expected_origin"] == "https://splendid.events"
