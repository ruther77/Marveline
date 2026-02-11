"""add_server_defaults_status_condition

Revision ID: cc96cee37419
Revises: 9cc4b58c8f4d
Create Date: 2026-02-12 00:11:18.828635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc96cee37419'
down_revision: Union[str, None] = '9cc4b58c8f4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajouter server_default sur products.condition pour robustesse
    # Garantit la valeur par défaut même en cas d'insertions SQL directes
    op.alter_column(
        'products',
        'condition',
        server_default='bon'
    )

    # Ajouter server_default sur reservations.status
    op.alter_column(
        'reservations',
        'status',
        server_default='draft'
    )

    # Ajouter server_default sur invoices.status
    op.alter_column(
        'invoices',
        'status',
        server_default='draft'
    )


def downgrade() -> None:
    # Supprimer les server_default dans l'ordre inverse
    op.alter_column('invoices', 'status', server_default=None)
    op.alter_column('reservations', 'status', server_default=None)
    op.alter_column('products', 'condition', server_default=None)
