"""add_invoice_type

Revision ID: t0u1v2w3x4y5
Revises: c9d0e1f2a3b4
Create Date: 2026-02-22 00:00:00.000000

Strategy: expand-only
- Ajoute colonne invoice_type (DEFAULT 'full') → backward compatible
- Retire contrainte unique implicite sur reservation_id
- Ajoute contrainte unique composite (tenant_id, reservation_id, invoice_type)

Rollback: drop contrainte composite, recreer unique reservation_id, drop colonne.
"""
from alembic import op
import sqlalchemy as sa

revision = 't0u1v2w3x4y5'
down_revision = 'c0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Ajouter colonne invoice_type avec valeur par défaut 'full'
    op.add_column(
        'invoices',
        sa.Column(
            'invoice_type',
            sa.String(10),
            nullable=False,
            server_default='full',
            comment="Type de facture : full, advance (40%), balance (60%)"
        )
    )

    # 2. Retirer l'index unique implicite créé par unique=True sur reservation_id
    #    PostgreSQL nomme la contrainte avec le pattern : <table>_<col>_key
    op.drop_constraint('invoices_reservation_id_key', 'invoices', type_='unique')

    # 3. Ajouter contrainte unique composite
    op.create_unique_constraint(
        'uq_invoice_tenant_reservation_type',
        'invoices',
        ['tenant_id', 'reservation_id', 'invoice_type']
    )

    # 4. Ajouter CHECK sur invoice_type
    op.create_check_constraint(
        'check_invoice_type_valid',
        'invoices',
        "invoice_type IN ('full', 'advance', 'balance')"
    )


def downgrade() -> None:
    # Inverse
    op.drop_constraint('check_invoice_type_valid', 'invoices', type_='check')
    op.drop_constraint('uq_invoice_tenant_reservation_type', 'invoices', type_='unique')
    op.create_unique_constraint('invoices_reservation_id_key', 'invoices', ['reservation_id'])
    op.drop_column('invoices', 'invoice_type')
