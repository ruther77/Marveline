"""IAM v2 contract : DROP users_deprecated table.

Strategie expand/contract — phase finale.
A executer UNIQUEMENT apres :
  1. Backfill valide en production (Lot 6)
  2. Frontend 100% sur IAM v2 (Lot 5)
  3. 30 jours sans incident depuis le rename (Lot 7 expand)

ATTENTION : cette migration est IRREVERSIBLE (pas de downgrade).

Revision ID: h5i6j7k8l9m0
Revises: g4h5i6j7k8l9
"""
from alembic import op

revision = "h5i6j7k8l9m0"
down_revision = "g4h5i6j7k8l9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("users_deprecated")


def downgrade() -> None:
    raise RuntimeError(
        "Irreversible migration — users_deprecated data has been dropped. "
        "Restore from backup if needed."
    )
