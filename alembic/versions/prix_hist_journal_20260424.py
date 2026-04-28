"""epicerie_prix_historique : journal d'événements (source_fournisseur + etl_import_id)

Passage de "compressé par changement de prix" à "un point par facture".
Ajoute source_fournisseur et etl_import_id pour tracer chaque entrée.

Revision ID: prix_hist_journal_20260424
Revises: cat_colisages_20260424
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa


revision = 'prix_hist_journal_20260424'
down_revision = 'cat_colisages_20260424'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'epicerie_prix_historique',
        sa.Column('source_fournisseur', sa.String(50), nullable=True,
                  comment='Code fournisseur (METRO, TAIYAT, ETHAN, EUROCIEL, ...)'),
    )
    op.add_column(
        'epicerie_prix_historique',
        sa.Column('etl_import_id', sa.BigInteger(), nullable=True,
                  comment='FK vers etl_imports.id (nullable : entrées manuelles sans import)'),
    )
    op.create_foreign_key(
        'fk_prix_hist_etl_import',
        'epicerie_prix_historique', 'etl_imports',
        ['etl_import_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'idx_prix_hist_etl_import',
        'epicerie_prix_historique',
        ['etl_import_id'],
    )


def downgrade():
    op.drop_index('idx_prix_hist_etl_import', table_name='epicerie_prix_historique')
    op.drop_constraint('fk_prix_hist_etl_import', 'epicerie_prix_historique', type_='foreignkey')
    op.drop_column('epicerie_prix_historique', 'etl_import_id')
    op.drop_column('epicerie_prix_historique', 'source_fournisseur')
