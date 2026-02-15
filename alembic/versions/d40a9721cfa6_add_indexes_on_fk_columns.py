"""add_indexes_on_fk_columns

Revision ID: d40a9721cfa6
Revises: b03b473d5966
Create Date: 2026-02-15 12:47:28.364588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd40a9721cfa6'
down_revision: Union[str, None] = 'b03b473d5966'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes on foreign key columns for better JOIN performance.

    Adds indexes on 4 FK columns:
    - categories.parent_id
    - reservations.customer_id
    - reservation_lines.reservation_id
    - reservation_lines.product_id

    Note: bundle_items.bundle_id et bundle_items.product_id ont déjà index=True
    dans le model, donc indexes créés automatiquement par migration de table.
    """
    # Category FK index (self-referential)
    op.create_index(
        'ix_categories_parent_id',
        'categories',
        ['parent_id']
    )

    # Reservation FK index
    op.create_index(
        'ix_reservations_customer_id',
        'reservations',
        ['customer_id']
    )

    # ReservationLine FK indexes
    op.create_index(
        'ix_reservation_lines_reservation_id',
        'reservation_lines',
        ['reservation_id']
    )
    op.create_index(
        'ix_reservation_lines_product_id',
        'reservation_lines',
        ['product_id']
    )


def downgrade() -> None:
    """Remove indexes on foreign key columns."""
    # Drop in reverse order
    op.drop_index('ix_reservation_lines_product_id', 'reservation_lines')
    op.drop_index('ix_reservation_lines_reservation_id', 'reservation_lines')
    op.drop_index('ix_reservations_customer_id', 'reservations')
    op.drop_index('ix_categories_parent_id', 'categories')
    # bundle_items indexes gérés par le model (index=True), pas par cette migration
