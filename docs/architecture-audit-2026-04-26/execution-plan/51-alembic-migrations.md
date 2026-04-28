# 51 — Alembic Migrations Plan

> Liste ordonnée des migrations Alembic pour le refactor. Chaque entrée = 1 sprint = 1 ou plusieurs migrations.
> **Conventions** : cf. `02-conventions.md` §1.4 (naming, downgrade obligatoire, step-by-step backward-compatible).
> **Ordre d'application** : strict — chaque migration `down_revision` pointe vers la précédente.

## Index migrations

| Sprint | Migration ID | Filename | Type | Bloc |
|---|---|---|---|---|
| Sprint 1 T2 | `a1b2c3d4e5f6` | `2026_04_28_1430_add_relance_email_send_error.py` | Schema | F1058 |
| Sprint 1 T2 | `a1b2c3d4e5f7` | `2026_04_28_1431_relance_status_add_failed.py` | Schema | F1058 |
| Sprint 1 T4 | `b1c2d3e4f5a6` | `2026_04_28_1500_create_access_reviews.py` | Schema | F1055 |
| B1.S1 | `c1d2e3f4a5b5` | `2026_05_01_0830_create_pgsql_helpers.py` | Helper | §0 — `fn_set_updated_at()` requis avant tout trigger updated_at |
| B1.S1 | `c1d2e3f4a5b6` | `2026_05_01_0900_setup_audit_hmac_key_versioning.py` | Schema | Bloc 1 Q1 |
| B1.S2 | `c1d2e3f4a5b7` | `2026_05_05_0900_enable_rls_tenant_tables.py` | DDL | Bloc 1 Q2 |
| B1.S2 | `c1d2e3f4a5b8` | `2026_05_05_1000_setup_app_tenant_id_session_var.py` | Helper | Bloc 1 Q2 |
| B1.S3 | `c1d2e3f4a5b9` | `2026_05_07_0900_create_outbox_table.py` | Schema | Bloc 1 Q4 |
| B1.S3 | `c1d2e3f4a5ba` | `2026_05_07_0930_outbox_rls_null_tenant.py` | RLS | Bloc 1 Q4 — events globaux |
| B1.S5 | `c1d2e3f4a5c0` | `2026_05_12_0900_split_constants_loyalty.py` | Refactor | Bloc 1 §1.2.5 |
| B2.S2 | `d1e2f3a4b5c6` | `2026_05_19_0900_create_verticals_table.py` | Schema | Bloc 2 §2.2 |
| B1.S2 | `c1d2e3f4a5bb` | `2026_05_05_1100_enable_rls_on_tenant_settings.py` | RLS | Vague 8 — table existe déjà, juste enable RLS |
| B2.S2 | `d1e2f3a4b5c7` | `2026_05_19_1000_provisioning_atomic_helpers.py` | Helper | Bloc 2 §2.1 |
| B2.S3 | `d1e2f3a4b5c8` | `2026_05_22_0900_create_auth_vertical_scopes.py` | Schema | Bloc 2 §2.3 |
| B2.S3 | `d1e2f3a4b5c9` | `2026_05_22_1000_drop_permission_v2_legacy.py` | Cleanup | Bloc 2 §2.3 |
| B2.S5 | `d1e2f3a4b5d0` | `2026_05_29_0900_create_auth_factor_table.py` | Schema | Bloc 2 Q6=B |
| B2.S5 | `d1e2f3a4b5d1` | `2026_05_29_1000_migrate_mfa_devices_to_auth_factor.py` | Data | Bloc 2 Q6=B |
| B2.S5 | `d1e2f3a4b5d2` | `2026_05_29_1100_drop_mfa_devices_legacy.py` | Cleanup | Bloc 2 Q6=B |
| B3.S2 | `e1f2a3b4c5d6` | `2026_06_05_0900_create_fsm_transitions_table.py` | Schema | Bloc 3 §3.2.1 |
| B3.S2 | `e1f2a3b4c5d7` | `2026_06_05_1000_install_fsm_triggers.py` | Trigger | Bloc 3 §3.2.1 |
| B3.S2 | `e1f2a3b4c5d8` | `2026_06_05_1100_install_ledger_immutable_triggers.py` | Trigger | Bloc 3 §3.2.5 |
| B3.S2 | `e1f2a3b4c5d9` | `2026_06_07_0900_create_ledger_tables.py` | Schema | Bloc 3 §3.2.15 |
| B3.S3 | `e1f2a3b4c5e0` | `2026_06_12_0900_add_tva_rate_snapshot_to_lines.py` | Schema | Bloc 3 TR-3 |
| B3.S3 | `e1f2a3b4c5e1` | `2026_06_12_1000_backfill_tva_rate_snapshot.py` | Data | Bloc 3 TR-3 |
| B3.S3 | `e1f2a3b4c5e2` | `2026_06_12_1100_pricing_rules_numeric_discount.py` | Schema | Bloc 4 §4.2.5 (overlap) |
| B3.S4 | `e1f2a3b4c5e3` | `2026_06_19_0900_invoice_immutability_trigger.py` | Trigger | Bloc 3 §3.2.8 |
| B3.S4 | `e1f2a3b4c5e4` | `2026_06_19_1000_reference_unique_per_tenant.py` | Schema | Bloc 3 §3.2.10 |
| B3.S4 | `e1f2a3b4c5e5` | `2026_06_19_1100_drop_finance_legacy_tables.py` | Cleanup | Bloc 3 §3.2.9 |
| B3.S6 | `e1f2a3b4c5e6` | `2026_07_03_0900_invoices_e_invoicing_columns.py` | Schema | Bloc 3 Q19 |
| B4.S2 | `f1a2b3c4d5e6` | `2026_06_05_0900_stock_item_status_enum.py` | Schema | Bloc 4 §4.2.3 |
| B4.S2 | `f1a2b3c4d5e7` | `2026_06_05_1000_create_product_stock_view.py` | View | Bloc 4 §4.2.2 |
| B4.S2 | `f1a2b3c4d5e8` | `2026_06_05_1100_drop_product_available_quantity.py` | Cleanup | Bloc 4 Q22=A |
| B4.S2 | `f1a2b3c4d5e9` | `2026_06_05_1200_supplier_receipt_qty_check.py` | Constraint | Bloc 4 §4.2.9 |
| B4.S2 | `f1a2b3c4d5ea` | `2026_06_05_1300_stock_management_wac_pmp.py` | Schema+Trigger | Bloc 3 Q13=A — PMP/WAC |
| B2.S4 | `c4d5e6f7a8be` | `2026_05_28_0900_tenants_rp_id_frontend_url.py` | Schema+Backfill | V4-P0-03 F368 + V5-P0-02 F295 |
| B4.S5 | `f1a2b3c4d5fd` | `2026_06_29_1100_pii_extended_columns.py` | Schema | V5-P0-01 — phone+address+first_name+last_name encrypted |
| B4.S5 | `f1a2b3c4d5fe` | `2026_06_29_1200_migrate_pii_extended_to_encrypted.py` | Data | V5-P0-01 — backfill via Celery KMS |
| B4.S5 | `f1a2b3c4d5ff` | `2026_07_02_0900_drop_pii_extended_clear_text.py` | Cleanup | V5-P0-01 — drop colonnes plain text |
| B6.S3 | `b3c4d5e6f7ad` | `2026_09_03_1400_feature_flags_fail_safe_value.py` | Schema | V5-P0-04 F1031 |
| B3.S7 | `e3f4a5b6c7d8` | `2026_07_15_0900_supplier_constraints.py` | Constraint | V6-P0-03/04 F826/F827/F828 |
| B3.S7 | `e3f4a5b6c7d9` | `2026_07_15_1000_vente_lines_tva_snapshot.py` | Schema+Backfill | V6-P0-02 F728 |
| B3.S7 | `e3f4a5b6c7da` | `2026_07_15_1100_deposits_immutable_trigger.py` | Trigger | V6-P1-01 F675 |
| B3.S7 | `e3f4a5b6c7db` | `2026_07_15_1200_evenements_unique_reference.py` | Constraint | V6-P1-02 F767 |
| B4.S3 | `f1a2b3c4d5f0` | `2026_06_12_0900_categories_enrich_columns.py` | Schema | Bloc 4 §4.2.1 |
| B4.S3 | `f1a2b3c4d5f1` | `2026_06_12_1000_seed_categories_per_tenant.py` | Data | Bloc 4 §4.2.1 |
| B4.S3 | `f1a2b3c4d5f2` | `2026_06_12_1100_products_add_category_id_fk.py` | Schema | Bloc 4 §4.2.1 |
| B4.S3 | `f1a2b3c4d5f3` | `2026_06_12_1200_backfill_products_category_id.py` | Data | Bloc 4 §4.2.1 |
| B4.S3 | `f1a2b3c4d5f4` | `2026_06_15_0900_drop_products_category_string.py` | Cleanup | Bloc 4 §4.2.1 |
| B4.S3 | `f1a2b3c4d5f5` | `2026_06_15_1000_install_category_cycle_trigger.py` | Trigger | Bloc 4 F493 |
| B4.S4 | `f1a2b3c4d5f6` | `2026_06_19_0900_install_pgtrgm_extension.py` | Extension | Bloc 4 §4.2.20 |
| B4.S4 | `f1a2b3c4d5f7` | `2026_06_19_1000_create_customer_search_trgm_index.py` | Index | Bloc 4 F453 |
| B4.S4 | `f1a2b3c4d5f8` | `2026_06_19_1100_customers_iso_country.py` | Schema | Bloc 4 §4.2.15 |
| B4.S4 | `f1a2b3c4d5f8a` | `2026_06_19_1130_tenant_settings_add_rfm_thresholds.py` | Schema | Q27=B — ALTER ADD COLUMN sur table existante (Vague 8) |
| B4.S5 | `f1a2b3c4d5f9` | `2026_06_26_0900_pii_encrypted_columns.py` | Schema | Bloc 4 §4.2.7 |
| B4.S5 | `f1a2b3c4d5f9a` | `2026_06_26_0930_tenant_settings_add_pii_encryption_enabled.py` | Schema | Q28=B — ALTER ADD COLUMN sur table existante (Vague 8) |
| B4.S5 | `f1a2b3c4d5fa` | `2026_06_26_1000_migrate_pii_to_encrypted.py` | Data | Bloc 4 §4.2.7 |
| B4.S5 | `f1a2b3c4d5fb` | `2026_06_29_0900_drop_pii_clear_text.py` | Cleanup | Bloc 4 §4.2.7 |
| B4.S5 | `f1a2b3c4d5fc` | `2026_06_29_1000_item_condition_enum.py` | Schema | Bloc 4 §4.2.16 |
| B5.S2 | `a2b3c4d5e6f7` | `2026_07_03_0900_split_etl_referential_per_tenant.py` | Data | Bloc 5 Q29=A |
| B5.S2 | `a2b3c4d5e6f8` | `2026_07_03_1000_create_categorie_produit_seed.py` | Schema | Bloc 5 Q29=A |
| B5.S2 | `a2b3c4d5e6f9` | `2026_07_06_0900_install_cross_tenant_triggers.py` | Trigger | Bloc 5 §5.2.2 |
| B5.S5 | `a2b3c4d5e6fa` | `2026_07_17_0900_categorie_id_fk_catalogue.py` | Schema | Bloc 5 §5.2.12 |
| B5.S6 | `a2b3c4d5e6fb` | `2026_07_24_0900_catalogue_produit_price_history.py` | Schema | Bloc 5 §5.2.16 |
| B6.S2 | `b3c4d5e6f7a8` | `2026_08_07_0900_audit_logs_hmac_chain.py` | Schema | Bloc 6 §6.2.4 |
| B6.S2 | `b3c4d5e6f7a9` | `2026_08_07_1000_audit_logs_pii_encrypted.py` | Schema | Bloc 6 §6.2.6 |
| B6.S2 | `b3c4d5e6f7aa` | `2026_08_10_0900_audit_logs_drop_clear_text.py` | Cleanup | Bloc 6 §6.2.6 |
| B6.S3 | `b3c4d5e6f7ab` | `2026_08_14_0900_feature_flag_tenants_table.py` | Schema | Bloc 6 §6.2.10 |
| B6.S3 | `b3c4d5e6f7ac` | `2026_08_14_1000_drop_target_tenants_array.py` | Cleanup | Bloc 6 §6.2.10 |
| B6.S3 | `b3c4d5e6f7ad` | `2026_08_14_1100_feature_flag_history_table.py` | Schema | Bloc 6 §6.2.10 |
| B6.S1 | `b3c4d5e6f7ae` | `2026_08_03_0900_notification_log_table.py` | Schema | Bloc 6 §6.2.2 |
| B6.S1 | `b3c4d5e6f7af` | `2026_08_03_1000_notifications_v2_account_id.py` | Schema | Bloc 6 §6.2.2 |
| B7.S1 | `c4d5e6f7a8b9` | `2026_09_04_0900_tenants_add_vertical_brand.py` | Schema | Bloc 7 §7.2 |
| B7.S1 | `c4d5e6f7a8ba` | `2026_09_04_1000_backfill_tenants_vertical.py` | Data | Bloc 7 §7.2 |
| B7.S1 | `c4d5e6f7a8bb` | `2026_09_07_0900_drop_tenant_app_code_check.py` | Cleanup | Bloc 7 §7.2 |
| B7.S1 | `c4d5e6f7a8bc` | `2026_09_07_1000_rename_apps_to_verticals.py` | Schema | Bloc 7 §2.2 |
| B7.S2 | `c4d5e6f7a8bd` | `2026_09_11_0900_drop_brand_code_catalogue.py` | Cleanup | Bloc 7 Q43=B |
| B7.S2 | `c4d5e6f7a8be` | `2026_09_11_1000_drop_is_multi_brand_tenant.py` | Cleanup | Bloc 7 Q43=B |

