"""add password_change_required to users

Revision ID: b1c2d3e4f5a6
Revises: dd55ee66ff77, cc33dd44ee55, c9d0e1f2a3b4
Create Date: 2026-02-28 00:00:00.000000

Ajout du champ password_change_required sur la table users.
Utilisé par le service HIBP (CaroCorp §7.2 NIVEAU 5) pour marquer
les utilisateurs dont le mot de passe est présent dans des leaks connus.

Stratégie expand/contract : ajout de colonne nullable avec server_default.
Rollback : drop_column (aucune donnée critique perdue).
"""
from alembic import op
import sqlalchemy as sa

revision: str = "b1c2d3e4f5a6"
down_revision = ("dd55ee66ff77", "cc33dd44ee55", "c9d0e1f2a3b4")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_change_required",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "password_change_required")
