"""add_customer_types_and_notes

Revision ID: a3b4c5d6e7f8
Revises: b1c2d3e4f5a6, z9a0b1c2d3e4, f66e752f8495
Create Date: 2026-03-01 00:00:00.000000

Expand/contract — 3 changements :
  1. ADD COLUMN customers.notes (TEXT nullable) — non destructif
  2. DROP + ADD check_customer_type_valid : IN ('individual', 'company', 'professional', 'association')
  3. DROP + ADD check_customer_data_coherence : professional/association → company_name requis

Rollback safe : downgrade restaure les contraintes à 2 types + supprime la colonne notes.
"""
from typing import Union
from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, tuple] = ("b1c2d3e4f5a6", "z9a0b1c2d3e4", "f66e752f8495")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ajout colonne notes (expand — non destructif)
    op.add_column(
        "customers",
        sa.Column("notes", sa.String(2000), nullable=True, comment="Note interne (non visible client)")
    )

    # 2. Mise à jour contrainte check_customer_type_valid
    op.drop_constraint("check_customer_type_valid", "customers", type_="check")
    op.create_check_constraint(
        "check_customer_type_valid",
        "customers",
        "customer_type IN ('individual', 'company', 'professional', 'association')"
    )

    # 3. Mise à jour contrainte check_customer_data_coherence
    op.drop_constraint("check_customer_data_coherence", "customers", type_="check")
    op.create_check_constraint(
        "check_customer_data_coherence",
        "customers",
        "(customer_type='individual' AND first_name IS NOT NULL AND last_name IS NOT NULL) "
        "OR (customer_type IN ('company', 'professional', 'association') AND company_name IS NOT NULL)"
    )


def downgrade() -> None:
    # 3. Restaurer contrainte check_customer_data_coherence (2 types)
    op.drop_constraint("check_customer_data_coherence", "customers", type_="check")
    op.create_check_constraint(
        "check_customer_data_coherence",
        "customers",
        "(customer_type='individual' AND first_name IS NOT NULL AND last_name IS NOT NULL) "
        "OR (customer_type='company' AND company_name IS NOT NULL)"
    )

    # 2. Restaurer contrainte check_customer_type_valid (2 types)
    op.drop_constraint("check_customer_type_valid", "customers", type_="check")
    op.create_check_constraint(
        "check_customer_type_valid",
        "customers",
        "customer_type IN ('individual', 'company')"
    )

    # 1. Supprimer colonne notes
    op.drop_column("customers", "notes")
