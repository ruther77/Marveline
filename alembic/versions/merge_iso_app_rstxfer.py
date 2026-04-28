"""Merge des heads iso_app_01 et rstxfer.

Revision ID: merge_isoapp_rstxfer
Revises: iso_app_01, rstxfer
Create Date: 2026-04-15 00:00:00.000000

Merge sans op : réunit les deux branches divergentes.
"""
from typing import Sequence, Union

revision: str = "merge_isoapp_rstxfer"
down_revision: Union[str, None, tuple] = ("iso_app_01", "rstxfer")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
