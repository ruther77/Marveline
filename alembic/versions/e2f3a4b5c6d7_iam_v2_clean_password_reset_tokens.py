"""IAM v2 — Lot 0C : password_reset_tokens — rendre user_id et tenant_id nullable.

Révision : e2f3a4b5c6d7
Down revision : d1e2f3a4b5c6
Branch labels : None
Depends on : None

Supprime la dépendance legacy sur users.id dans password_reset_tokens :
    - user_id : NOT NULL → NULL (FK users.id gardée pour rollback, sera DROP en Lot 8)
    - tenant_id : NOT NULL → NULL (colonne gardée pour rollback, sera DROP en Lot 8)

Permet au service account.py IAM v2 de créer des tokens avec account_id uniquement,
sans renseigner user_id ni tenant_id.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_id : NOT NULL → NULL
    op.alter_column(
        'password_reset_tokens', 'user_id',
        existing_type=sa.BigInteger(),
        nullable=True,
        comment="[LEGACY] Utilisateur propriétaire (users.id — IAM v1, sera DROP en Lot 8)",
    )

    # tenant_id : NOT NULL → NULL
    # TenantMixin l'a déclaré NOT NULL — on le relaxe pour IAM v2
    op.alter_column(
        'password_reset_tokens', 'tenant_id',
        existing_type=sa.BigInteger(),
        nullable=True,
        comment="[LEGACY] Tenant (IAM v1 — sera DROP en Lot 8)",
    )


def downgrade() -> None:
    # ATTENTION : downgrade possible uniquement si toutes les lignes ont user_id/tenant_id non-null
    op.alter_column(
        'password_reset_tokens', 'tenant_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.alter_column(
        'password_reset_tokens', 'user_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