---

## Détail migrations critiques

### Migration `c1d2e3f4a5b7` — Enable RLS on tenant tables (B1.S2)

```python
"""Enable Row-Level Security on tenant-scoped tables (Bloc 1 Q2=A)

Revision ID: c1d2e3f4a5b7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-05 09:00:00.000000

Bloc 1 Q2=A : RLS enforce DB-side, repository qui oublie tenant_id = SELECT vide.
"""
from alembic import op

revision = "c1d2e3f4a5b7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

# Liste exhaustive des tables tenant-scoped
TENANT_TABLES = [
    "customers",
    "products",
    "product_variants",
    "product_bundles",
    "bundle_items",
    "categories",
    "product_collections",
    "product_images",
    "product_maintenances",
    "stock_items",
    "stock_management",
    "inventory_movements",
    "movement_items",
    "movement_item_units",
    "movement_damages",
    "reservations",
    "reservation_lines",
    "reservation_versions",
    "reservation_workflows",
    "devis",
    "devis_lines",
    "deposits",
    "invoices",
    "invoice_lines",
    "invoice_charges",
    "invoice_credit_notes",
    "payments",
    "ventes",
    "vente_lines",
    "relances",
    "loyalty_members",
    "loyalty_programs",
    "points_ledger",
    "revenue_ledger",
    "payment_ledger",
    "tier_history",
    "wallet_passes",
    "rewards_catalog",
    "reward_redemptions",
    "referral_links",
    "flash_offers",
    "loyalty_notification_log",
    "suppliers",
    "supplier_orders",
    "supplier_order_lines",
    "supplier_order_receipts",
    "supplier_order_receipt_lines",
    "supplier_product_prices",
    "evenements",
    "event_incidents",
    "incident_actions",
    "epicerie_produits",
    "epicerie_stock",
    "epicerie_stock_movements",
    "epicerie_ventes",
    "epicerie_vente_lignes",
    "internal_transfers",
    "internal_transfer_lines",
    "supply_orders",
    "supply_order_lines",
    "marges",
    "prix_historiques",
    "produits_ean",
    "restaurant_ingredients",
    "restaurant_categorie_ingredients",
    "restaurant_types_preparation",
    "restaurant_recettes_type_preparation",
    "restaurant_instances_preparation",
    "restaurant_variantes_plats",
    "restaurant_variantes_sides",
    "restaurant_sides",
    "restaurant_tables",
    "restaurant_commandes",
    "restaurant_lignes_commande",
    "mouvements_stock_restaurant",
    "alertes_stock_restaurant",
    "transfer_requests",
    "transfer_request_lines",
    "ingredient_epicerie_mappings",
    "audit_logs",
    "feature_flag_tenants",
    "tenant_memberships",
    "account_sessions",
    "api_keys",
    "auth_factors",
    "access_reviews",
    "notifications",
    "notification_log",
    # NOTE — `outbox_events` EXCLU de RLS auto :
    # `outbox_events.tenant_id` est NULLABLE (events globaux : provisioning, beat heartbeat,
    # migrations DEVUP-level). La policy générique `tenant_id = current_setting(...)::bigint`
    # filtre silencieusement les rows NULL → dispatcher aveugle.
    # Politique custom appliquée via migration dédiée (cf. infra) ou filtrage applicatif.
    "categorie_produits",
    "catalogue_produits",
    "catalogue_produit_eans",
    "catalogue_produit_colisages",
    "catalogue_produit_price_history",
    "etl_imports",
    "etl_conflicts",
    "etl_correction_history",
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);
        """)
        # Force RLS pour le rôle applicatif (BYPASSRLS reste pour superadmin DEVUP)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    # Ordre inverse pour rollback
    for table in reversed(TENANT_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
```

