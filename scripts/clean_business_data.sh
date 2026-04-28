#!/usr/bin/env bash
# ============================================================================
# clean_business_data.sh — Supprime toutes les données métier et reset les séquences
#
# Usage :
#   ./scripts/clean_business_data.sh [tenant_id]
#   Default: tenant_id=1
#
# Conserve : produits, catégories, bundles, stock_items, comptes, tenants, audit_logs
# Supprime : clients, devis, réservations, factures, paiements, mouvements, etc.
# ============================================================================

set -euo pipefail

TENANT_ID="${1:-1}"
COMPOSE_CMD="docker compose"

echo "=== Clean données métier tenant ${TENANT_ID} ==="

$COMPOSE_CMD exec -T db psql -U caro -d CaroCorp -c "
BEGIN;

-- Suppression dans l'ordre FK
DELETE FROM movement_item_units WHERE tenant_id = ${TENANT_ID};
DELETE FROM inventory_movement_damages WHERE tenant_id = ${TENANT_ID};
DELETE FROM movement_items WHERE tenant_id = ${TENANT_ID};
DELETE FROM inventory_movements WHERE tenant_id = ${TENANT_ID};
DELETE FROM invoice_charges WHERE tenant_id = ${TENANT_ID};
DELETE FROM invoice_credit_notes WHERE tenant_id = ${TENANT_ID};
DELETE FROM payments WHERE tenant_id = ${TENANT_ID};
DELETE FROM invoices WHERE tenant_id = ${TENANT_ID};
DELETE FROM deposits WHERE tenant_id = ${TENANT_ID};
DELETE FROM reservation_pre_check_items WHERE tenant_id = ${TENANT_ID};
DELETE FROM reservation_extensions WHERE tenant_id = ${TENANT_ID};
DELETE FROM reservation_lines WHERE tenant_id = ${TENANT_ID};
DELETE FROM reservations WHERE tenant_id = ${TENANT_ID};
DELETE FROM devis_lines WHERE tenant_id = ${TENANT_ID};
DELETE FROM devis_versions WHERE tenant_id = ${TENANT_ID};
DELETE FROM devis_negotiations WHERE tenant_id = ${TENANT_ID};
DELETE FROM devis WHERE tenant_id = ${TENANT_ID};
DELETE FROM customers WHERE tenant_id = ${TENANT_ID};
DELETE FROM vente_payments WHERE tenant_id = ${TENANT_ID};
DELETE FROM vente_lines WHERE tenant_id = ${TENANT_ID};
DELETE FROM ventes WHERE tenant_id = ${TENANT_ID};
DELETE FROM notifications WHERE tenant_id = ${TENANT_ID};
DELETE FROM relances WHERE tenant_id = ${TENANT_ID};
UPDATE stock_items SET status = 'available', current_reservation_id = NULL
  WHERE tenant_id = ${TENANT_ID} AND status != 'available';

-- Reset séquences
SELECT setval('customers_id_seq', 1, false);
SELECT setval('devis_id_seq', 1, false);
SELECT setval('devis_lines_id_seq', 1, false);
SELECT setval('devis_versions_id_seq', 1, false);
SELECT setval('reservations_id_seq', 1, false);
SELECT setval('reservation_lines_id_seq', 1, false);
SELECT setval('reservation_pre_check_items_id_seq', 1, false);
SELECT setval('invoices_id_seq', 1, false);
SELECT setval('payments_id_seq', 1, false);
SELECT setval('deposits_id_seq', 1, false);
SELECT setval('inventory_movements_id_seq', 1, false);
SELECT setval('movement_items_id_seq', 1, false);
SELECT setval('movement_item_units_id_seq', 1, false);
SELECT setval('invoice_charges_id_seq', 1, false);
SELECT setval('invoice_credit_notes_id_seq', 1, false);
SELECT setval('notifications_id_seq', 1, false);
SELECT setval('relances_id_seq', 1, false);
SELECT setval('ventes_id_seq', 1, false);

-- Resync available_quantity produits et variantes
UPDATE products p
SET available_quantity = (
    SELECT count(*) FROM stock_items si
    WHERE si.product_id = p.id AND si.tenant_id = p.tenant_id AND si.status = 'available'
)
WHERE p.tenant_id = ${TENANT_ID};

UPDATE product_variants pv
SET available_quantity = (
    SELECT count(*) FROM stock_items si
    WHERE si.variant_id = pv.id AND si.tenant_id = pv.tenant_id AND si.status = 'available'
)
WHERE pv.tenant_id = ${TENANT_ID};

COMMIT;
"

echo "=== Done. Prochain client=id 1, devis=id 1, resa=id 1 ==="
