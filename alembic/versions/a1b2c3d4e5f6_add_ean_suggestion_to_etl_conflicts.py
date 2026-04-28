"""add_ean_suggestion_to_etl_conflicts

Revision ID: b7c8d9e0f1a2
Revises: u3v4w5x6y7z8
Create Date: 2026-03-11

Expand — ajout des colonnes ean_a, ean_b, suggestion à etl_conflicts.
Colonnes nullable : aucun backfill requis, pas de verrouillage de table.

Références :
    Gap 6 — résolution UI opérateur : suggestion dérivable depuis type_conflit,
             ean_a / ean_b pour les conflits EAN_COLLISION.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c8d9e0f1a2'
down_revision = 'u3v4w5x6y7z8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'etl_conflicts',
        sa.Column('ean_a', sa.Text(), nullable=True,
                  comment="EAN de l'entrée entrante (utile pour type EAN_COLLISION)"),
    )
    op.add_column(
        'etl_conflicts',
        sa.Column('ean_b', sa.Text(), nullable=True,
                  comment="EAN de l'entrée catalogue existante (utile pour type EAN_COLLISION)"),
    )
    op.add_column(
        'etl_conflicts',
        sa.Column('suggestion', sa.String(20), nullable=True,
                  comment="Suggestion automatique ETL : MERGED | KEPT_SEPARATE — dérivée depuis type_conflit"),
    )


def downgrade() -> None:
    op.drop_column('etl_conflicts', 'suggestion')
    op.drop_column('etl_conflicts', 'ean_b')
    op.drop_column('etl_conflicts', 'ean_a')
