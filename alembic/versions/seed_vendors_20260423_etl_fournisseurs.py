"""seed finance_vendors pour les 5 fournisseurs ETL connus

Revision ID: seed_vendors_20260423
Revises: colisage_20260423
Create Date: 2026-04-23

Contexte : le pipeline ETL accepte 5 vendor_codes (metro, taiyat, eurociel,
ethan, gnanam) mais seuls METRO et TAIYAT étaient présents en base dans
finance_vendors (seedés manuellement hors Alembic). Conséquence : les imports
EUROCIEL/ETHAN/GNANAM validés ne produisaient aucune ligne dans
/epicerie/fournisseurs (vendor_id NULL sur les FinanceInvoice).

Stratégie : INSERT idempotent (ON CONFLICT DO NOTHING sur la contrainte
unique sur `code`). Sans effet si la ligne existe déjà, rejoue safe sur bases
déjà seedées (incluant la prod qui a reçu le seed manuel du 2026-04-23).

Le code applicatif (reception_etl._resolve_vendor_id) auto-crée aussi les
vendors manquants au moment de la validation, cette migration couvre le cas
d'un reprovisioning propre avant le premier import.

Rollback : suppression uniquement des vendors **sans aucune référence**
(invoice, supply_order). `finance_invoices.vendor_id` est en `ON DELETE SET
NULL` — supprimer un vendor référencé basculerait ses FK à NULL et ferait
disparaître silencieusement ses factures de la page fournisseurs. Avec la
clause de garde, un downgrade est un no-op dès qu'au moins une facture a
été créée pour un vendor.
"""
from alembic import op


revision = "seed_vendors_20260423"
down_revision = "colisage_20260423"
branch_labels = None
depends_on = None


_VENDORS = [
    ("METRO", "METRO"),
    ("TAIYAT", "TAI YAT DISTRIBUTION"),
    ("EUROCIEL", "EUROCIEL"),
    ("ETHAN", "ETHAN"),
    ("GNANAM", "GNANAM"),
]


def upgrade() -> None:
    for code, name in _VENDORS:
        op.execute(
            f"""
            INSERT INTO finance_vendors (code, name, created_at, updated_at)
            VALUES ('{code}', '{name}', NOW(), NOW())
            ON CONFLICT (code) DO NOTHING
            """
        )


def downgrade() -> None:
    codes = "', '".join(code for code, _ in _VENDORS)
    op.execute(
        f"""
        DELETE FROM finance_vendors
        WHERE code IN ('{codes}')
          AND NOT EXISTS (
            SELECT 1 FROM finance_invoices fi WHERE fi.vendor_id = finance_vendors.id
          )
          AND NOT EXISTS (
            SELECT 1 FROM epicerie_supply_orders so WHERE so.vendor_id = finance_vendors.id
          )
        """
    )
