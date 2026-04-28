"""add_address_postal_code_to_users

Revision ID: 4115e0373d57
Revises: b5c6d7e8f9a0
Create Date: 2026-02-17 13:52:42.820454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4115e0373d57'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'address', sa.String(500), nullable=True,
        comment="Adresse postale de l'utilisateur"
    ))
    op.add_column('users', sa.Column(
        'postal_code', sa.String(20), nullable=True,
        comment='Code postal'
    ))


def downgrade() -> None:
    op.drop_column('users', 'postal_code')
    op.drop_column('users', 'address')
