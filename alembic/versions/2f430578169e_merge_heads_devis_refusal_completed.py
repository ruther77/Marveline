"""merge_heads_devis_refusal_completed

Revision ID: 2f430578169e
Revises: ab12cd34ef56, q6r7s8t9u0v1
Create Date: 2026-03-04 10:06:18.201334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f430578169e'
down_revision: Union[str, None] = ('ab12cd34ef56', 'q6r7s8t9u0v1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
