"""Backfill IAM v2 : copie users → accounts + tenant_memberships.

Usage :
    python scripts/backfill_users_to_accounts.py --dry-run
    python scripts/backfill_users_to_accounts.py --execute

Idempotent : skip les accounts dont l'email existe deja.
Genere un rapport CSV dans scripts/backfill_report.csv.
"""
import argparse
import csv
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

# Ajouter la racine du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPORT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backfill_report.csv")


def get_engine():
    """Cree un engine synchrone depuis la config."""
    return create_engine(str(settings.DATABASE_URL), echo=False)


def _table_exists(session: Session, table_name: str) -> bool:
    """Verifie si une table existe dans la base."""
    result = session.execute(text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :name)"
    ), {"name": table_name})
    return bool(result.scalar())


def fetch_legacy_users(session: Session) -> list[dict]:
    """Lit tous les users de la table legacy."""
    if not _table_exists(session, "users"):
        logger.info("Table 'users' does not exist — nothing to backfill")
        return []
    result = session.execute(text("""
        SELECT id, email, hashed_password, first_name, last_name,
               role, tenant_id, is_active, created_at, updated_at
        FROM users
        ORDER BY id
    """))
    return [dict(row._mapping) for row in result]


def fetch_existing_account_emails(session: Session) -> set[str]:
    """Retourne l'ensemble des emails deja presents dans accounts."""
    result = session.execute(text("SELECT lower(email) FROM accounts"))
    return {row[0] for row in result}


def backfill(dry_run: bool) -> None:
    """Execute le backfill users → accounts + tenant_memberships."""
    engine = get_engine()
    report_rows: list[dict] = []

    with Session(engine) as session:
        users = fetch_legacy_users(session)
        logger.info("Found %d legacy users", len(users))

        if not users:
            logger.info("Nothing to backfill")
            return

        existing_emails = fetch_existing_account_emails(session)
        logger.info("Found %d existing accounts", len(existing_emails))

        created_accounts = 0
        created_memberships = 0
        skipped = 0

        for user in users:
            email = (user["email"] or "").lower().strip()
            if not email:
                logger.warning("Skipping user id=%d — empty email", user["id"])
                report_rows.append({
                    "user_id": user["id"],
                    "email": email,
                    "action": "SKIPPED",
                    "reason": "empty email",
                })
                skipped += 1
                continue

            if email in existing_emails:
                logger.debug("Skipping user id=%d email=%s — account exists", user["id"], email)
                report_rows.append({
                    "user_id": user["id"],
                    "email": email,
                    "action": "SKIPPED",
                    "reason": "account already exists",
                })
                skipped += 1
                continue

            external_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            if not dry_run:
                # INSERT account
                result = session.execute(text("""
                    INSERT INTO accounts
                        (external_id, email, hashed_password, first_name, last_name,
                         is_active, password_change_required, created_at, updated_at)
                    VALUES
                        (:external_id, :email, :hashed_password, :first_name, :last_name,
                         :is_active, false, :created_at, :updated_at)
                    RETURNING id
                """), {
                    "external_id": external_id,
                    "email": email,
                    "hashed_password": user["hashed_password"],
                    "first_name": user["first_name"] or "",
                    "last_name": user["last_name"] or "",
                    "is_active": user["is_active"] if user["is_active"] is not None else True,
                    "created_at": user["created_at"] or now,
                    "updated_at": user["updated_at"] or now,
                })
                account_id = result.scalar_one()

                # INSERT tenant_membership
                role_name = user["role"] or "staff"
                session.execute(text("""
                    INSERT INTO tenant_memberships
                        (account_id, tenant_id, role_name, status, activated_at)
                    VALUES
                        (:account_id, :tenant_id, :role_name, 'active', :activated_at)
                """), {
                    "account_id": account_id,
                    "tenant_id": user["tenant_id"],
                    "role_name": role_name,
                    "activated_at": user["created_at"] or now,
                })

                created_memberships += 1
            else:
                account_id = f"DRY-{user['id']}"

            existing_emails.add(email)
            created_accounts += 1

            report_rows.append({
                "user_id": user["id"],
                "email": email,
                "action": "CREATED" if not dry_run else "WOULD_CREATE",
                "reason": f"account_id={account_id}",
            })

        if not dry_run:
            session.commit()
            logger.info("Committed transaction")
        else:
            logger.info("DRY RUN — no changes committed")

        logger.info(
            "Summary: %d created, %d memberships, %d skipped (of %d total)",
            created_accounts, created_memberships, skipped, len(users),
        )

    # Write CSV report
    with open(REPORT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "email", "action", "reason"])
        writer.writeheader()
        writer.writerows(report_rows)
    logger.info("Report written to %s", REPORT_PATH)


def main():
    parser = argparse.ArgumentParser(description="Backfill users → accounts + tenant_memberships (IAM v2)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview without writing")
    group.add_argument("--execute", action="store_true", help="Execute the backfill")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "EXECUTE"
    logger.info("Starting backfill — mode: %s", mode)
    backfill(dry_run=args.dry_run)
    logger.info("Done")


if __name__ == "__main__":
    main()
