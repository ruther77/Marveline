"""add delivery guards settings to tenant_settings

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-04-26

Ajoute :
  - block_delivery_without_advance : bloque /deliver si acompte non payé
  - require_signature_before_delivery : exige signature_url avant /deliver

Les deux true par défaut (bonne pratique loueur événementiel).
Désactivable par tenant pour les modèles B2B sur compte courant.
"""
from alembic import op
import sqlalchemy as sa

revision = 'v2w3x4y5z6a7'
down_revision = 'u1v2w3x4y5z6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tenant_settings',
        sa.Column(
            'block_delivery_without_advance', sa.Boolean(),
            nullable=False, server_default=sa.text('true'),
            comment="Bloque /deliver si acompte non encaissé.",
        ),
    )
    op.add_column(
        'tenant_settings',
        sa.Column(
            'require_signature_before_delivery', sa.Boolean(),
            nullable=False, server_default=sa.text('true'),
            comment="Exige signature_url avant /deliver.",
        ),
    )


def downgrade() -> None:
    op.drop_column('tenant_settings', 'require_signature_before_delivery')
    op.drop_column('tenant_settings', 'block_delivery_without_advance')
