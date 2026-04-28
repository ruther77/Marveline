"""restaurant_commandes : ajoute sumup_order_id (UUID pour idempotence)
+ date_ouverture (timestamp de l'ouverture réelle côté POS, différent de
created_at qui tracke quand la ligne DB est insérée).

Revision ID: sumup_cmd_20260424
Revises: prix_hist_journal_20260424
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa


revision = 'sumup_cmd_20260424'
down_revision = 'prix_hist_journal_20260424'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'restaurant_commandes',
        sa.Column('sumup_order_id', sa.String(100), nullable=True,
                  comment='UUID commande SumUp (idempotence import)'),
    )
    op.add_column(
        'restaurant_commandes',
        sa.Column('date_ouverture', sa.DateTime(timezone=True), nullable=True,
                  comment="Date réelle d'ouverture côté POS (vs created_at qui tracke l'insert DB)"),
    )
    op.create_index(
        'uq_commandes_sumup_order',
        'restaurant_commandes',
        ['sumup_order_id'],
        unique=True,
        postgresql_where=sa.text('sumup_order_id IS NOT NULL'),
    )


def downgrade():
    op.drop_index('uq_commandes_sumup_order', table_name='restaurant_commandes')
    op.drop_column('restaurant_commandes', 'date_ouverture')
    op.drop_column('restaurant_commandes', 'sumup_order_id')
