"""Migrate notifications.link: /inventory/stock → /stock/items (data-only, §11.5.2).

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-03-06

Nettoyage des liens legacy `/inventory/stock` persistés dans notifications.link.
Ces liens étaient émis par le dashboard (activity feed low_stock) avant la
migration namespace Inventaire → Stock (§11.1).
"""
from alembic import op


revision = "q1r2s3t4u5v6"
down_revision = "p0q1r2s3t4u5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE notifications
        SET link = REPLACE(link, '/inventory/stock', '/stock/items')
        WHERE link LIKE '/inventory/stock%'
    """)
    op.execute("""
        UPDATE notifications
        SET link = REPLACE(link, '/inventory/movements', '/stock/movements')
        WHERE link LIKE '/inventory/movements%'
    """)


def downgrade() -> None:
    # Downgrade non applicable : on ne peut distinguer les liens /stock/items
    # qui étaient déjà canoniques de ceux migrés. No-op volontaire.
    pass
