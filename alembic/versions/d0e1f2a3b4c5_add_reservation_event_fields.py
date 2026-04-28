"""add_reservation_event_fields

Revision ID: d0e1f2a3b4c5
Revises: c7d8e9f0a1b2
Create Date: 2026-02-18 12:00:00.000000

Ajoute event_type, event_name, guest_count sur la table reservations.
Migration additive (expand-only) — aucune colonne supprimée.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'reservations',
        sa.Column(
            'event_type',
            sa.String(50),
            nullable=True,
            comment="Type d'événement (mariage, anniversaire, entreprise, autre)"
        )
    )
    op.add_column(
        'reservations',
        sa.Column(
            'event_name',
            sa.String(200),
            nullable=True,
            comment="Nom de l'événement (ex: Mariage Dupont)"
        )
    )
    op.add_column(
        'reservations',
        sa.Column(
            'guest_count',
            sa.Integer,
            nullable=True,
            comment="Nombre d'invités (doit être > 0)"
        )
    )
    op.create_check_constraint(
        'check_reservation_guest_count_positive',
        'reservations',
        'guest_count IS NULL OR guest_count > 0'
    )


def downgrade() -> None:
    op.drop_constraint(
        'check_reservation_guest_count_positive',
        'reservations',
        type_='check'
    )
    op.drop_column('reservations', 'guest_count')
    op.drop_column('reservations', 'event_name')
    op.drop_column('reservations', 'event_type')
