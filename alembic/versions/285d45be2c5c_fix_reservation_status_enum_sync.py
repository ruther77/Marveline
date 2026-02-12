"""fix_reservation_status_enum_sync

Revision ID: 285d45be2c5c
Revises: 3dce6788397a
Create Date: 2026-02-12 16:02:10.581000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '285d45be2c5c'
down_revision: Union[str, None] = '3dce6788397a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Synchronise ReservationStatus enum avec contrainte DB.

    Problème résolu:
        - Python Enum: draft, confirmed, delivered, returned, cancelled
        - DB ancienne: draft, confirmed, in_progress, completed, cancelled

    Solution (expand/contract):
        1. Drop contrainte existante
        2. Migrer données: in_progress → delivered, completed → returned
        3. Créer nouvelle contrainte alignée avec Python enum
    """
    # Étape 1: Supprimer ancienne contrainte
    op.drop_constraint(
        'check_reservation_status_valid',
        'reservations',
        type_='check'
    )

    # Étape 2: Migrer données existantes (si elles existent)
    # in_progress → delivered (vaisselle livrée au client)
    op.execute("""
        UPDATE reservations
        SET status = 'delivered'
        WHERE status = 'in_progress'
    """)

    # completed → returned (vaisselle retournée par le client)
    op.execute("""
        UPDATE reservations
        SET status = 'returned'
        WHERE status = 'completed'
    """)

    # Étape 3: Créer nouvelle contrainte avec statuts Python enum
    op.create_check_constraint(
        'check_reservation_status_valid',
        'reservations',
        "status IN ('draft', 'confirmed', 'delivered', 'returned', 'cancelled')"
    )


def downgrade() -> None:
    """Rollback: revenir aux anciens statuts DB.

    WARNING: Perte de clarté métier (in_progress/completed moins explicites).
    """
    # Étape 1: Supprimer nouvelle contrainte
    op.drop_constraint(
        'check_reservation_status_valid',
        'reservations',
        type_='check'
    )

    # Étape 2: Migrer données vers anciens statuts
    # delivered → in_progress
    op.execute("""
        UPDATE reservations
        SET status = 'in_progress'
        WHERE status = 'delivered'
    """)

    # returned → completed
    op.execute("""
        UPDATE reservations
        SET status = 'completed'
        WHERE status = 'returned'
    """)

    # Étape 3: Recréer ancienne contrainte
    op.create_check_constraint(
        'check_reservation_status_valid',
        'reservations',
        "status IN ('draft', 'confirmed', 'in_progress', 'completed', 'cancelled')"
    )
