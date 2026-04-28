"""Migrate notifications.link: /events/ → /reservations/ (data-only, §9.7).

Revision ID: p0q1r2s3t4u5
Revises: ee77ff88gg99
Create Date: 2026-03-06

Nettoyage des liens legacy `/events/{id}` persistés dans notifications.link.
Les liens `/evenements/…` (incidents) ne sont pas modifiés — ils restent canoniques.
"""
from alembic import op


revision = "p0q1r2s3t4u5"
down_revision = "ee77ff88gg99"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE notifications
        SET link = REPLACE(link, '/events/', '/reservations/')
        WHERE link LIKE '/events/%'
    """)


def downgrade() -> None:
    # Downgrade non applicable : on ne peut distinguer les liens /reservations/
    # qui étaient déjà canoniques de ceux migrés. No-op volontaire.
    pass