### Migration `c1d2e3f4a5ba` — RLS policy custom `outbox_events` (events globaux NULL)

```python
"""Outbox RLS policy with NULL tenant exception.

Revision ID: c1d2e3f4a5ba
Revises: c1d2e3f4a5b9
Create Date: 2026-05-12 11:00:00.000000

`outbox_events.tenant_id` est NULLABLE (events globaux DEVUP-level : provisioning,
beat heartbeat, broker migrations). La policy générique TENANT_TABLES filtre
silencieusement les rows NULL → le dispatcher Outbox ne verrait jamais ces events.

Cette migration applique une policy custom qui :
- laisse passer les rows tenant_id IS NULL (events globaux, lus par worker DEVUP)
- filtre tenant_id par le current_setting standard pour les events tenant-scoped

Le worker dispatcher tourne sous un rôle BYPASSRLS séparé (cf. §6.2.7 architecture-cible).
"""
from alembic import op

revision = "c1d2e3f4a5ba"
down_revision = "c1d2e3f4a5b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation_outbox_events ON outbox_events
            USING (
                tenant_id IS NULL
                OR tenant_id = current_setting('app.current_tenant_id', true)::bigint
            )
            WITH CHECK (
                tenant_id IS NULL
                OR tenant_id = current_setting('app.current_tenant_id', true)::bigint
            );
    """)
    op.execute("ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE outbox_events NO FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_outbox_events ON outbox_events;")
    op.execute("ALTER TABLE outbox_events DISABLE ROW LEVEL SECURITY;")
```

