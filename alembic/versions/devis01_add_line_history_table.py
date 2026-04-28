"""Add devis_line_history table (G28).

Historique ligne par ligne des modifications de devis.

Revision ID: devis01
Revises: loyalty01
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

revision = "devis01"
down_revision = "loyalty01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devis_line_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("devis_id", sa.Integer(), nullable=False),
        sa.Column("devis_line_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["devis_id"], ["devis.id"], ondelete="CASCADE"),
        sa.CheckConstraint("action IN ('create', 'update', 'delete')", name="ck_devis_line_history_action"),
    )
    op.create_index("ix_devis_line_history_devis", "devis_line_history", ["devis_id"])
    op.create_index("ix_devis_line_history_line", "devis_line_history", ["devis_line_id"])


def downgrade() -> None:
    op.drop_table("devis_line_history")
