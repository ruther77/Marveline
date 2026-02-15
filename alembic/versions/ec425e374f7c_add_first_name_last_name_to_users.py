"""add_first_name_last_name_to_users

Revision ID: ec425e374f7c
Revises: d40a9721cfa6
Create Date: 2026-02-15 14:22:47.067923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec425e374f7c'
down_revision: Union[str, None] = 'd40a9721cfa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remplace full_name par first_name + last_name.

    Strategy expand/contract:
    1. Ajouter first_name et last_name nullable
    2. Migrer données de full_name → first_name/last_name (split sur espace)
    3. Rendre first_name et last_name NOT NULL
    4. Drop colonne full_name (devient hybrid_property)
    """
    # Étape 1: Ajouter colonnes nullable
    op.add_column('users', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))

    # Étape 2: Migrer données existantes (split full_name sur premier espace)
    # Si full_name = "Jean Dupont", first_name = "Jean", last_name = "Dupont"
    # Si full_name = "Jean Marie Dupont", first_name = "Jean", last_name = "Marie Dupont"
    op.execute("""
        UPDATE users
        SET
            first_name = SPLIT_PART(full_name, ' ', 1),
            last_name = TRIM(SUBSTRING(full_name FROM LENGTH(SPLIT_PART(full_name, ' ', 1)) + 2))
        WHERE full_name IS NOT NULL
    """)

    # Gérer cas où last_name est vide (full_name sans espace)
    op.execute("""
        UPDATE users
        SET last_name = first_name
        WHERE last_name = '' OR last_name IS NULL
    """)

    # Étape 3: Rendre NOT NULL
    op.alter_column('users', 'first_name', nullable=False)
    op.alter_column('users', 'last_name', nullable=False)

    # Étape 4: Drop colonne full_name (devient hybrid_property)
    op.drop_column('users', 'full_name')


def downgrade() -> None:
    """Rollback: recréer full_name depuis first_name + last_name."""
    # Étape 1: Ajouter colonne full_name nullable
    op.add_column('users', sa.Column('full_name', sa.String(length=200), nullable=True))

    # Étape 2: Reconstruire full_name depuis first_name + last_name
    op.execute("""
        UPDATE users
        SET full_name = first_name || ' ' || last_name
    """)

    # Étape 3: Rendre NOT NULL
    op.alter_column('users', 'full_name', nullable=False)

    # Étape 4: Drop first_name et last_name
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
