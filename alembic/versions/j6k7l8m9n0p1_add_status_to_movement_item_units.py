"""add status_before and status_after to movement_item_units

Revision ID: j6k7l8m9n0p1
Revises: i5j6k7l8m9n0
Create Date: 2026-02-18 00:00:00.000000

"""
from typing import Union
from alembic import op
import sqlalchemy as sa


revision: str = 'j6k7l8m9n0p1'
down_revision: Union[str, None] = 'i5j6k7l8m9n0'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        'movement_item_units',
        sa.Column('status_before', sa.String(20), nullable=True,
                  comment='Statut StockItem avant la transition'),
    )
    op.add_column(
        'movement_item_units',
        sa.Column('status_after', sa.String(20), nullable=True,
                  comment='Statut StockItem après la transition'),
    )


def downgrade() -> None:
    op.drop_column('movement_item_units', 'status_after')
    op.drop_column('movement_item_units', 'status_before')
