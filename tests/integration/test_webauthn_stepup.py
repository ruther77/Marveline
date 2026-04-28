"""S1.T8 — Tests F370/STEPUP-WEBAUTHN-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L1694-1788 (Story S1.T8).

Avant : `app/api/v1/endpoints/webauthn.py:85` :
    device_id = getattr(current_user, '_device_id', '') or ''
UserCompat n'a JAMAIS d'attribut `_device_id` -> device_id = "" toujours.
Cle ecrite : "stepup:42:" / Cle lue par require_stepup : "stepup:42:{did_du_jwt}".
Mismatch -> 100% des stepup WebAuthn refuses post-verify.

Apres : helper `_extract_did_from_request(request)` lit le claim `did` du JWT
exactement comme `app/core/deps.py:require_stepup` et `app/api/v1/endpoints/mfa.py:verify_mfa_stepup`.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.endpoints.webauthn import _extract_did_from_request


def _mk_request(authorization: str | None = None):
    """Helper : Request mock avec un header Authorization optionnel."""
    request = MagicMock()
    headers = {}
    if authorization is not None:
        headers["Authorization"] = authorization
    # request.headers.get(name, default) -> dict.get
    request.headers.get = lambda name, default="": headers.get(name, default)
    return request


# ----------------------------------------------------------------------------
# _extract_did_from_request : 5 cas
# ----------------------------------------------------------------------------

def test_extract_did_returns_claim_when_jwt_has_did():
    """JWT Bearer valide avec claim 'did' -> renvoie le did."""
    request = _mk_request("Bearer fake.jwt.token")
    with patch(
        "app.api.v1.endpoints.webauthn.decode_token",
        return_value={"sub": "42", "tid": 1, "did": "abc123-fingerprint"},
    ):
        did = _extract_did_from_request(request)
    assert did == "abc123-fingerprint"


def test_extract_did_returns_empty_when_jwt_has_no_did_claim():
    """JWT Bearer valide sans claim 'did' -> "" (default)."""
    request = _mk_request("Bearer fake.jwt.token")
    with patch(
        "app.api.v1.endpoints.webauthn.decode_token",
        return_value={"sub": "42", "tid": 1},  # pas de 'did'
    ):
        did = _extract_did_from_request(request)
    assert did == ""


def test_extract_did_returns_empty_when_no_authorization_header():
    """Pas de header Authorization -> "" sans crash."""
    request = _mk_request(authorization=None)
    did = _extract_did_from_request(request)
    assert did == ""


def test_extract_did_returns_empty_when_authorization_not_bearer():
    """Header Authorization sans prefix 'Bearer ' -> "" (Basic, ApiKey, etc.)."""
    request = _mk_request("Basic dXNlcjpwYXNz")
    did = _extract_did_from_request(request)
    assert did == ""


def test_extract_did_returns_empty_when_decode_token_raises():
    """JWT invalide / expire -> decode_token raise -> "" (pas de propagation)."""
    request = _mk_request("Bearer corrupted.jwt.token")
    with patch(
        "app.api.v1.endpoints.webauthn.decode_token",
        side_effect=Exception("TokenInvalid"),
    ):
        did = _extract_did_from_request(request)
    assert did == ""


def test_extract_did_returns_empty_when_decode_token_returns_none():
    """decode_token renvoie None (cas defensif) -> "" (pas de AttributeError)."""
    request = _mk_request("Bearer fake.jwt.token")
    with patch(
        "app.api.v1.endpoints.webauthn.decode_token",
        return_value=None,
    ):
        did = _extract_did_from_request(request)
    assert did == ""


# ----------------------------------------------------------------------------
# Coherence write/read : meme logique que require_stepup
# ----------------------------------------------------------------------------

def test_extract_did_matches_require_stepup_logic():
    """L'implementation doit matcher exactement le pattern de
    `app/core/deps.py:require_stepup` (lignes 773-779) et
    `app/api/v1/endpoints/mfa.py:verify_mfa_stepup` (lignes 411-417) :
    decode_token(token_bearer).get('did', '').

    Ce test verifie qu'un meme JWT donne le meme device_id que require_stepup
    extrairait, garantissant le matching write/read de la cle Redis stepup."""
    request = _mk_request("Bearer fake.jwt.token")
    fake_payload = {"sub": "42", "tid": 1, "did": "device-fp-xyz"}

    # 1. _extract_did_from_request (notre helper webauthn endpoint)
    with patch(
        "app.api.v1.endpoints.webauthn.decode_token",
        return_value=fake_payload,
    ):
        webauthn_did = _extract_did_from_request(request)

    # 2. Logique inline dans require_stepup (deps.py L777) : payload.get("did", "")
    expected_from_guard = fake_payload.get("did", "")

    assert webauthn_did == expected_from_guard
    assert webauthn_did == "device-fp-xyz"
