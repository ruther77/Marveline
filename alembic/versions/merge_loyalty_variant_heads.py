"""merge loyalty + variant_devis heads

Revision ID: merge_loy_var01
Revises: dev01_add_variant_id_dl, loyalty01
Create Date: 2026-03-25
"""
from alembic import op

revision = "merge_loy_var01"
down_revision = ("dev01_add_variant_id_dl", "loyalty01")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
