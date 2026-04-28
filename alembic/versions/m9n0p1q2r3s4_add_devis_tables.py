"""add devis tables

Revision ID: m9n0p1q2r3s4
Revises: l8m9n0p1q2r3
Create Date: 2026-02-20

B1-A : Tables devis (7 tables) — module devis complet.
Stratégie expand/contract : création pure, aucune modification de colonne existante.
Rollback : DROP TABLE dans l'ordre inverse des FK.
"""
from typing import Union
import sqlalchemy as sa
from alembic import op


revision: str = 'm9n0p1q2r3s4'
down_revision: Union[str, None] = 'l8m9n0p1q2r3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Table principale devis ───────────────────────────────────────────
    op.create_table(
        'devis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('reference', sa.String(50), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('event_location', sa.String(255), nullable=True),
        sa.Column('valid_until', sa.Date(), nullable=False),
        sa.Column('tva_rate', sa.Integer(), nullable=False, server_default='2000'),
        sa.Column('subtotal_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tva_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('discount_pct', sa.Integer(), nullable=True),
        sa.Column('caution_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('caution_amount_cents', sa.BigInteger(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('converted_reservation_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['converted_reservation_id'], ['reservations.id'],
                                ondelete='SET NULL'),
        sa.UniqueConstraint('tenant_id', 'reference', name='uq_devis_tenant_reference'),
        sa.CheckConstraint(
            "status IN ('draft','sent','negotiation','accepted','refused',"
            "'expired','converted','cancelled','version_pending')",
            name='check_devis_status_valid'
        ),
        sa.CheckConstraint('total_cents >= 0', name='check_devis_total_positive'),
    )
    op.create_index('ix_devis_tenant_id', 'devis', ['tenant_id'])
    op.create_index('ix_devis_tenant_id_composite', 'devis', ['tenant_id', 'id'])
    op.create_index('ix_devis_tenant_status', 'devis', ['tenant_id', 'status'])
    op.create_index('ix_devis_tenant_customer', 'devis', ['tenant_id', 'customer_id'])

    # ── 2. Lignes de devis ──────────────────────────────────────────────────
    op.create_table(
        'devis_lines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('devis_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('unit_price_cents', sa.BigInteger(), nullable=False),
        sa.Column('discount_pct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('subtotal_cents', sa.BigInteger(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['devis_id'], ['devis.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.CheckConstraint('unit_price_cents >= 0', name='check_devis_line_price_positive'),
        sa.CheckConstraint('quantity > 0', name='check_devis_line_qty_positive'),
    )
    op.create_index('ix_devis_lines_tenant_devis', 'devis_lines', ['tenant_id', 'devis_id'])

    # ── 3. Modules devis ────────────────────────────────────────────────────
    op.create_table(
        'devis_modules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('devis_id', sa.Integer(), nullable=False),
        sa.Column('module_type', sa.String(30), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('content_json', sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'::json")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['devis_id'], ['devis.id'], ondelete='CASCADE'),
        sa.CheckConstraint(
            "module_type IN ('socle','stock','facturation','securite','services')",
            name='check_devis_module_type_valid'
        ),
    )
    op.create_index('ix_devis_modules_tenant_devis', 'devis_modules', ['tenant_id', 'devis_id'])

    # ── 4. Phases de devis ──────────────────────────────────────────────────
    op.create_table(
        'devis_phases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('devis_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('date_start', sa.Date(), nullable=False),
        sa.Column('date_end', sa.Date(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['devis_id'], ['devis.id'], ondelete='CASCADE'),
        sa.CheckConstraint('date_end >= date_start', name='check_devis_phase_dates_valid'),
    )
    op.create_index('ix_devis_phases_tenant_devis', 'devis_phases', ['tenant_id', 'devis_id'])

    # ── 5. Versions (snapshots immuables) ───────────────────────────────────
    op.create_table(
        'devis_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('devis_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('snapshot_json', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['devis_id'], ['devis.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('devis_id', 'version_number', name='uq_devis_version'),
    )
    op.create_index('ix_devis_versions_tenant_devis', 'devis_versions',
                    ['tenant_id', 'devis_id'])

    # ── 6. Négociations ─────────────────────────────────────────────────────
    op.create_table(
        'devis_negotiations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('devis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('proposed_amount_cents', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['devis_id'], ['devis.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_devis_negotiations_tenant_devis', 'devis_negotiations',
                    ['tenant_id', 'devis_id'])

    # ── 7. Demandes de modification ─────────────────────────────────────────
    op.create_table(
        'devis_change_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('devis_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['devis_id'], ['devis.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint(
            "status IN ('pending','accepted','refused')",
            name='check_change_request_status_valid'
        ),
    )
    op.create_index('ix_devis_change_requests_tenant_devis', 'devis_change_requests',
                    ['tenant_id', 'devis_id'])


def downgrade() -> None:
    op.drop_table('devis_change_requests')
    op.drop_table('devis_negotiations')
    op.drop_table('devis_versions')
    op.drop_table('devis_phases')
    op.drop_table('devis_modules')
    op.drop_table('devis_lines')
    op.drop_table('devis')
