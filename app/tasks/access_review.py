"""Tâches Celery — access reviews périodiques (§S-13.3 §10-MULTI-TENANT-OPS).

Beat schedule (4 tâches) :
    privileged_access_review  : 1er du mois (super_admin, platform_ops)
    tenant_admin_review       : 1er du trimestre (tenant_admin)
    recertification_review    : 1er juillet + 1er janvier (tous users)
    auto_suspend_uncertified  : 1er février + 1er août (suspend non-recertifiés J+30)

Logique de suspension automatique (§10) :
    Un user non-recertifié au-delà de J+30 est automatiquement suspendu
    (is_active=False) et notifié. Réactivation sur action admin.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Rôles concernés par chaque type de review ────────────────────────────────

PRIVILEGED_ROLES = {"super_admin", "platform_ops"}
TENANT_ADMIN_ROLES = {"tenant_admin"}
ALL_ROLES = {"super_admin", "platform_ops", "tenant_admin", "manager", "staff", "viewer"}

# Délai de grâce avant suspension automatique (§10)
GRACE_PERIOD_DAYS = 30

# ── Requêtes IAM v2 (accounts + tenant_memberships) ─────────────────────────

_SQL_USERS_BY_ROLES = """
    SELECT a.id, a.email, tm.tenant_id, tm.role_name
    FROM accounts a
    JOIN tenant_memberships tm ON a.id = tm.account_id
    WHERE tm.role_name IN :roles
      AND a.is_active = true
      AND tm.status = 'active'
"""

_SQL_TENANT_ADMINS = """
    SELECT a.id, a.email, tm.tenant_id
    FROM accounts a
    JOIN tenant_memberships tm ON a.id = tm.account_id
    WHERE tm.role_name = 'tenant_admin'
      AND a.is_active = true
      AND tm.status = 'active'
"""

_SQL_ACTIVE_COUNT = """
    SELECT COUNT(DISTINCT a.id)
    FROM accounts a
    JOIN tenant_memberships tm ON a.id = tm.account_id
    WHERE a.is_active = true
      AND tm.status = 'active'
"""


# ── Tâches périodiques ────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.access_review.run_privileged_access_review")
def run_privileged_access_review():
    """Revue accès comptes privilégiés (super_admin, platform_ops) — 1er du mois (§10)."""
    logger.info("[access_review] Starting privileged access review: %s", datetime.now(timezone.utc).date())
    try:
        from app.core.database import SyncSessionLocal
        from sqlalchemy import text

        with SyncSessionLocal() as db:
            result = db.execute(
                text(_SQL_USERS_BY_ROLES),
                {"roles": tuple(PRIVILEGED_ROLES)},
            )
            users = result.fetchall()
            count = len(users)
            logger.info(
                "[access_review] Privileged review: %d users to certify roles=%s",
                count, PRIVILEGED_ROLES,
            )
            return {"status": "ok", "users_to_review": count, "roles": list(PRIVILEGED_ROLES)}
    except Exception as exc:
        logger.error("[access_review] Privileged review failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="app.tasks.access_review.run_tenant_admin_review")
def run_tenant_admin_review():
    """Revue accès tenant_admin — 1er du trimestre (§10)."""
    logger.info("[access_review] Starting tenant_admin review: %s", datetime.now(timezone.utc).date())
    try:
        from app.core.database import SyncSessionLocal
        from sqlalchemy import text

        with SyncSessionLocal() as db:
            result = db.execute(text(_SQL_TENANT_ADMINS))
            users = result.fetchall()
            count = len(users)
            logger.info("[access_review] Tenant admin review: %d admins to certify", count)
            return {"status": "ok", "users_to_review": count, "roles": ["tenant_admin"]}
    except Exception as exc:
        logger.error("[access_review] Tenant admin review failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="app.tasks.access_review.run_recertification_review")
def run_recertification_review():
    """Recertification annuelle de tous les accès — 1er juillet + 1er janvier (§10)."""
    review_date = datetime.now(timezone.utc).date()
    deadline = (datetime.now(timezone.utc) + timedelta(days=GRACE_PERIOD_DAYS)).date()
    logger.info(
        "[access_review] Starting full recertification: started=%s deadline=%s",
        review_date, deadline,
    )
    try:
        from app.core.database import SyncSessionLocal
        from sqlalchemy import text

        with SyncSessionLocal() as db:
            total = db.execute(text(_SQL_ACTIVE_COUNT)).scalar()
            logger.info("[access_review] Recertification campaign: %d active users, deadline=%s", total, deadline)
            return {
                "status": "ok",
                "users_total": total,
                "review_date": str(review_date),
                "deadline": str(deadline),
            }
    except Exception as exc:
        logger.error("[access_review] Recertification review failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="app.tasks.access_review.run_auto_suspend_uncertified")
def run_auto_suspend_uncertified():
    """Suspension automatique des users non-recertifiés à J+30 — 1er fév + 1er août (§10).

    Note : en l'absence d'une table access_reviews dédiée, cette tâche loggue
    uniquement. L'implémentation complète nécessite la table access_reviews.
    """
    logger.info("[access_review] Running auto-suspend for uncertified users: %s", datetime.now(timezone.utc).date())
    logger.warning(
        "[access_review] auto_suspend_uncertified: table access_reviews not yet implemented — skipping suspensions"
    )
    return {"status": "skipped", "reason": "access_reviews table pending", "grace_days": GRACE_PERIOD_DAYS}
