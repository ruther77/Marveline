"""merge heads: cgv_tenant_settings + sla_owner_events

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8, a2b3c4d5e6f7
Create Date: 2026-02-23

Merge des deux branches indépendantes.
"""
from alembic import op

revision = "w4x5y6z7a8b9"
down_revision = ("v3w4x5y6z7a8", "a2b3c4d5e6f7")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
