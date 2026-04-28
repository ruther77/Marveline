"""add reservation advanced tables

Revision ID: n0p1q2r3s4t5
Revises: m9n0p1q2r3s4
Create Date: 2026-02-20

Tables créées :
- reservation_risks
- reservation_pre_check_items
- reservation_extensions

Colonnes ajoutées sur reservations :
- devis_id (FK devis, nullable)
- signature_url (VARCHAR 500, nullable)
"""
from alembic import op
import sqlalchemy as sa

revision = 'n0p1q2r3s4t5'
down_revision = 'm9n0p1q2r3s4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- reservation_risks --
    op.create_table(
        'reservation_risks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('blocking', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reservation_risks_tenant_id', 'reservation_risks', ['tenant_id'])
    op.create_index('ix_reservation_risks_reservation_id', 'reservation_risks',
                    ['tenant_id', 'reservation_id'])

    # -- reservation_pre_check_items --
    op.create_table(
        'reservation_pre_check_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('checked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('checked_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('checked_by', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['checked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pre_check_items_tenant_reservation', 'reservation_pre_check_items',
                    ['tenant_id', 'reservation_id'])

    # -- reservation_extensions --
    op.create_table(
        'reservation_extensions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('original_return_date', sa.Date(), nullable=False),
        sa.Column('new_return_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('extra_charge_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reservation_extensions_tenant_reservation', 'reservation_extensions',
                    ['tenant_id', 'reservation_id'])

    # -- colonnes sur reservations --
    op.add_column('reservations',
        sa.Column('devis_id', sa.Integer(), nullable=True))
    op.add_column('reservations',
        sa.Column('signature_url', sa.String(500), nullable=True))
    op.create_foreign_key(
        'fk_reservations_devis_id', 'reservations', 'devis', ['devis_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_reservations_devis_id', 'reservations', type_='foreignkey')
    op.drop_column('reservations', 'signature_url')
    op.drop_column('reservations', 'devis_id')

    op.drop_index('ix_reservation_extensions_tenant_reservation', 'reservation_extensions')
    op.drop_table('reservation_extensions')

    op.drop_index('ix_pre_check_items_tenant_reservation', 'reservation_pre_check_items')
    op.drop_table('reservation_pre_check_items')

    op.drop_index('ix_reservation_risks_reservation_id', 'reservation_risks')
    op.drop_index('ix_reservation_risks_tenant_id', 'reservation_risks')
    op.drop_table('reservation_risks')
