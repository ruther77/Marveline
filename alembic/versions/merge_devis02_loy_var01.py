"""Merge devis02 + merge_loy_var01 heads.

Revision ID: merge_all_heads_01
Revises: devis02, merge_loy_var01
Create Date: 2026-03-25
"""
from alembic import op

revision = "merge_all_heads_01"
down_revision = ("devis02", "merge_loy_var01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
