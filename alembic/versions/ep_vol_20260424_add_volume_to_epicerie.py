"""add volume_unitaire_ml to epicerie_produits

Revision ID: ep_vol_20260424
Revises: colisage_20260423
Create Date: 2026-04-24

Contexte : Phase P0 audit 2026-04-24 a rempli catalogue_produits.volume_unitaire_ml
à 71% (1173/1652). Le champ n'existait pas côté épicerie, donc non propagé et
non affiché sur /inventaire. Cette migration l'ajoute (EXPAND pur nullable).

Rollback : DROP COLUMN non destructif.
"""
from alembic import op
import sqlalchemy as sa


revision = 'ep_vol_20260424'
down_revision = 'seed_vendors_20260423'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'epicerie_produits',
        sa.Column(
            'volume_unitaire_ml', sa.Integer(), nullable=True,
            comment="Volume unitaire en mL (ex: 750 pour 75cL, 1000 pour 1L). "
                    "Propagé depuis catalogue_produits.volume_unitaire_ml au sync.",
        ),
    )


def downgrade() -> None:
    op.drop_column('epicerie_produits', 'volume_unitaire_ml')
