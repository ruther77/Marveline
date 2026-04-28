"""IAM v2 expand : rename users → users_deprecated.

Strategie expand/contract :
  - Expand (cette migration) : rename table, garder les donnees intactes
  - Contract (migration separee, 30j apres validation prod) : DROP users_deprecated

Prerequis : backfill_users_to_accounts.py execute avec --execute (Lot 6).
Rollback : renommer users_deprecated → users.

Revision ID: g4h5i6j7k8l9
Revises: merge_logi04_rls001
"""
from alembic import op

revision = "g4h5i6j7k8l9"
down_revision = "merge_logi04_rls001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("users", "users_deprecated")
    # Renommer les index et contraintes associes
    op.execute("ALTER INDEX IF EXISTS ix_users_email RENAME TO ix_users_deprecated_email")
    op.execute(
        "ALTER TABLE users_deprecated "
        "RENAME CONSTRAINT uq_users_tenant_email TO uq_users_deprecated_tenant_email"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users_deprecated "
        "RENAME CONSTRAINT uq_users_deprecated_tenant_email TO uq_users_tenant_email"
    )
    op.execute("ALTER INDEX IF EXISTS ix_users_deprecated_email RENAME TO ix_users_email")
    op.rename_table("users_deprecated", "users")
