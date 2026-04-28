"""catalogue_produit_colisages : pivot colisages observés par produit.

Le colisage n'est plus un critère discriminant du produit logique (même
produit en pack 18/20/24). Cette table trace quels colisages ont été
observés pour un produit, avec source fournisseur + first/last seen.

Revision ID: cat_colisages_20260424
Revises: cat_eans_20260424
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa


revision = 'cat_colisages_20260424'
down_revision = 'cat_eans_20260424'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'catalogue_produit_colisages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('catalogue_produit_id', sa.BigInteger(), nullable=False),
        sa.Column('colisage', sa.Integer(), nullable=False),
        sa.Column('source_fournisseur', sa.String(length=50), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['catalogue_produit_id'], ['catalogue_produits.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'catalogue_produit_id', 'colisage', 'source_fournisseur',
            name='uq_cat_prod_colisage_source',
        ),
    )
    op.create_index(
        'ix_cat_prod_colisages_produit',
        'catalogue_produit_colisages',
        ['catalogue_produit_id'],
    )


def downgrade():
    op.drop_index(
        'ix_cat_prod_colisages_produit',
        table_name='catalogue_produit_colisages',
    )
    op.drop_table('catalogue_produit_colisages')
