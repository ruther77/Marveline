"""add volume_unitaire_ml to catalogue_produits

Revision ID: cat_vol_20260423
Revises: resto_ing_code_20260422
Create Date: 2026-04-23

Strategy: EXPAND pur (colonne nullable ajoutée, pas de backfill bloquant,
pas de contrainte). Les lignes existantes restent NULL et seront backfillées
par le script `scripts/backfill_catalogue_designation.py` qui parse la
désignation via le tokenizer METRO pour extraire le volume.

Rollback : DROP COLUMN non destructif (l'info est reconstructible).
"""
from alembic import op
import sqlalchemy as sa


revision = 'cat_vol_20260423'
down_revision = 'resto_ing_code_20260422'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'catalogue_produits',
        sa.Column(
            'volume_unitaire_ml', sa.Integer(), nullable=True,
            comment="Volume unitaire en mL. Ex: 330 pour 33cL, 1500 pour 1.5L. "
                    "Alimenté par l'ETL ou le backfill script.",
        ),
    )


def downgrade() -> None:
    op.drop_column('catalogue_produits', 'volume_unitaire_ml')
