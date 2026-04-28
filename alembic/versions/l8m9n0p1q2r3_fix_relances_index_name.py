"""fix relances index name conflict with TenantMixin auto-index

Revision ID: l8m9n0p1q2r3
Revises: k7l8m9n0p1q2
Create Date: 2026-02-20

Renomme ix_relances_tenant_id (tenant_id, id) → ix_relances_tenant_id_composite
pour éviter le conflit avec l'index auto ix_relances_tenant_id sur (tenant_id)
généré par TenantMixin (index=True).
"""
from typing import Union
from alembic import op


revision: str = 'l8m9n0p1q2r3'
down_revision: Union[str, None] = 'k7l8m9n0p1q2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_relances_tenant_id', table_name='relances')
    op.create_index('ix_relances_tenant_id_composite', 'relances', ['tenant_id', 'id'])
    # L'index simple (tenant_id) est géré par le ORM via TenantMixin — pas recréé ici


def downgrade() -> None:
    op.drop_index('ix_relances_tenant_id_composite', table_name='relances')
    op.create_index('ix_relances_tenant_id', 'relances', ['tenant_id', 'id'])
