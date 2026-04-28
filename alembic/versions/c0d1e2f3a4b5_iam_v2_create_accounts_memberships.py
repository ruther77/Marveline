"""IAM v2 — Lot 0A : CREATE TABLE accounts, account_oauth_identities, tenant_memberships, account_sessions.

Révision : c0d1e2f3a4b5
Down revision : s6t7u8v9w0x1
Branch labels : None
Depends on : None

Stratégie expand/contract :
    - Lot 0A : CREATE nouvelles tables (cette migration)
    - Lot 0B : ALTER existantes (migration d1e2f3a4b5c6)
    - Lot 7  : Backfill users → accounts, user_roles → tenant_memberships
    - Lot 8  : DROP legacy (users, user_roles, user_sessions + colonnes orphelines)

Impact rollback :
    - downgrade() DROP les 4 nouvelles tables (aucune donnée de prod en Lot 0)
    - Non destructif pour les tables existantes (pas d'ALTER ici)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0d1e2f3a4b5'
down_revision = 's6t7u8v9w0x1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. TABLE accounts — Identité globale (remplace users)               #
    # ------------------------------------------------------------------ #
    op.create_table(
        'accounts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            'external_id', sa.String(64), nullable=False,
            comment="UUID v4 immuable — jamais réutilisé"
        ),
        sa.Column(
            'email', sa.String(255), nullable=False,
            comment="Email unique global et immuable (clé de login)"
        ),
        sa.Column(
            'hashed_password', sa.String(255), nullable=True,
            comment="Argon2id+pepper hash — null si compte OAuth-only"
        ),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column(
            'password_change_required', sa.Boolean(), nullable=False,
            server_default='false',
            comment="True si password détecté dans HIBP (flag global)"
        ),
        # SoftDeleteMixin
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        # TimestampMixin
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_accounts_email'),
    )
    op.create_index('ix_accounts_external_id', 'accounts', ['external_id'], unique=True)
    op.create_index('ix_accounts_email', 'accounts', ['email'])

    # ------------------------------------------------------------------ #
    # 2. TABLE account_oauth_identities — Identités OAuth liées à un compte #
    # ------------------------------------------------------------------ #
    op.create_table(
        'account_oauth_identities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'account_id', sa.BigInteger(), nullable=False,
            comment="Compte global associé"
        ),
        sa.Column(
            'provider', sa.String(50), nullable=False,
            comment="Provider OAuth : google | github | facebook"
        ),
        sa.Column(
            'provider_subject', sa.String(255), nullable=False,
            comment="ID stable chez le provider (claim 'sub')"
        ),
        sa.Column(
            'email_at_provider', sa.String(255), nullable=True,
            comment="Email snapshot chez le provider (informatif uniquement)"
        ),
        sa.Column(
            'linked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False,
            comment="Date de liaison du compte OAuth"
        ),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_subject', name='uq_oauth_provider_subject'),
    )
    op.create_index('idx_oauth_account_id', 'account_oauth_identities', ['account_id'])

    # ------------------------------------------------------------------ #
    # 3. TABLE tenant_memberships — Appartenance d'un compte à un tenant  #
    # ------------------------------------------------------------------ #
    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.BigInteger(), nullable=False, comment="Compte global"),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, comment="Tenant concerné"),
        sa.Column(
            'role_name', sa.String(50), nullable=False,
            comment="Rôle RBAC du membership"
        ),
        sa.Column(
            'status', sa.String(20), nullable=False,
            server_default='active',
            comment="État : active | suspended | offboarding"
        ),
        sa.Column(
            'invited_by', sa.BigInteger(), nullable=True,
            comment="Compte ayant invité ce membre (null = auto-provisionné)"
        ),
        sa.Column('invited_at', sa.DateTime(timezone=True), nullable=True, comment="Date d'invitation"),
        sa.Column(
            'activated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True,
            comment="Date d'activation du membership"
        ),
        sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True, comment="Date de suspension"),
        sa.Column(
            'revoked_at', sa.DateTime(timezone=True), nullable=True,
            comment="Date de révocation — NULL = membership actif"
        ),
        sa.Column('revoke_reason', sa.String(200), nullable=True, comment="Raison de la révocation"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'offboarding')",
            name='ck_membership_status_valid'
        ),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_name'], ['auth_roles.name'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invited_by'], ['accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    # Index unique partiel : 1 membership actif par (account, tenant)
    op.create_index(
        'uq_membership_active_per_tenant',
        'tenant_memberships', ['account_id', 'tenant_id'],
        unique=True,
        postgresql_where=sa.text('revoked_at IS NULL'),
    )
    op.create_index(
        'idx_membership_tenant_role',
        'tenant_memberships', ['tenant_id', 'role_name'],
        postgresql_where=sa.text('revoked_at IS NULL'),
    )
    op.create_index(
        'idx_membership_account_active',
        'tenant_memberships', ['account_id'],
        postgresql_where=sa.text('revoked_at IS NULL'),
    )
    op.create_index('idx_membership_tenant_all', 'tenant_memberships', ['tenant_id'])

    # ------------------------------------------------------------------ #
    # 4. TABLE account_sessions — Sessions liées à un membership          #
    # ------------------------------------------------------------------ #
    op.create_table(
        'account_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            'session_id', sa.String(64), nullable=False,
            comment="UUID de session (claim 'sid' dans JWT)"
        ),
        sa.Column(
            'account_id', sa.BigInteger(), nullable=False,
            comment="Compte propriétaire (claim 'sub' dans JWT)"
        ),
        sa.Column(
            'membership_id', sa.BigInteger(), nullable=False,
            comment="Membership actif au moment du login (claim 'mid' dans JWT)"
        ),
        sa.Column(
            'tenant_id', sa.BigInteger(), nullable=False,
            comment="Tenant dénormalisé pour perf (claim 'tid' dans JWT)"
        ),
        sa.Column(
            'device_id', sa.String(128), nullable=False,
            comment="Fingerprint device (claim 'did' dans JWT)"
        ),
        sa.Column(
            'ip_address', sa.String(45), nullable=False,
            comment="IP au login (IPv4 ou IPv6)"
        ),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column(
            'expires_at', sa.DateTime(timezone=True), nullable=False,
            comment="Expiration de la session (refresh token TTL)"
        ),
        sa.Column(
            'revoked_at', sa.DateTime(timezone=True), nullable=True,
            comment="Date de révocation — NULL = active"
        ),
        sa.Column('revoke_reason', sa.String(200), nullable=True),
        sa.Column(
            'mfa_verified', sa.Boolean(), nullable=False,
            server_default='false',
            comment="True si challenge TOTP réussi (acr=2)"
        ),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['membership_id'], ['tenant_memberships.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('idx_account_sessions_session_id', 'account_sessions', ['session_id'], unique=True)
    op.create_index('idx_account_sessions_tenant_account', 'account_sessions', ['tenant_id', 'account_id'])
    op.create_index(
        'idx_account_sessions_membership_active',
        'account_sessions', ['membership_id'],
        postgresql_where=sa.text('revoked_at IS NULL'),
    )
    op.create_index('idx_account_sessions_device', 'account_sessions', ['device_id'])
    op.create_index(
        'idx_account_sessions_account_active',
        'account_sessions', ['account_id'],
        postgresql_where=sa.text('revoked_at IS NULL'),
    )


def downgrade() -> None:
    # Ordre inverse des FK
    op.drop_table('account_sessions')
    op.drop_table('tenant_memberships')
    op.drop_table('account_oauth_identities')
    op.drop_table('accounts')
