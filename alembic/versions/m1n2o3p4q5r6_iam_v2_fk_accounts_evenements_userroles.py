"""iam_v2_fk_accounts_evenements_userroles

Phase 2 IAM v2 - Après iam_v2_drop_legacy (f3a4b5c6d7e8) :
  1. Ajoute les FK accounts.id sur les colonnes precisement liees a users.id
     (drop effectue par f3a4b5c6d7e8 Phase 1) :
     - event_incidents.declared_by
     - event_incidents.owner_id
     - incident_actions.assignee_id
  2. Recree la table user_roles avec FK vers accounts.id
     (droppee dans f3a4b5c6d7e8 Phase 3)

Strategie : Les IDs dans ces colonnes sont deja des account_id
(le service _validate_user_tenant verifie TenantMembership.account_id == user_id
 depuis la migration IAM v2 expand phase).
Aucune migration de donnees requise.

Revision ID: m1n2o3p4q5r6
Revises: b7c8d9e0f1a2
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'm1n2o3p4q5r6'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── event_incidents : FK vers accounts.id ────────────────────────────
    op.create_foreign_key(
        'event_incidents_declared_by_fkey',
        'event_incidents', 'accounts',
        ['declared_by'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'event_incidents_owner_id_fkey',
        'event_incidents', 'accounts',
        ['owner_id'], ['id'],
        ondelete='SET NULL',
    )

    # ── incident_actions : FK vers accounts.id ────────────────────────────
    op.create_foreign_key(
        'incident_actions_assignee_id_fkey',
        'incident_actions', 'accounts',
        ['assignee_id'], ['id'],
        ondelete='RESTRICT',
    )

    # ── user_roles : recreation avec FK accounts.id ───────────────────────
    op.create_table(
        'user_roles',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            'user_id', sa.BigInteger(),
            sa.ForeignKey('accounts.id', ondelete='CASCADE', name='user_roles_user_id_fkey'),
            nullable=False,
            comment='Account concerne (IAM v2)',
        ),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, comment='Tenant concerne'),
        sa.Column(
            'role_name', sa.String(50),
            sa.ForeignKey('auth_roles.name', ondelete='RESTRICT', name='user_roles_role_name_fkey'),
            nullable=False,
            comment='Role attribue',
        ),
        sa.Column(
            'assigned_by', sa.BigInteger(),
            sa.ForeignKey('accounts.id', ondelete='SET NULL', name='user_roles_assigned_by_fkey'),
            nullable=False,
            comment='Account ayant attribue le role (IAM v2)',
        ),
        sa.Column(
            'assigned_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
            comment="Date d'attribution",
        ),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Date de revocation (NULL = actif)'),
        sa.Column('revoke_reason', sa.String(200), nullable=True,
                  comment='Raison de la revocation'),
    )

    op.create_index(
        'uq_user_roles_active_per_tenant',
        'user_roles', ['user_id', 'tenant_id'],
        unique=True,
        postgresql_where=sa.text('revoked_at IS NULL'),
    )
    op.create_index(
        'idx_user_roles_tenant_active',
        'user_roles', ['tenant_id', 'role_name'],
        postgresql_where=sa.text('revoked_at IS NULL'),
    )
    op.create_index(
        'idx_user_roles_user_active',
        'user_roles', ['user_id'],
        postgresql_where=sa.text('revoked_at IS NULL'),
    )


def downgrade() -> None:
    # ── user_roles ──────────────────────────────────────────────────────────
    op.drop_index('idx_user_roles_user_active', table_name='user_roles')
    op.drop_index('idx_user_roles_tenant_active', table_name='user_roles')
    op.drop_index('uq_user_roles_active_per_tenant', table_name='user_roles')
    op.drop_table('user_roles')

    # ── incident_actions ───────────────────────────────────────────────────
    op.drop_constraint(
        'incident_actions_assignee_id_fkey', 'incident_actions',
        type_='foreignkey',
    )

    # ── event_incidents ────────────────────────────────────────────────────
    op.drop_constraint(
        'event_incidents_owner_id_fkey', 'event_incidents',
        type_='foreignkey',
    )
    op.drop_constraint(
        'event_incidents_declared_by_fkey', 'event_incidents',
        type_='foreignkey',
    )
