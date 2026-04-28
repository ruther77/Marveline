"""Add reservation_versions table for line change history.

Revision ID: resa01
Revises: cents02
Create Date: 2026-04-02
"""

import sqlalchemy as sa
from alembic import op

revision = "resa01"
down_revision = "cents02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reservation_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(50), nullable=False, comment="line_added, line_removed, line_updated, status_changed"),
        sa.Column("change_summary", sa.String(500), nullable=True, comment="Description lisible du changement"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False, comment="Snapshot complet lignes + totaux"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_resa_versions_tenant_resa", "reservation_versions", ["tenant_id", "reservation_id"])


def downgrade() -> None:
    op.drop_table("reservation_versions")
