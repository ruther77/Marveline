"""Merge cents01 + cus01_siret_vat heads.

Revision ID: merge_cents01_cus01
Revises: cents01, cus01_siret_vat
Create Date: 2026-04-02
"""

revision = "merge_cents01_cus01"
down_revision = ("cents01", "cus01_siret_vat")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
