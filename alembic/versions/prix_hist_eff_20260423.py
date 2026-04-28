"""epicerie_prix_historique : add effective_date + purge anciens enregistrements

Revision ID: prix_hist_eff_20260423
Revises: cat_vol_20260423
Create Date: 2026-04-23

Strategy:
  - EXPAND : ajout colonne `effective_date DATE NULL` (date facture, ou date
    saisie pour entrée manuelle). Indexée pour tri DESC dans l'historique.
  - PURGE : suppression de toutes les lignes pré-existantes — le service
    `recevoir_facture_etl` insérait un historique pour TOUS les produits actifs
    à chaque ETL avec la mauvaise référence et sans la date facture, ce qui a
    pollué la table. L'utilisateur peut re-valider les imports pour reconstruire
    un historique propre via le workflow corrigé.

Rollback : DROP COLUMN seulement (les données purgées ne sont pas restaurables).
"""
from alembic import op
import sqlalchemy as sa


revision = 'prix_hist_eff_20260423'
down_revision = 'cat_vol_20260423'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Purge des entrées polluées par l'ancien workflow (bug : insert pour tous
    # les produits à chaque validation ETL, pas seulement ceux de la facture).
    op.execute("DELETE FROM epicerie_prix_historique")

    op.add_column(
        'epicerie_prix_historique',
        sa.Column(
            'effective_date', sa.Date(), nullable=True,
            comment="Date à laquelle le prix s'applique (date facture pour ETL, "
                    "date saisie pour entrée manuelle). NULL = retomber sur created_at.",
        ),
    )
    op.create_index(
        'idx_prix_hist_effective',
        'epicerie_prix_historique',
        ['tenant_id', 'produit_id', 'effective_date'],
    )


def downgrade() -> None:
    op.drop_index('idx_prix_hist_effective', table_name='epicerie_prix_historique')
    op.drop_column('epicerie_prix_historique', 'effective_date')