### Migration `e1f2a3b4c5e1` — Backfill tva_rate_snapshot (B3.S3)

```python
"""Backfill tva_rate_snapshot on existing invoice/devis/reservation/vente lines.

Revision ID: e1f2a3b4c5e1
Revises: e1f2a3b4c5e0
Create Date: 2026-06-12 10:00:00.000000

Bloc 3 TR-3 : capture TVA snapshot sur lignes existantes (avant ALTER NOT NULL).
Source : Product.tva_rate (legacy) → si NULL, utilise Tenant.settings.default_tva_rate.

ATTENTION : migration data, peut être longue (~10 min sur 100k lines).
Lance Celery task en background si volume > 10k rows.
"""
from alembic import op
from sqlalchemy import text

revision = "e1f2a3b4c5e1"
down_revision = "e1f2a3b4c5e0"
branch_labels = None
depends_on = None


TABLES_WITH_TVA_SNAPSHOT = [
    ("invoice_lines", "product_id"),
    ("devis_lines", "product_id"),
    ("reservation_lines", "product_id"),
    ("vente_lines", "product_id"),
    ("epicerie_vente_lignes", "produit_id"),
    ("restaurant_lignes_commande", "variante_id"),  # via VariantePlat → Product (ajustement)
]


def upgrade() -> None:
    conn = op.get_bind()
    
    for table, product_fk in TABLES_WITH_TVA_SNAPSHOT:
        # Backfill via JOIN Product → Category (Bloc 4 §4.2.1)
        # Si Category pas encore migrée (B4.S3 pas livré) : utilise Product.tva_rate (legacy)
        # Sinon : Category.tva_rate
        
        # Strategy 1 : Product.tva_rate legacy (avant B4.S3)
        if conn.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_name='products' AND column_name='tva_rate'
            )
        """)).scalar():
            conn.execute(text(f"""
                UPDATE {table} SET tva_rate_snapshot = COALESCE(p.tva_rate, 0.20)
                FROM products p
                WHERE {table}.{product_fk} = p.id
                  AND {table}.tva_rate_snapshot IS NULL
            """))
        else:
            # Strategy 2 : via Category.tva_rate
            conn.execute(text(f"""
                UPDATE {table} SET tva_rate_snapshot = COALESCE(c.tva_rate, 0.20)
                FROM products p
                JOIN categories c ON c.id = p.category_id
                WHERE {table}.{product_fk} = p.id
                  AND {table}.tva_rate_snapshot IS NULL
            """))
        
        # Vérifier qu'il ne reste aucun NULL
        remaining = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE tva_rate_snapshot IS NULL")).scalar()
        if remaining > 0:
            raise RuntimeError(
                f"Backfill incomplete for {table}: {remaining} rows still NULL. "
                f"Investigate orphan {product_fk} references."
            )


def downgrade() -> None:
    # Pas de downgrade data : tva_rate_snapshot restera populated
    # (drop colonne se fait via migration séparée si rollback complet nécessaire)
    pass  # documenté irréversible
```

