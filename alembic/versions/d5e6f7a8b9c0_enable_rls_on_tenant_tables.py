"""enable RLS on audit_logs (chirurgical)

Revision ID: d5e6f7a8b9c0
Revises: d4d5e6f7a8b9
Create Date: 2026-04-16

Active Row-Level Security sur audit_logs uniquement.

CONTEXTE (verifie le 2026-04-16) :
- 7 tables tenant-scoped critiques (customers, invoices, reservations,
  products, devis, ventes, deposits) ont deja une policy stricte
  `tenant_isolation_X` : `tenant_id = current_setting('app.current_tenant_id')::integer`
  MAIS RLS n'est pas active dessus (policies dormantes).
- audit_logs n'a NI policy NI RLS.
- Les Celery tasks n'appellent jamais set_tenant_context() — activer RLS
  stricte sur les 7 tables les casserait immediatement (reservations,
  invoices crees en async via tasks).

DECISION :
- audit_logs n'est JAMAIS ecrit depuis Celery (grep confirme) → safe.
- audit_logs est ecrit exclusivement depuis le middleware audit dans le
  contexte HTTP, ou set_tenant_context est deja appele via deps.py.
- On aligne audit_logs sur le pattern strict des 7 autres tables
  (policy stricte avec ::integer cast, sans bypass NULL).

FUTUR TRAVAIL (hors scope demo 2026-04-18) :
- Sprint RLS-02 : injecter set_tenant_context() dans toutes les Celery
  tasks qui touchent tenant data, PUIS activer RLS sur les 7 tables
  dormantes (ALTER TABLE customers ENABLE/FORCE ROW LEVEL SECURITY, etc).

L'infra applicative est deja en place :
- app/core/database.py : event listener emet `SET LOCAL app.current_tenant_id`
- app/core/deps.py : set_tenant_context() dans get_current_user_async
"""
from alembic import op


revision = "d5e6f7a8b9c0"
down_revision = "d4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Policy stricte (meme pattern que les 7 tables dormantes) :
    # - tenant_id = current_setting('app.current_tenant_id')::integer
    # - PAS de bypass pour setting NULL (plus securise)
    op.execute("""
        CREATE POLICY tenant_isolation_audit_logs ON audit_logs
        USING (
            tenant_id = (current_setting('app.current_tenant_id', true))::integer
        )
    """)
    # Enable RLS (applique aux roles non-proprietaires)
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    # FORCE RLS : applique meme au proprietaire / superuser (crucial en dev
    # car `caro` est superuser — sans FORCE, tous les acces contournent RLS)
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_logs NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_audit_logs ON audit_logs")
