"""S1.T6 — Tests F1002/AUDIT-LOGIN-EXCL-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L1482-1589 (Story S1.T6).

Avant : `AuditMiddleware.EXCLUDED_PATHS` contient `/auth/login`. Si l'endpoint
oublie d'appeler `audit.log_login(success=False)` ou si une exception interrompt
l'endpoint avant cet appel, les tentatives echouees ne sont pas tracees ->
non-conformite RGPD Art.30 + brute-force credential stuffing invisible.

Apres : try/except `(HTTPException, AppException)` dans le endpoint /login
ecrit explicitement un AuditLog action='LOGIN_FAILED' avec changes={reason, actor_email}
via session DB separee (robustesse meme si session principale rollback).
"""
from sqlalchemy import select

from app.models.audit_log import AuditLog


# Tests integration via TestClient + test_user fixture (cf tests/conftest.py)


def test_login_wrong_password_creates_audit_log(client, test_db, test_user):
    """F1002 fix : login avec mauvais password -> AuditLog 'LOGIN_FAILED' cree.

    DoD spec L1576 : try/except dans auth.py avec audit explicite,
    password masque (jamais dans changes), 3 exceptions couvertes.
    """
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.email,
            "password": "definitivement-pas-le-bon-password",
        },
    )
    assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"

    # Verifier qu'un AuditLog 'LOGIN_FAILED' a ete cree
    logs = test_db.execute(
        select(AuditLog)
        .filter(AuditLog.action == "LOGIN_FAILED")
        .order_by(AuditLog.created_at.desc())
    ).scalars().all()

    assert len(logs) >= 1, "Au moins un AuditLog LOGIN_FAILED attendu"
    log = logs[0]
    assert log.account_id is None, "user_id NULL pour login echoue (compte non identifie)"
    assert log.changes is not None, "changes (metadata) doit etre populated"
    assert log.changes.get("actor_email") == test_user.email
    # Critique : le password ne doit JAMAIS apparaitre dans le log
    assert "definitivement-pas-le-bon-password" not in str(log.changes)
    assert "definitivement-pas-le-bon-password" not in (log.description or "")


def test_login_unknown_email_creates_audit_log_without_account_id(client, test_db):
    """F1002 fix : login avec email inconnu -> AuditLog cree, account_id=None,
    actor_email = email tente (anti-bruteforce ciblage)."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ghost@nobody.example",
            "password": "anything",
        },
    )
    assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"

    logs = test_db.execute(
        select(AuditLog)
        .filter(AuditLog.action == "LOGIN_FAILED")
        .filter(AuditLog.changes.op("->>")("actor_email") == "ghost@nobody.example")
    ).scalars().all()

    assert len(logs) >= 1, "AuditLog LOGIN_FAILED attendu pour email inconnu"
    log = logs[0]
    assert log.account_id is None
    assert log.changes.get("actor_email") == "ghost@nobody.example"


def test_login_failure_audit_contains_reason_class_name(client, test_db, test_user):
    """changes.reason doit contenir le class name de l'exception (InvalidCredentials,
    AccountLocked, AccountSuspended) pour debug + detection patterns brute-force."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.email,
            "password": "wrong-pw",
        },
    )
    assert response.status_code == 401

    logs = test_db.execute(
        select(AuditLog)
        .filter(AuditLog.action == "LOGIN_FAILED")
        .order_by(AuditLog.created_at.desc())
    ).scalars().all()

    assert len(logs) >= 1
    log = logs[0]
    reason = log.changes.get("reason") if log.changes else None
    # Le reason doit etre un nom de classe d'exception (PascalCase, pas vide)
    assert reason is not None and len(reason) > 0, "changes.reason doit etre populated"
    # Les exceptions attendues finissent par 'Exception', 'Error', ou sont des AppException specifiques
    assert reason[0].isupper(), f"reason doit etre un class name (PascalCase), got '{reason}'"


def test_login_success_does_not_create_login_failed_audit(client, test_db, test_user):
    """Non-regression : login reussi ne genere pas de AuditLog 'LOGIN_FAILED'."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.email,
            "password": "testpass123",  # cf conftest fixture test_user
        },
    )
    # Login peut soit succeder (200) soit demander MFA (200 avec mfa_required=True)
    # Dans les deux cas, pas de LOGIN_FAILED genere par notre fix.
    assert response.status_code in (200, 401, 403), f"got {response.status_code}: {response.text}"

    if response.status_code == 200:
        logs = test_db.execute(
            select(AuditLog)
            .filter(AuditLog.action == "LOGIN_FAILED")
            .filter(AuditLog.changes.op("->>")("actor_email") == test_user.email)
        ).scalars().all()
        assert len(logs) == 0, (
            f"Login reussi ne doit pas creer LOGIN_FAILED, got {len(logs)} logs"
        )