### Migration `f1a2b3c4d5e7` — Create product_stock_view (B4.S2)

```python
"""Create product_stock_view materialized view (Bloc 4 §4.2.2 + Q22=A).

Revision ID: f1a2b3c4d5e7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-05 10:00:00.000000

View matérialisée pour stock dérivé de stock_items.
Refresh debounced 5s via NOTIFY trigger + worker Celery.
"""
from alembic import op

revision = "f1a2b3c4d5e7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW product_stock_view AS
        SELECT
            si.tenant_id,
            si.product_id,
            si.variant_id,
            COUNT(*) FILTER (WHERE si.status = 'available'::stock_item_status)                  AS available,
            COUNT(*) FILTER (WHERE si.status = 'reserved'::stock_item_status)                   AS reserved,
            COUNT(*) FILTER (WHERE si.status = 'on_location'::stock_item_status)                AS on_location,
            COUNT(*) FILTER (WHERE si.status IN ('damaged'::stock_item_status, 'in_repair'::stock_item_status)) AS unavailable,
            COUNT(*) FILTER (WHERE si.status != 'retired'::stock_item_status)                   AS total_active
        FROM stock_items si
        WHERE si.retired = false
        GROUP BY si.tenant_id, si.product_id, si.variant_id;
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX uq_product_stock_view_pkv ON product_stock_view (tenant_id, product_id, variant_id);
    """)
    
    op.execute("""
        CREATE INDEX idx_product_stock_view_tenant_product ON product_stock_view (tenant_id, product_id);
    """)
    
    # Trigger NOTIFY pour worker refresh debounced
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_stock_view_refresh() RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('stock_view_dirty', json_build_object(
                'tenant_id', COALESCE(NEW.tenant_id, OLD.tenant_id),
                'product_id', COALESCE(NEW.product_id, OLD.product_id)
            )::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trg_stock_items_notify_view
            AFTER INSERT OR UPDATE OR DELETE ON stock_items
            FOR EACH ROW EXECUTE FUNCTION notify_stock_view_refresh();
    """)
    
    # Refresh initial
    op.execute("REFRESH MATERIALIZED VIEW product_stock_view;")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_stock_items_notify_view ON stock_items;")
    op.execute("DROP FUNCTION IF EXISTS notify_stock_view_refresh();")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS product_stock_view CASCADE;")
```

