"""Add printer + commerce columns to tenant_settings.

Config imprimante ESC/POS (host, port) et infos commerce (nom, adresse,
SIRET, tél) pour en-tête tickets.

Revision ID: b2print3conf4ts
Revises: a1pin2dev3auth
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2print3conf4ts'
down_revision = 'a1pin2dev3auth'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenant_settings', sa.Column('printer_host', sa.String(100), nullable=True, comment='IP imprimante ticket'))
    op.add_column('tenant_settings', sa.Column('printer_port', sa.Integer(), nullable=False, server_default='9100', comment='Port TCP imprimante'))
    op.add_column('tenant_settings', sa.Column('nom_commerce', sa.String(200), nullable=True, comment='Nom affiché sur ticket'))
    op.add_column('tenant_settings', sa.Column('adresse', sa.String(500), nullable=True, comment='Adresse sur ticket'))
    op.add_column('tenant_settings', sa.Column('siret', sa.String(20), nullable=True, comment='SIRET sur ticket'))
    op.add_column('tenant_settings', sa.Column('telephone', sa.String(20), nullable=True, comment='Tél. sur ticket'))


def downgrade() -> None:
    op.drop_column('tenant_settings', 'telephone')
    op.drop_column('tenant_settings', 'siret')
    op.drop_column('tenant_settings', 'adresse')
    op.drop_column('tenant_settings', 'nom_commerce')
    op.drop_column('tenant_settings', 'printer_port')
    op.drop_column('tenant_settings', 'printer_host')
