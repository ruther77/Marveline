"""merge etl_ux_03 + multi_ean_01

Revision ID: merge02
Revises: etl_ux_03, multi_ean_01
Create Date: 2026-04-10 00:00:00.000000
"""
from alembic import op

revision = "merge02"
down_revision = ("etl_ux_03", "multi_ean_01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
