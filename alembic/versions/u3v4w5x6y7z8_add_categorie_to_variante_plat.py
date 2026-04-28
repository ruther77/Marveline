"""Add categorie column to restaurant_variantes_plat.

Revision ID: u3v4w5x6y7z8
Revises: t2u3v4w5x6y7
Create Date: 2026-03-11

Expand-only migration : ADD COLUMN nullable.
Rollback : DROP COLUMN (aucune donnée critique dans cette colonne optionnelle).
"""
from alembic import op
import sqlalchemy as sa

revision = 'u3v4w5x6y7z8'
down_revision = 't2u3v4w5x6y7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'restaurant_variantes_plat',
        sa.Column('categorie', sa.String(50), nullable=True,
                  comment="Catégorie de l'article (ex: 'softs', 'alcools', 'jus')"),
    )


def downgrade() -> None:
    op.drop_column('restaurant_variantes_plat', 'categorie')
