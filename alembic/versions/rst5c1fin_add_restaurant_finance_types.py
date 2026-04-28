"""Phase 5c.1 — Étend FinanceInvoice pour tickets restaurant + agrégats journaliers.

Revision ID: rst5c1fin
Revises: z9a0b1c2d3e4
Create Date: 2026-04-14 00:00:00.000000

Ajouts (expand-only, non-destructif) :
  - Types `RESTAURANT_TICKET` et `RESTAURANT_DAILY_AGGREGATE` dans le CHECK type
  - Colonne `commande_id` (lien non-FK vers restaurant_commandes, cohérent avec
    vente_id/supply_order_id qui sont aussi non-FK)
  - Colonne `parent_invoice_id` (FK self-reference, ON DELETE SET NULL) pour lier
    les tickets à leur agrégat journalier
  - Index partiel sur parent_invoice_id (queries d'agrégation)
  - Index composite (tenant_id, type, date_facture) pour le job Celery d'agrégation
  - Index sur commande_id (lookup inverse ticket ← commande)
"""
from typing import Sequence, Union

from alembic import op

revision: str = "rst5c1fin"
down_revision: Union[str, None, tuple] = "z9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nouveau CHECK constraint — drop + recreate pour inclure les types restaurant
    op.execute(
        "ALTER TABLE finance_invoices "
        "DROP CONSTRAINT IF EXISTS check_finance_invoice_type_valide"
    )
    op.execute(
        "ALTER TABLE finance_invoices "
        "ADD CONSTRAINT check_finance_invoice_type_valide "
        "CHECK (type IN ('FOURNISSEUR', 'CLIENT', 'INTERNE', "
        "'RESTAURANT_TICKET', 'RESTAURANT_DAILY_AGGREGATE'))"
    )

    # Colonne commande_id — lien vers restaurant_commandes (non-FK, idem vente_id)
    op.execute(
        "ALTER TABLE finance_invoices "
        "ADD COLUMN IF NOT EXISTS commande_id BIGINT NULL"
    )

    # Colonne parent_invoice_id (FK self-reference)
    op.execute(
        "ALTER TABLE finance_invoices "
        "ADD COLUMN IF NOT EXISTS parent_invoice_id BIGINT NULL"
    )
    op.execute(
        "ALTER TABLE finance_invoices "
        "ADD CONSTRAINT fk_finance_invoices_parent "
        "FOREIGN KEY (parent_invoice_id) "
        "REFERENCES finance_invoices(id) ON DELETE SET NULL"
    )

    # Index partiel — seules les factures liées à un agrégat ont parent non-null
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_finance_invoices_parent "
        "ON finance_invoices(parent_invoice_id) "
        "WHERE parent_invoice_id IS NOT NULL"
    )

    # Index composite — job agrégation journalier : tous tickets du jour par tenant
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_finance_invoices_type_date "
        "ON finance_invoices(tenant_id, type, date_facture)"
    )

    # Index lookup ticket ← commande
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_finance_invoice_commande "
        "ON finance_invoices(commande_id) "
        "WHERE commande_id IS NOT NULL"
    )


def downgrade() -> None:
    # Les factures de type RESTAURANT_* existantes doivent avoir été purgées avant
    # downgrade (responsabilité opérateur) — le CHECK les rejetterait sinon.
    op.execute("DROP INDEX IF EXISTS idx_finance_invoice_commande")
    op.execute("DROP INDEX IF EXISTS ix_finance_invoices_type_date")
    op.execute("DROP INDEX IF EXISTS ix_finance_invoices_parent")
    op.execute(
        "ALTER TABLE finance_invoices "
        "DROP CONSTRAINT IF EXISTS fk_finance_invoices_parent"
    )
    op.execute(
        "ALTER TABLE finance_invoices "
        "DROP COLUMN IF EXISTS parent_invoice_id"
    )
    op.execute(
        "ALTER TABLE finance_invoices "
        "DROP COLUMN IF EXISTS commande_id"
    )
    op.execute(
        "ALTER TABLE finance_invoices "
        "DROP CONSTRAINT IF EXISTS check_finance_invoice_type_valide"
    )
    op.execute(
        "ALTER TABLE finance_invoices "
        "ADD CONSTRAINT check_finance_invoice_type_valide "
        "CHECK (type IN ('FOURNISSEUR', 'CLIENT', 'INTERNE'))"
    )
