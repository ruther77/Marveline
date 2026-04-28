"""merge_heads_fk_devis_timeline

Revision ID: e159e1c66a61
Revises: 6357d6fd9048, z7a8b9c0d1e2
Create Date: 2026-02-24 13:40:58.421310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e159e1c66a61'
down_revision: Union[str, None] = ('6357d6fd9048', 'z7a8b9c0d1e2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
