"""add reservation_uplift_pct to tenant_settings

Revision ID: uplift_20260425
Revises: sumup_cmd_20260424
Create Date: 2026-04-25

Contexte : pour les tenants resto/bar qui encaissent une partie significative
de leur CA hors POS (commandes réservées, événements payés à part, prépaiements
en espèces non saisis), on permet d'appliquer un % d'uplift sur le ca_cts
calculé par le dashboard. Pilotage temps réel sans attendre la feature complète
de gestion des réservations.

Default 0 (aucun uplift, POS pur). Set à 12 pour tenant 3 (Restaurant
MassaCorp / L'incontournable) — uplift moyen estimé +12% via réservations
non POS, validé sur ratios métier 2026-04-25.

Rollback : DROP COLUMN, non destructif.
"""
from alembic import op
import sqlalchemy as sa


revision = "uplift_20260425"
down_revision = "sumup_cmd_20260424"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column(
            "reservation_uplift_pct",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="% d'uplift appliqué au CA jour pour intégrer les "
                    "commandes réservées hors POS. 0 = aucun, 12 = +12%.",
        ),
    )
    # Seed initial : tenant 3 (Restaurant) à +12% (estimation moyenne réservations)
    op.execute(
        "UPDATE tenant_settings SET reservation_uplift_pct = 12 WHERE tenant_id = 3"
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "reservation_uplift_pct")
