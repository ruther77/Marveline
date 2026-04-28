"""add_fk_reservation_devis_deferrable

Revision ID: 6357d6fd9048
Revises: y6z7a8b9c0d1
Create Date: 2026-02-24 13:03:34.007292

Strategy (expand/contract) :
  Expand  : Ajouter FK nullable DEFERRABLE INITIALLY DEFERRED sur reservations.devis_id.
            DEFERRABLE brise la circularité devis↔reservations au sein d'une même transaction
            (INSERT devis + INSERT reservation dans la même tx ne lève pas de violation FK).
  Rollback: Supprimer la contrainte FK (données intactes).
  Contract: Migration ultérieure pour NOT NULL si besoin métier.

Vérification orphelins avant upgrade :
  SELECT COUNT(*) FROM reservations
  WHERE devis_id IS NOT NULL
  AND devis_id NOT IN (SELECT id FROM devis);
  → 0 (vérifié 2026-02-24)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6357d6fd9048'
down_revision: Union[str, None] = 'y6z7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remplace la FK standard créée par n0p1q2r3s4t5 par une version DEFERRABLE
    op.drop_constraint(
        constraint_name="fk_reservations_devis_id",
        table_name="reservations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        constraint_name="fk_reservations_devis_id",
        source_table="reservations",
        referent_table="devis",
        local_cols=["devis_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    # Rétablit la FK standard (non-DEFERRABLE) de n0p1q2r3s4t5
    op.drop_constraint(
        constraint_name="fk_reservations_devis_id",
        table_name="reservations",
        type_="foreignkey",
    )
    op.create_foreign_key(
        constraint_name="fk_reservations_devis_id",
        source_table="reservations",
        referent_table="devis",
        local_cols=["devis_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
