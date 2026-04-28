"""add_invoice_charges_table

Revision ID: c7d8e9f0a1b2
Revises: e7f8a9b0c1d2
Create Date: 2026-02-18 10:00:00.000000

Ajoute la table invoice_charges pour les charges additionnelles (dommages, main-d'œuvre).
Migration expand-only (additive) — aucune colonne supprimée.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'invoice_charges',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('invoice_id', sa.BigInteger(), nullable=False),
        sa.Column('charge_type', sa.String(length=20), nullable=False,
                  comment='Type de charge : DAMAGE ou LABOR'),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False,
                  comment='Montant de la charge en centimes (> 0)'),
        sa.Column('description', sa.String(length=500), nullable=False,
                  comment='Description de la charge'),
        sa.Column('hours', sa.Numeric(precision=5, scale=2), nullable=True,
                  comment="Nombre d'heures (LABOR uniquement)"),
        sa.Column('day_type', sa.String(length=10), nullable=True,
                  comment='Type de jour : weekday, weekend, night'),
        sa.Column('damage_type_id', sa.BigInteger(), nullable=True,
                  comment='ID du type de dommage (optionnel, Session I)'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('amount_cents > 0', name='check_charge_amount_positive'),
        sa.CheckConstraint(
            "charge_type IN ('DAMAGE', 'LABOR')",
            name='check_charge_type_valid'
        ),
        sa.CheckConstraint(
            "day_type IS NULL OR day_type IN ('weekday', 'weekend', 'night')",
            name='check_charge_day_type_valid'
        ),
        sa.ForeignKeyConstraint(
            ['invoice_id'], ['invoices.id'],
            ondelete='RESTRICT',
            name='fk_invoice_charges_invoice_id'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_invoice_charges_tenant_invoice',
        'invoice_charges',
        ['tenant_id', 'invoice_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_invoice_charges_tenant_invoice', table_name='invoice_charges')
    op.drop_table('invoice_charges')
