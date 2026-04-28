"""S1.T9 — Tests F296/OAUTH-ONLY-TYPEERROR-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L1791-1903 (Story S1.T9).

Avant : `account.py:70 -> verify_password(password, account.hashed_password)`.
Compte OAuth-only -> hashed_password=None -> TypeError 500.
HTTP 500 vs 401 -> user enumeration des comptes OAuth-only.

Apres : `if not account.hashed_password: verify_password(password, DUMMY_HASH); return None`.
Timing-safe (Argon2 sur DUMMY_HASH) + 401 dans tous les cas (None retourne).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.account import AccountService


def _mk_account(hashed_password: str | None):
    """Helper : Account mock avec un hashed_password donne (None pour OAuth-only)."""
    account = MagicMock()
    account.hashed_password = hashed_password
    account.email = "user@test.fr"
    account.is_active = True
    return account


@pytest.mark.asyncio
async def test_verify_credentials_oauth_only_returns_none_not_typeerror():
    """F296 fix : compte OAuth-only (hashed_password=None) -> None, pas TypeError 500."""
    svc = AccountService(db=MagicMock())
    svc._repo.get_by_email = AsyncMock(return_value=_mk_account(hashed_password=None))

    # Avant fix : raise TypeError("argument should be str, not None")
    # Apres fix : retourne None proprement
    result = await svc.verify_credentials("oauth@test.fr", "any_password")

    assert result is None


@pytest.mark.asyncio
async def test_verify_credentials_oauth_only_calls_dummy_hash_for_timing_safety(monkeypatch):
    """Anti user-enum : verify_password DOIT etre appele sur DUMMY_HASH meme en OAuth-only,
    pour egaliser le temps de reponse avec un email inconnu."""
    from app.services import account as account_module

    # Espionner verify_password sans casser sa logique
    calls = []
    original = account_module.verify_password

    def spy_verify(plain, hashed):
        calls.append((plain, hashed))
        return False  # Pas important pour le timing test

    monkeypatch.setattr(account_module, "verify_password", spy_verify)

    svc = AccountService(db=MagicMock())
    svc._repo.get_by_email = AsyncMock(return_value=_mk_account(hashed_password=None))

    await svc.verify_credentials("oauth@test.fr", "any_password")

    # 1 appel a verify_password, sur DUMMY_HASH (timing-safe)
    assert len(calls) == 1
    plain, hashed = calls[0]
    assert plain == "any_password"
    assert hashed == account_module.DUMMY_HASH


@pytest.mark.asyncio
async def test_verify_credentials_unknown_email_still_returns_none():
    """Non-regression : email inconnu -> None (timing-safe deja en place avant fix)."""
    svc = AccountService(db=MagicMock())
    svc._repo.get_by_email = AsyncMock(return_value=None)

    result = await svc.verify_credentials("ghost@test.fr", "any_password")

    assert result is None


@pytest.mark.asyncio
async def test_verify_credentials_valid_password_returns_account(monkeypatch):
    """Non-regression : compte avec hashed_password valide + password correct -> Account."""
    from app.services import account as account_module

    monkeypatch.setattr(account_module, "verify_password", lambda p, h: p == "good_pass")
    monkeypatch.setattr(account_module, "needs_rehash", lambda h: False)

    account = _mk_account(hashed_password="$argon2id$v=19$m=...$realhash")
    svc = AccountService(db=MagicMock())
    svc._repo.get_by_email = AsyncMock(return_value=account)

    result = await svc.verify_credentials("user@test.fr", "good_pass")

    assert result is account


@pytest.mark.asyncio
async def test_verify_credentials_wrong_password_returns_none(monkeypatch):
    """Non-regression : compte avec password mais mauvais password -> None."""
    from app.services import account as account_module

    monkeypatch.setattr(account_module, "verify_password", lambda p, h: False)

    account = _mk_account(hashed_password="$argon2id$v=19$m=...$realhash")
    svc = AccountService(db=MagicMock())
    svc._repo.get_by_email = AsyncMock(return_value=account)

    result = await svc.verify_credentials("user@test.fr", "wrong_pass")

    assert result is None


@pytest.mark.asyncio
async def test_verify_credentials_oauth_only_does_not_distinguishable_from_unknown(monkeypatch):
    """User enumeration prevention : OAuth-only et email-inconnu doivent retourner
    la meme valeur (None) et appeler le meme nombre de fois verify_password (1x)
    pour rendre indistinguable la reponse cote attaquant."""
    from app.services import account as account_module

    counter = {"calls": 0}

    def spy(plain, hashed):
        counter["calls"] += 1
        return False

    monkeypatch.setattr(account_module, "verify_password", spy)

    # Cas 1 : email inconnu
    svc1 = AccountService(db=MagicMock())
    svc1._repo.get_by_email = AsyncMock(return_value=None)
    result_unknown = await svc1.verify_credentials("ghost@test.fr", "x")
    calls_unknown = counter["calls"]

    # Cas 2 : OAuth-only
    counter["calls"] = 0
    svc2 = AccountService(db=MagicMock())
    svc2._repo.get_by_email = AsyncMock(return_value=_mk_account(hashed_password=None))
    result_oauth = await svc2.verify_credentials("oauth@test.fr", "x")
    calls_oauth = counter["calls"]

    # Reponses identiques (None) + meme nombre d'appels verify_password (1x)
    assert result_unknown is None
    assert result_oauth is None
    assert calls_unknown == calls_oauth == 1
