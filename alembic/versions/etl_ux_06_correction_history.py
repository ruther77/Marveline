"""Add etl_correction_history table for auto-learning corrections.

Revision ID: etl_ux_06
Revises: etl_ux_05
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = "etl_ux_06"
down_revision = "etl_ux_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etl_correction_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("designation_norm", sa.Text(), nullable=False),
        sa.Column("field_corrected", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=False),
        sa.Column("etl_import_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("idx_etl_correction_designation", "etl_correction_history", ["designation_norm"])
    op.create_index("idx_etl_correction_field", "etl_correction_history", ["field_corrected"])


def downgrade() -> None:
    op.drop_index("idx_etl_correction_field", "etl_correction_history")
    op.drop_index("idx_etl_correction_designation", "etl_correction_history")
    op.drop_table("etl_correction_history")
