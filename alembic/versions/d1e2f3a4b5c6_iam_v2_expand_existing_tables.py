"""IAM v2 — Lot 0B : ALTER TABLE expand — ajout colonnes IAM v2 sur tables existantes.

Révision : d1e2f3a4b5c6
Down revision : c0d1e2f3a4b5
Branch labels : None
Depends on : None

Tables modifiées (expand-only, toutes colonnes nullable) :
    - mfa_devices       : + membership_id (FK tenant_memberships, UNIQUE partiel)
                          + user_id passe nullable (préparation Lot 8 DROP FK users)
    - audit_logs        : + account_id, + membership_id, + actor_type
    - api_keys          : + membership_id (FK tenant_memberships, SET NULL)
    - password_reset_tokens : + account_id (FK accounts, CASCADE)

Impact rollback :
    - downgrade() supprime les colonnes ajoutées (SAFE — aucun code v2 en prod à ce stade)
    - La contrainte UNIQUE partielle sur mfa_devices.membership_id est droppée en downgrade
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. mfa_devices — membership_id + user_id devient nullable           #
    # ------------------------------------------------------------------ #
    op.alter_column(
        'mfa_devices', 'user_id',
        existing_type=sa.BigInteger(),
        nullable=True,
        comment="[LEGACY] User who owns this MFA device (users.id — IAM v1)",
    )
    op.add_column(
        'mfa_devices',
        sa.Column(
            'membership_id', sa.BigInteger(), nullable=True,
            comment="Membership auquel appartient ce device TOTP (IAM v2 — 1 device par membership)"
        ),
    )
    op.create_foreign_key(
        'fk_mfa_devices_membership_id',
        'mfa_devices', 'tenant_memberships',
        ['membership_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index(
        'uq_mfa_device_membership',
        'mfa_devices', ['membership_id'],
        unique=True,
        postgresql_where=sa.text('membership_id IS NOT NULL'),
    )

    # ------------------------------------------------------------------ #
    # 2. audit_logs — account_id, membership_id, actor_type               #
    # ------------------------------------------------------------------ #
    op.add_column(
        'audit_logs',
        sa.Column(
            'account_id', sa.BigInteger(), nullable=True,
            comment="ID compte global (IAM v2 — remplace user_id)"
        ),
    )
    op.add_column(
        'audit_logs',
        sa.Column(
            'membership_id', sa.BigInteger(), nullable=True,
            comment="ID membership tenant au moment de l'action (IAM v2)"
        ),
    )
    op.add_column(
        'audit_logs',
        sa.Column(
            'actor_type', sa.String(20), nullable=True,
            comment="Type d'acteur : account | api_key | system (IAM v2)"
        ),
    )
    op.create_index(
        'idx_audit_account_id', 'audit_logs', ['account_id'],
        postgresql_where=sa.text('account_id IS NOT NULL'),
    )

    # ------------------------------------------------------------------ #
    # 3. api_keys — membership_id                                         #
    # ------------------------------------------------------------------ #
    op.add_column(
        'api_keys',
        sa.Column(
            'membership_id', sa.BigInteger(), nullable=True,
            comment="Membership qui a créé la clé (IAM v2 — remplace created_by FK users)"
        ),
    )
    op.create_foreign_key(
        'fk_api_keys_membership_id',
        'api_keys', 'tenant_memberships',
        ['membership_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_api_keys_membership_id', 'api_keys', ['membership_id'])

    # ------------------------------------------------------------------ #
    # 4. password_reset_tokens — account_id                               #
    # ------------------------------------------------------------------ #
    op.add_column(
        'password_reset_tokens',
        sa.Column(
            'account_id', sa.BigInteger(), nullable=True,
            comment="Compte propriétaire du token de reset (IAM v2 — remplace user_id FK users)"
        ),
    )
    op.create_foreign_key(
        'fk_prt_account_id',
        'password_reset_tokens', 'accounts',
        ['account_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_prt_account_id', 'password_reset_tokens', ['account_id'])


def downgrade() -> None:
    # Annuler dans l'ordre inverse

    # password_reset_tokens
    op.drop_index('ix_prt_account_id', table_name='password_reset_tokens')
    op.drop_constraint('fk_prt_account_id', 'password_reset_tokens', type_='foreignkey')
    op.drop_column('password_reset_tokens', 'account_id')

    # api_keys
    op.drop_index('ix_api_keys_membership_id', table_name='api_keys')
    op.drop_constraint('fk_api_keys_membership_id', 'api_keys', type_='foreignkey')
    op.drop_column('api_keys', 'membership_id')

    # audit_logs
    op.drop_index('idx_audit_account_id', table_name='audit_logs')
    op.drop_column('audit_logs', 'actor_type')
    op.drop_column('audit_logs', 'membership_id')
    op.drop_column('audit_logs', 'account_id')

    # mfa_devices
    op.drop_index('uq_mfa_device_membership', table_name='mfa_devices')
    op.drop_constraint('fk_mfa_devices_membership_id', 'mfa_devices', type_='foreignkey')
    op.drop_column('mfa_devices', 'membership_id')
    op.alter_column(
        'mfa_devices', 'user_id',
        existing_type=sa.BigInteger(),
        nullable=False,
        comment="User who owns this MFA device",
    )
