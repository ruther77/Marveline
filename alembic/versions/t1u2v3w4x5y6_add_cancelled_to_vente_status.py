"""add cancelled to vente status

Revision ID: t1u2v3w4x5y6
Revises: o1p2q3r4s5t6
Create Date: 2026-02-21

Expand migration : ajoute 'cancelled' au CHECK constraint de ventes.status.
Non-destructive — valeur existante non retirée.
"""
from alembic import op

revision = "t1u2v3w4x5y6"
down_revision = "s5t6u7v8w9x0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supprimer l'ancien constraint et en créer un nouveau avec 'cancelled'
    op.drop_constraint("check_vente_status_valid", "ventes", type_="check")
    op.create_check_constraint(
        "check_vente_status_valid",
        "ventes",
        "status IN ('draft','pending','deposit_paid','fully_paid','overdue','refunded','cancelled')",
    )


def downgrade() -> None:
    # Rollback : retirer 'cancelled' de la liste (les lignes cancelled deviendraient invalides)
    op.drop_constraint("check_vente_status_valid", "ventes", type_="check")
    op.create_check_constraint(
        "check_vente_status_valid",
        "ventes",
        "status IN ('draft','pending','deposit_paid','fully_paid','overdue','refunded')",
    )
