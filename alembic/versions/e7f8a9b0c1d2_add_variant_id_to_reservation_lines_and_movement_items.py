"""add_variant_id_to_reservation_lines_and_movement_items

Revision ID: e7f8a9b0c1d2
Revises: f66e752f8495
Create Date: 2026-02-17 10:00:00.000000

Ajoute variant_id (FK -> product_variants) sur reservation_lines et movement_items.
Supprime product_variation_id (orphelin sans FK) sur movement_items.

Strategie expand-only : variant_id est nullable -> aucun breaking change sur les donnees existantes.
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'f66e752f8495'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # reservation_lines -- ajout variant_id
    # -----------------------------------------------------------------------
    op.add_column(
        'reservation_lines',
        sa.Column(
            'variant_id',
            sa.Integer(),
            nullable=True,
            comment='Variante couleur choisie (nullable si produit sans variantes)'
        )
    )
    op.create_foreign_key(
        'fk_reservation_lines_variant_id',
        'reservation_lines',
        'product_variants',
        ['variant_id'],
        ['id'],
        ondelete='RESTRICT'
    )
    op.create_index(
        'ix_reservation_lines_variant_id',
        'reservation_lines',
        ['variant_id']
    )

    # -----------------------------------------------------------------------
    # movement_items -- ajout variant_id + suppression product_variation_id
    # -----------------------------------------------------------------------
    op.add_column(
        'movement_items',
        sa.Column(
            'variant_id',
            sa.Integer(),
            nullable=True,
            comment='Variante couleur du produit (remplace product_variation_id)'
        )
    )
    op.create_foreign_key(
        'fk_movement_items_variant_id',
        'movement_items',
        'product_variants',
        ['variant_id'],
        ['id'],
        ondelete='RESTRICT'
    )
    op.create_index(
        'ix_movement_items_variant_id',
        'movement_items',
        ['variant_id']
    )

    # Suppression de l'orphelin product_variation_id (aucune FK, aucune donnee reelle)
    op.drop_column('movement_items', 'product_variation_id')


def downgrade() -> None:
    # Restaurer product_variation_id
    op.add_column(
        'movement_items',
        sa.Column(
            'product_variation_id',
            sa.Integer(),
            nullable=True,
            comment='Reference variation produit (pas de FK) -- LEGACY'
        )
    )
    op.drop_constraint('fk_movement_items_variant_id', 'movement_items', type_='foreignkey')
    op.drop_index('ix_movement_items_variant_id', table_name='movement_items')
    op.drop_column('movement_items', 'variant_id')

    op.drop_constraint('fk_reservation_lines_variant_id', 'reservation_lines', type_='foreignkey')
    op.drop_index('ix_reservation_lines_variant_id', table_name='reservation_lines')
    op.drop_column('reservation_lines', 'variant_id')
