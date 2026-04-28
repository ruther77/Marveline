"""add_damage_types_table

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-02-18 03:00:00.000000

Crée la table damage_types et ajoute la FK sur invoice_charges.damage_type_id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'damage_types',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('default_fee_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_damage_type_tenant_name'),
        sa.CheckConstraint('default_fee_cents >= 0', name='check_damage_type_fee_positive'),
    )
    op.create_index('ix_damage_types_tenant', 'damage_types', ['tenant_id'])

    # Ajout FK sur colonne damage_type_id déjà existante dans invoice_charges
    op.create_foreign_key(
        'fk_invoice_charges_damage_type_id',
        'invoice_charges',
        'damage_types',
        ['damage_type_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_invoice_charges_damage_type_id',
        'invoice_charges',
        type_='foreignkey',
    )
    op.drop_index('ix_damage_types_tenant', table_name='damage_types')
    op.drop_table('damage_types')