### Migration `f1a2b3c4d5f3` — Backfill products.category_id (B4.S3)

```python
"""Backfill products.category_id from products.category string.

Revision ID: f1a2b3c4d5f3
Revises: f1a2b3c4d5f2
Create Date: 2026-06-12 12:00:00.000000

Strategy : pour chaque tenant, lookup Category par (tenant_id, code=products.category).
Échoue avec IntegrityError si tenant a un Product.category sans Category correspondante seedée.
Pré-requis : f1a2b3c4d5f1 (seed Categories) doit être appliquée.
"""
from alembic import op
from sqlalchemy import text

revision = "f1a2b3c4d5f3"
down_revision = "f1a2b3c4d5f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # 1. Update products.category_id depuis Category lookup
    conn.execute(text("""
        UPDATE products p
        SET category_id = c.id
        FROM categories c
        WHERE c.tenant_id = p.tenant_id
          AND c.code = p.category
          AND p.category_id IS NULL
    """))
    
    # 2. Vérifier qu'aucun Product n'a category_id NULL
    orphans = conn.execute(text("""
        SELECT id, tenant_id, category, name FROM products WHERE category_id IS NULL LIMIT 10
    """)).fetchall()
    
    if orphans:
        raise RuntimeError(
            f"Backfill products.category_id incomplete. {len(orphans)} orphans (showing first 10):\n"
            + "\n".join(f"  - id={r[0]} tenant={r[1]} category='{r[2]}' name='{r[3]}'" for r in orphans)
            + "\nFix : ajouter Category(tenant_id, code=<missing>) seed pour chaque tenant manquant."
        )
    
    # 3. Maintenant on peut SET NOT NULL
    op.alter_column("products", "category_id", nullable=False)


def downgrade() -> None:
    op.alter_column("products", "category_id", nullable=True)
    # Note : la colonne products.category string a été dropée par f1a2b3c4d5f4
    # Donc le rollback complet nécessite aussi f1a2b3c4d5f4 downgrade
```

### Migration `c4d5e6f7a8ba` — Backfill tenants.vertical (B7.S1)

