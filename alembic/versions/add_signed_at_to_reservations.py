"""add signed_at to reservations

Revision ID: add_signed_at_res01
Revises: merge_all_heads_01
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "add_signed_at_res01"
down_revision = "merge_all_heads_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reservations", sa.Column("signed_at", sa.DateTime(), nullable=True, comment="Horodatage signature client"))


def downgrade() -> None:
    op.drop_column("reservations", "signed_at")
