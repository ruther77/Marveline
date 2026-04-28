"""add return inspection items + dispute logs

Revision ID: u1v2w3x4y5z6
Revises: uplift_20260425
Create Date: 2026-04-25

Tables créées :
- reservation_return_inspection_items : tracking item-level retour (good/damaged/missing)
- reservation_dispute_logs : audit trail litige (open/note/resolve + charges)

Permet :
- Constat de retour structuré par ligne (vs notes free-text)
- Historique litige tracé pour clôture comptable
- Calcul automatique charges à imputer sur caution
"""
from alembic import op
import sqlalchemy as sa

revision = 'u1v2w3x4y5z6'
down_revision = 'uplift_20260425'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- reservation_return_inspection_items --
    op.create_table(
        'reservation_return_inspection_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('reservation_line_id', sa.Integer(), nullable=True),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('quantity_expected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quantity_returned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quantity_damaged', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quantity_missing', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('condition', sa.String(20), nullable=False, server_default='good'),
        sa.Column('damage_description', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('charge_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('inspected_by', sa.Integer(), nullable=True),
        sa.Column('inspected_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['reservation_line_id'], ['reservation_lines.id'], ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(['inspected_by'], ['accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "condition IN ('good','damaged','missing','partial')",
            name='check_inspection_condition',
        ),
        sa.CheckConstraint(
            'quantity_returned >= 0 AND quantity_damaged >= 0 AND quantity_missing >= 0',
            name='check_inspection_quantities_positive',
        ),
        sa.CheckConstraint(
            'charge_cents >= 0', name='check_inspection_charge_positive',
        ),
    )
    op.create_index(
        'ix_inspection_tenant_reservation',
        'reservation_return_inspection_items',
        ['tenant_id', 'reservation_id'],
    )
    op.create_index(
        'ix_inspection_line',
        'reservation_return_inspection_items',
        ['reservation_line_id'],
    )

    # -- reservation_dispute_logs --
    op.create_table(
        'reservation_dispute_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('reservation_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('charge_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "action IN ('opened','note_added','charge_applied','resolved')",
            name='check_dispute_action',
        ),
        sa.CheckConstraint('charge_cents >= 0', name='check_dispute_charge_positive'),
    )
    op.create_index(
        'ix_dispute_tenant_reservation',
        'reservation_dispute_logs',
        ['tenant_id', 'reservation_id'],
    )
    op.create_index(
        'ix_dispute_created_at', 'reservation_dispute_logs', ['created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_dispute_created_at', table_name='reservation_dispute_logs')
    op.drop_index('ix_dispute_tenant_reservation', table_name='reservation_dispute_logs')
    op.drop_table('reservation_dispute_logs')

    op.drop_index('ix_inspection_line', table_name='reservation_return_inspection_items')
    op.drop_index('ix_inspection_tenant_reservation',
                  table_name='reservation_return_inspection_items')
    op.drop_table('reservation_return_inspection_items')
