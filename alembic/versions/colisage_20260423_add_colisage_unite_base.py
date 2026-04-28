"""add colisage + unite_base to catalogue & epicerie produits

Revision ID: colisage_20260423
Revises: prix_hist_eff_20260423
Create Date: 2026-04-23

Contexte : la page /inventaire affiche un prix de vente "par U" sans indiquer
ce que représente physiquement cette U. L'audit 2026-04-23 a révélé :
  - 100 % des produits épicerie ont `unite_vente='U'` (valeur par défaut)
  - Le champ `colisage` (int) n'est jamais persisté dans catalogue_produits
  - Seule trace du colisage = `conditionnement` (texte), absent sur 17-44 %
    des lignes selon la source (METRO/TAIYAT/EUROCIEL)

Stratégie : EXPAND pur
  - 3 colonnes nullable ajoutées, pas de contrainte, pas de backfill bloquant
  - Lignes existantes restent NULL
  - Backfill séparé via scripts/etl/sync_catalogue_to_epicerie.py (étape 2)

Colonnes ajoutées :
  1. catalogue_produits.colisage       INT NULL
     → nombre d'unités de base par colis reçu (ex: 150 sucettes, 6 bouteilles)
  2. epicerie_produits.colisage         INT NULL
     → même chose, propagé depuis le catalogue au sync
  3. epicerie_produits.unite_base       VARCHAR(20) NULL
     → unité physique réelle ('piece', 'kg', 'L', 'g', 'cL', 'mL', 'colis')
       distincte de unite_vente qui reste l'unité UI/caisse

Rollback : DROP COLUMN x3 non destructif.
"""
from alembic import op
import sqlalchemy as sa


revision = 'colisage_20260423'
down_revision = 'prix_hist_eff_20260423'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'catalogue_produits',
        sa.Column(
            'colisage', sa.Integer(), nullable=True,
            comment="Nombre d'unités de base par colis reçu. "
                    "Ex: 150 (sucettes par sachet), 6 (bouteilles par carton). "
                    "Extrait du libellé par le parser ETL.",
        ),
    )
    op.add_column(
        'epicerie_produits',
        sa.Column(
            'colisage', sa.Integer(), nullable=True,
            comment="Colisage propagé depuis catalogue_produits.colisage au sync. "
                    "Rend visible ce que représente 1 unité de vente.",
        ),
    )
    op.add_column(
        'epicerie_produits',
        sa.Column(
            'unite_base', sa.String(length=20), nullable=True,
            comment="Unité physique réelle ('piece', 'kg', 'L', 'g', 'cL', 'mL', 'colis'). "
                    "Distincte de unite_vente (unité UI/caisse). "
                    "Propagée depuis catalogue_produits.unite_base au sync.",
        ),
    )


def downgrade() -> None:
    op.drop_column('epicerie_produits', 'unite_base')
    op.drop_column('epicerie_produits', 'colisage')
    op.drop_column('catalogue_produits', 'colisage')
