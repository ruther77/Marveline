"""IAM v2 — Lot 7 : DROP tables legacy IAM v1 + colonnes orphelines.

Révision : f3a4b5c6d7e8
Down revision : e2f3a4b5c6d7
Branch labels : None
Depends on : None

Contract phase (expand/contract) : suppression des structures v1 devenues orphelines
après backfill complet (scripts/backfill_users_to_accounts.py).

Actions dans l'ordre :
  Phase 1 — DROP FK constraints sur tables métier référençant users.id
             Les colonnes (created_by, author_id, etc.) sont CONSERVÉES nullable —
             les valeurs historiques (user IDs) restent comme audit trail orphelin.
  Phase 2 — DROP colonnes expand legacy :
             - mfa_devices.user_id      (remplacée par membership_id — Lot 0B)
             - audit_logs.user_id       (remplacée par account_id — Lot 0B)
             - password_reset_tokens.user_id   (remplacée par account_id — Lot 0B/0C)
             - password_reset_tokens.tenant_id (devenu orphelin — Lot 0C)
  Phase 3 — DROP tables dans l'ordre FK :
             user_sessions → user_roles → users

PRÉ-REQUIS OBLIGATOIRE :
  scripts/backfill_users_to_accounts.py doit avoir été exécuté (Lot 6)
  avant d'appliquer cette migration.

Impact rollback :
  - downgrade() recrée les 3 tables et restaure les FK sur les tables métier.
  - Les données users étant supprimées, un downgrade POST-PROD nécessite
    une restauration DB complète (dump pré-migration).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a4b5c6d7e8'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================== #
    # PHASE 1 — DROP FK constraints sur tables métier                    #
    # (colonnes conservées nullable — les valeurs historiques restent)   #
    # ================================================================== #

    # api_keys.created_by → users.id
    op.drop_constraint('api_keys_created_by_fkey', 'api_keys', type_='foreignkey')

    # devis_change_requests.author_id → users.id
    op.drop_constraint('devis_change_requests_author_id_fkey', 'devis_change_requests', type_='foreignkey')

    # devis_negotiations.author_id → users.id
    op.drop_constraint('devis_negotiations_author_id_fkey', 'devis_negotiations', type_='foreignkey')

    # devis_versions.created_by → users.id
    op.drop_constraint('devis_versions_created_by_fkey', 'devis_versions', type_='foreignkey')

    # event_incidents.declared_by → users.id
    op.drop_constraint('event_incidents_declared_by_fkey', 'event_incidents', type_='foreignkey')

    # event_incidents.owner_id → users.id
    op.drop_constraint('event_incidents_owner_id_fkey', 'event_incidents', type_='foreignkey')

    # incident_actions.assignee_id → users.id
    op.drop_constraint('incident_actions_assignee_id_fkey', 'incident_actions', type_='foreignkey')

    # inventory_movements.handled_by_user_id → users.id
    op.drop_constraint('fk_movement_handled_by_user', 'inventory_movements', type_='foreignkey')

    # reservation_extensions.created_by → users.id
    op.drop_constraint('reservation_extensions_created_by_fkey', 'reservation_extensions', type_='foreignkey')

    # reservation_pre_check_items.checked_by → users.id
    op.drop_constraint('reservation_pre_check_items_checked_by_fkey', 'reservation_pre_check_items', type_='foreignkey')

    # reservations.assigned_user_id → users.id
    op.drop_constraint('fk_reservations_assigned_user_id', 'reservations', type_='foreignkey')

    # stock_adjustments.created_by → users.id
    op.drop_constraint('stock_adjustments_created_by_fkey', 'stock_adjustments', type_='foreignkey')

    # stock_inventaire_sessions.created_by → users.id
    op.drop_constraint('stock_inventaire_sessions_created_by_fkey', 'stock_inventaire_sessions', type_='foreignkey')

    # supplier_order_receipts.received_by → users.id
    op.drop_constraint('supplier_order_receipts_received_by_fkey', 'supplier_order_receipts', type_='foreignkey')

    # vente_payments.created_by → users.id
    op.drop_constraint('vente_payments_created_by_fkey', 'vente_payments', type_='foreignkey')

    # ================================================================== #
    # PHASE 2 — DROP colonnes expand legacy                              #
    # ================================================================== #

    # --- mfa_devices.user_id + tenant_id ---
    # UniqueConstraint(tenant_id, user_id) doit être droppée avant les deux colonnes.
    # En IAM v2, membership_id remplace la paire (tenant_id, user_id) comme clé d'unicité.
    op.drop_constraint('uq_mfa_device_tenant_user', 'mfa_devices', type_='unique')
    op.drop_constraint('mfa_devices_user_id_fkey', 'mfa_devices', type_='foreignkey')
    op.drop_column('mfa_devices', 'user_id')
    # tenant_id est redondant en IAM v2 (membership_id → tenant_memberships.tenant_id).
    # TenantMixin imposait NOT NULL mais sans FK explicite en DB (pas de constraint à dropper).
    op.drop_column('mfa_devices', 'tenant_id')

    # --- audit_logs.user_id ---
    # Pas de FK constraint sur cette colonne (BigInteger sans ForeignKey déclaré en DB).
    # L'index partiel composite doit être droppé avant la colonne.
    op.drop_index('idx_audit_user_created', table_name='audit_logs')
    op.drop_column('audit_logs', 'user_id')

    # --- password_reset_tokens.user_id (nullable depuis Lot 0C) ---
    op.drop_constraint('password_reset_tokens_user_id_fkey', 'password_reset_tokens', type_='foreignkey')
    op.drop_column('password_reset_tokens', 'user_id')

    # --- password_reset_tokens.tenant_id (nullable depuis Lot 0C) ---
    # Pas de FK explicite en DB (constraint inexistante) — dropper la colonne directement.
    op.drop_column('password_reset_tokens', 'tenant_id')

    # ================================================================== #
    # PHASE 3 — DROP tables legacy IAM v1                                #
    # Ordre : user_sessions → user_roles → users (respect des FK)        #
    # Les FK intra-tables sont supprimées avec les tables.               #
    # ================================================================== #

    op.drop_table('user_sessions')
    op.drop_table('user_roles')
    op.drop_table('users')


def downgrade() -> None:
    """Restaure les tables et FK legacy IAM v1.

    AVERTISSEMENT : Ce downgrade ne restaure PAS les données users.
    Il est fourni uniquement pour la cohérence du graphe Alembic.
    En production, un downgrade POST-MIGRATION nécessite une restauration
    complète depuis le dump pré-migration (backup_pre_lot7.dump).
    """
    # ================================================================== #
    # PHASE 3 inverse — RECREER les tables legacy                        #
    # ================================================================== #

    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='staff'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('password_change_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('oauth_provider', sa.String(50), nullable=True),
        sa.Column('oauth_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email'),
    )

    op.create_table(
        'user_roles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role_name', sa.String(50), nullable=False),
        sa.Column('assigned_by', sa.BigInteger(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='user_roles_user_id_fkey'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL', name='user_roles_assigned_by_fkey'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('device_id', sa.String(128), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoke_reason', sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='user_sessions_user_id_fkey'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )

    # ================================================================== #
    # PHASE 2 inverse — RESTAURER les colonnes expand legacy             #
    # ================================================================== #

    # password_reset_tokens.tenant_id — pas de FK en DB, juste la colonne
    op.add_column(
        'password_reset_tokens',
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
    )

    # password_reset_tokens.user_id
    op.add_column(
        'password_reset_tokens',
        sa.Column('user_id', sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        'password_reset_tokens_user_id_fkey',
        'password_reset_tokens', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE',
    )

    # audit_logs.user_id — pas de FK (juste un BigInteger nullable + index partiel)
    op.add_column(
        'audit_logs',
        sa.Column('user_id', sa.BigInteger(), nullable=True, index=True),
    )
    op.create_index(
        'idx_audit_user_created',
        'audit_logs', ['user_id', 'created_at'],
        postgresql_where=sa.text('user_id IS NOT NULL'),
    )

    # mfa_devices.tenant_id + user_id
    # tenant_id : pas de FK explicite en DB (TenantMixin = NOT NULL uniquement)
    # Restaurée nullable pour ne pas bloquer l'insert (données perdues, pas de backfill possible)
    op.add_column(
        'mfa_devices',
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'mfa_devices',
        sa.Column('user_id', sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        'mfa_devices_user_id_fkey',
        'mfa_devices', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_unique_constraint(
        'uq_mfa_device_tenant_user',
        'mfa_devices', ['tenant_id', 'user_id'],
    )

    # ================================================================== #
    # PHASE 1 inverse — RESTAURER les FK sur tables métier               #
    # Les colonnes contiennent des user IDs orphelins (table users vide). #
    # Nullifier avant de créer les FK pour éviter les violations.        #
    # ================================================================== #

    op.execute(sa.text("UPDATE vente_payments SET created_by = NULL"))
    op.execute(sa.text("UPDATE supplier_order_receipts SET received_by = NULL"))
    op.execute(sa.text("UPDATE stock_inventaire_sessions SET created_by = NULL"))
    op.execute(sa.text("UPDATE stock_adjustments SET created_by = NULL"))
    op.execute(sa.text("UPDATE reservations SET assigned_user_id = NULL"))
    op.execute(sa.text("UPDATE reservation_pre_check_items SET checked_by = NULL"))
    op.execute(sa.text("UPDATE reservation_extensions SET created_by = NULL"))
    op.execute(sa.text("UPDATE inventory_movements SET handled_by_user_id = NULL"))
    op.execute(sa.text("UPDATE incident_actions SET assignee_id = NULL"))
    op.execute(sa.text("UPDATE event_incidents SET owner_id = NULL, declared_by = NULL"))
    op.execute(sa.text("UPDATE devis_versions SET created_by = NULL"))
    op.execute(sa.text("UPDATE devis_negotiations SET author_id = NULL"))
    op.execute(sa.text("UPDATE devis_change_requests SET author_id = NULL"))
    op.execute(sa.text("UPDATE api_keys SET created_by = NULL"))

    op.create_foreign_key(
        'vente_payments_created_by_fkey',
        'vente_payments', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'supplier_order_receipts_received_by_fkey',
        'supplier_order_receipts', 'users',
        ['received_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'stock_inventaire_sessions_created_by_fkey',
        'stock_inventaire_sessions', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'stock_adjustments_created_by_fkey',
        'stock_adjustments', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'fk_reservations_assigned_user_id',
        'reservations', 'users',
        ['assigned_user_id'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'reservation_pre_check_items_checked_by_fkey',
        'reservation_pre_check_items', 'users',
        ['checked_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'reservation_extensions_created_by_fkey',
        'reservation_extensions', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'fk_movement_handled_by_user',
        'inventory_movements', 'users',
        ['handled_by_user_id'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'incident_actions_assignee_id_fkey',
        'incident_actions', 'users',
        ['assignee_id'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'event_incidents_owner_id_fkey',
        'event_incidents', 'users',
        ['owner_id'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'event_incidents_declared_by_fkey',
        'event_incidents', 'users',
        ['declared_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'devis_versions_created_by_fkey',
        'devis_versions', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'devis_negotiations_author_id_fkey',
        'devis_negotiations', 'users',
        ['author_id'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'devis_change_requests_author_id_fkey',
        'devis_change_requests', 'users',
        ['author_id'], ['id'],
        ondelete='SET NULL',
    )

    op.create_foreign_key(
        'api_keys_created_by_fkey',
        'api_keys', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL',
    )