```python
"""Backfill tenants.vertical from current app_code.

Revision ID: c4d5e6f7a8ba
Revises: c4d5e6f7a8b9
Create Date: 2026-09-04 10:00:00.000000

Mapping app_code → vertical :
  marveline, splendid, lesplendid → 'location'
  epicerie, massacorp_epi         → 'epicerie'
  restaurant, massacorp_resto     → 'restaurant'
  atdt                            → 'autour_de_table'

Tenants existants en prod : marveline, lesplendid, epicerie, restaurant
"""
from alembic import op
from sqlalchemy import text

revision = "c4d5e6f7a8ba"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


VERTICAL_MAPPING = {
    "marveline": "location",
    "splendid": "location",
    "lesplendid": "location",
    "epicerie": "epicerie",
    "massacorp_epi": "epicerie",
    "restaurant": "restaurant",
    "massacorp_resto": "restaurant",
    "atdt": "autour_de_table",
}


def upgrade() -> None:
    conn = op.get_bind()
    
    # 1. Lookup tenants existants sans vertical
    rows = conn.execute(text("SELECT id, app_code FROM tenants WHERE vertical IS NULL")).fetchall()
    
    for row in rows:
        tid, app_code = row
        vertical = VERTICAL_MAPPING.get(app_code)
        if vertical is None:
            raise RuntimeError(
                f"Tenant {tid} has app_code='{app_code}' not in VERTICAL_MAPPING. "
                f"Add to VERTICAL_MAPPING in this migration before running."
            )
        conn.execute(
            text("UPDATE tenants SET vertical = :v WHERE id = :tid"),
            {"v": vertical, "tid": tid}
        )
    
    # 2. Vérifier qu'aucun tenant n'est sans vertical
    remaining = conn.execute(text("SELECT COUNT(*) FROM tenants WHERE vertical IS NULL")).scalar()
    if remaining > 0:
        raise RuntimeError(f"Tenants still without vertical: {remaining}")
    
    # 3. SET NOT NULL
    op.alter_column("tenants", "vertical", nullable=False)


def downgrade() -> None:
    op.alter_column("tenants", "vertical", nullable=True)
    # Pas de UPDATE inverse : si rollback nécessaire, restore depuis backup pre-migration
```

### Migration `c4d5e6f7a8bd` — Drop brand_code Catalogue (B7.S2)

```python
"""Drop brand_code from Catalogue (Bloc 7 Q43=B).

Revision ID: c4d5e6f7a8bd
Revises: c4d5e6f7a8bc
Create Date: 2026-09-11 09:00:00.000000

Q43=B : 2 tenants distincts (Marveline / Splendid), pas de multi-brand intra-tenant.
Drop des colonnes brand_code sur Product, Category, Bundle, ProductCollection.

Audit data préalable (à faire manuellement avant cette migration) :
  SELECT COUNT(DISTINCT brand_code) FROM products WHERE brand_code IS NOT NULL;
  -- Si > 0 : confirmer avec DEVUP que tenant_id est bien splitté Marveline/Splendid avant drop.
"""
from alembic import op

revision = "c4d5e6f7a8bd"
down_revision = "c4d5e6f7a8bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop colonnes brand_code (catalogue)
    for table in ["products", "categories", "product_bundles", "product_collections"]:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS brand_code;")
    
    # Drop indexes éventuels
    op.execute("DROP INDEX IF EXISTS idx_products_brand_code;")
    op.execute("DROP INDEX IF EXISTS idx_categories_brand_code;")


def downgrade() -> None:
    # Re-add brand_code colonnes (vides — data perdue irréversiblement)
    for table in ["products", "categories", "product_bundles", "product_collections"]:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS brand_code VARCHAR(50) NULL;")
    # Pas de backfill possible — data perdue. Restore depuis backup pre-migration si nécessaire.
```

---

## Pattern step-by-step backward-compatible

Pour les migrations qui touchent une colonne en production active (ex: `Product.available_quantity` lue/écrite par 30+ services), suivre **4 déploiements** :

### Step 1 : Add new column nullable

```python
# Migration A
def upgrade():
    op.add_column("products", sa.Column("category_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_products_category", "products", "categories", ["category_id"], ["id"])
```

**Déploiement A** : code lit l'ancienne colonne, ne touche pas à la nouvelle.

### Step 2 : Backfill via Celery task

```python
# Migration B (data only, idempotent)
def upgrade():
    op.execute("""
        UPDATE products p SET category_id = c.id
        FROM categories c WHERE c.code = p.category AND c.tenant_id = p.tenant_id
          AND p.category_id IS NULL
    """)
```

**Déploiement B** : code lit l'ancienne, écrit DOUBLE (ancienne + nouvelle). Celery task `backfill_category_id_task` complète les rows manquantes.

### Step 3 : Switch reads to new column + ALTER NOT NULL

```python
# Migration C
def upgrade():
    # Vérifier 0 NULL
    op.execute("DO $$ BEGIN IF (SELECT COUNT(*) FROM products WHERE category_id IS NULL) > 0 THEN RAISE EXCEPTION 'incomplete backfill'; END IF; END $$;")
    op.alter_column("products", "category_id", nullable=False)
```

