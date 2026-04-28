"""merge_heads_product_images

Revision ID: 906dc9836bab
Revises: p3q4r5s6t7u8, s5t6u7v8w9x0
Create Date: 2026-02-22 23:27:40.917330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '906dc9836bab'
down_revision: Union[str, None] = ('p3q4r5s6t7u8', 's5t6u7v8w9x0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
