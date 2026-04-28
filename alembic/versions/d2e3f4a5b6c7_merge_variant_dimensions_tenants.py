"""merge_variant_dimensions_tenants

Revision ID: d2e3f4a5b6c7
Revises: a0b1c2d3e4f5, c1d2e3f4a5b6
Create Date: 2026-03-02

Merge : a0b1c2d3e4f5 (add_variant_dimensions) + c1d2e3f4a5b6 (add_tenants_table)
"""
from typing import Sequence, Union

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None, tuple] = ("a0b1c2d3e4f5", "c1d2e3f4a5b6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
