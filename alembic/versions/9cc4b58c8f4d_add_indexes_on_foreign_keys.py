"""add_indexes_on_foreign_keys

Revision ID: 9cc4b58c8f4d
Revises: 5cc8547db975
Create Date: 2026-02-12 00:10:28.620307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cc4b58c8f4d'
down_revision: Union[str, None] = '5cc8547db975'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajouter index sur reservations.customer_id pour optimiser les requêtes
    # "Toutes les réservations d'un client" et les FK constraint checks
    op.create_index(
        'ix_reservations_customer_id',
        'reservations',
        ['customer_id'],
        unique=False
    )

    # Ajouter index sur reservation_lines.product_id pour optimiser les requêtes
    # "Toutes les lignes de réservation d'un produit" et les FK constraint checks
    op.create_index(
        'ix_reservation_lines_product_id',
        'reservation_lines',
        ['product_id'],
        unique=False
    )


def downgrade() -> None:
    # Supprimer les indexes dans l'ordre inverse
    op.drop_index('ix_reservation_lines_product_id', table_name='reservation_lines')
    op.drop_index('ix_reservations_customer_id', table_name='reservations')