**Déploiement C** : code lit la nouvelle, écrit la nouvelle uniquement. L'ancienne devient orpheline.

### Step 4 : Drop old column

```python
# Migration D
def upgrade():
    op.drop_column("products", "category")
    op.drop_constraint("check_product_category_valid", "products", type_="check")
```

**Déploiement D** : nettoyage. L'ancienne colonne disparaît.

**Pourquoi** : si à n'importe quelle étape on rollback, on ne perd pas de data. Idempotence backfill. Lecture toujours possible.

---

## Tests Alembic

### Test idempotence

```python
# tests/integration/migrations/test_alembic_idempotence.py
import pytest
from alembic.config import Config
from alembic import command


def test_upgrade_downgrade_upgrade_cycle(alembic_config):
    """Upgrade head + downgrade base + upgrade head = OK (idempotence)."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


def test_each_migration_individually(alembic_config):
    """Chaque migration up/down individuellement (sans cumul)."""
    # Liste des revisions
    revisions = [...]  # parsed from alembic/versions/
    for rev in revisions:
        command.upgrade(alembic_config, rev)
        command.downgrade(alembic_config, "-1")
        command.upgrade(alembic_config, rev)
```

### Test cohérence schema cible

```python
def test_final_schema_matches_models(alembic_config, async_db):
    """Après upgrade head, le schema DB matches les models SQLAlchemy."""
    command.upgrade(alembic_config, "head")
    
    # Comparer pg_class + information_schema vs Base.metadata
    # (nécessite SQLAlchemy autogenerate compare_schema)
    from alembic.autogenerate import compare_metadata
    from app.models.base import Base
    
    diff = compare_metadata(...)
    assert diff == [], f"Schema drift: {diff}"
```

---

## Volume migrations par bloc

| Bloc | # migrations | Effort total | Type principal |
|---|---|---|---|
| Sprint 1 | 3 | 0.5j | Schema + Data |
| Bloc 1 | 6 | 5j | DDL + Helpers |
| Bloc 2 | 8 | 8j | Schema + Data + Trigger |
| Bloc 3 | 7 | 7j | Trigger + Schema + Data |
| Bloc 4 | 14 | 12j | Schema + Data + Trigger + Index |
| Bloc 5 | 6 | 6j | Schema + Data + Trigger |
| Bloc 6 | 7 | 6j | Schema + Data |
| Bloc 7 | 5 | 4j | Schema + Cleanup |
| **Total** | **56 migrations** | **~48 jours-homme** | — |

**Pic effort** : Bloc 4 (Catalogue/Stock) avec 14 migrations dont 4 data backfill complexes (Category seed, products.category_id, PII encryption, item_condition enum).

---

## Procédure déploiement

### Pre-deploy checklist

1. ✅ Migration testée upgrade + downgrade en local
2. ✅ Migration testée sur copie staging avec data réelle
3. ✅ Tests régression : `pytest tests/` complet vert post-upgrade
4. ✅ Bench perf : pas de dégradation >10% sur top 20 queries
5. ✅ Plan rollback documenté + testé
6. ✅ Communication clients (si maintenance window nécessaire)
7. ✅ Backup DB pre-deploy (point-in-time recovery activé)
8. ✅ AlertManager prêt (alertes proactives sur erreurs migration)

### Deploy sequence

```bash
# 1. Backup DB
pg_dump $DATABASE_URL | gzip > backup-$(date +%Y%m%d-%H%M).sql.gz

# 2. Apply migration
alembic upgrade <revision>

# 3. Smoke test prod
curl https://api.devup.fr/health/ready
pytest tests/smoke -v

# 4. Monitor 30 min
# Loki : ERROR rate stable
# Grafana : http_request_duration_p99 stable
# AlertManager : 0 alerte

# 5. If OK : commit `migration applied <revision>` + Slack #devup-eng-prod
# 6. If KO : alembic downgrade -1 + investigation
```

---

## Volume DDL (lignes SQL générées)

Les ~56 migrations produisent ~3000 lignes SQL au total :
- ~800 lignes `CREATE TABLE`
- ~600 lignes `ALTER TABLE` (add/drop column)
- ~400 lignes `CREATE INDEX`
- ~500 lignes `CREATE TRIGGER` + functions PL/pgSQL
- ~400 lignes data migration (UPDATE backfill)
- ~200 lignes seed data
- ~100 lignes RLS policies

**Pré-requis** : `50-sql-schema.md` doit être lu avant chaque migration pour comprendre l'état cible.
