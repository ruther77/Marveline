"""merge_heads_phase4_variants_users

Revision ID: f66e752f8495
Revises: 4115e0373d57, d7e8f9a0b1c2
Create Date: 2026-02-17 16:55:07.881176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f66e752f8495'
down_revision: Union[str, None] = ('4115e0373d57', 'd7e8f9a0b1c2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
