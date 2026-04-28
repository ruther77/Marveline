"""add_product_fields_phase2

Revision ID: b5c6d7e8f9a0
Revises: 7b215135cf65
Create Date: 2026-02-17 12:28:14.157773

Ajoute les champs Phase 2 (alignement marveline.fr) sur la table products :
- cleaning_fee : frais nettoyage en centimes (0 = inclus, règle marveline.fr)
- description : description longue nullable
- short_description : description courte nullable (max 500 chars)
- requires_advance_booking_days : délai réservation minimum (90 pour nappages)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = '7b215135cf65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column(
        'cleaning_fee',
        sa.BigInteger(),
        nullable=False,
        server_default='0',
        comment='Frais de nettoyage en centimes (0 = inclus dans le prix)'
    ))
    op.add_column('products', sa.Column(
        'description',
        sa.Text(),
        nullable=True,
        comment='Description longue du produit'
    ))
    op.add_column('products', sa.Column(
        'short_description',
        sa.String(500),
        nullable=True,
        comment='Description courte (utilisée dans les bundles et listes)'
    ))
    op.add_column('products', sa.Column(
        'requires_advance_booking_days',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='Délai minimum de réservation en jours (90 pour nappages, 0 sinon)'
    ))
    op.create_check_constraint(
        'check_product_cleaning_fee_positive',
        'products',
        'cleaning_fee >= 0'
    )
    op.create_check_constraint(
        'check_product_advance_booking_positive',
        'products',
        'requires_advance_booking_days >= 0'
    )


def downgrade() -> None:
    op.drop_constraint('check_product_advance_booking_positive', 'products', type_='check')
    op.drop_constraint('check_product_cleaning_fee_positive', 'products', type_='check')
    op.drop_column('products', 'requires_advance_booking_days')
    op.drop_column('products', 'short_description')
    op.drop_column('products', 'description')
    op.drop_column('products', 'cleaning_fee')
