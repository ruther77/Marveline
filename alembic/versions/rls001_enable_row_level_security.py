"""P1-01: Enable PostgreSQL Row-Level Security on all tenant-aware tables.

Defense en profondeur : meme si le code applicatif oublie le filtre tenant_id,
PostgreSQL le bloque via les policies RLS.

La variable session app.current_tenant_id est settee par database.py avant chaque
requete via SET LOCAL (valide uniquement dans la transaction courante).

current_setting('app.current_tenant_id', true) retourne NULL si pas defini
(le flag true evite une erreur). Les superusers bypass RLS par defaut.

Revision ID: rls001
Revises: (auto-detected)
Create Date: 2026-03-21
"""
from alembic import op

revision = "rls001"
down_revision = "logi03"
branch_labels = None
depends_on = None

# 48 tables avec TenantMixin (liste exhaustive auditee le 2026-03-21)
TENANT_TABLES = [
    # Core metier
    "products", "customers", "reservations", "invoices", "deposits",
    "devis", "ventes", "inventory_movements", "payments",
    "product_bundles", "bundle_items", "categories",
    # Logistique
    "containers", "container_assignments", "container_items",
    "damage_types", "delivery_zones", "evenements",
    # Finance
    "invoice_charges", "invoice_credit_notes",
    # Inventory
    "inventory_movement_damages", "movement_item_units",
    "pricing_rules", "product_collections", "product_images",
    "product_maintenances", "product_variants", "relances",
    "stock_items", "stock_adjustments", "stock_inventaire_sessions",
    # Fournisseurs
    "suppliers", "supplier_orders", "supplier_order_lines",
    # IAM
    "api_keys",
    # Restaurant
    "restaurant_categories_ingredient", "restaurant_ingredients",
    "restaurant_alertes_stock", "restaurant_instances_preparation",
    "restaurant_lignes_commande", "restaurant_commandes",
    "restaurant_recettes_type_preparation", "restaurant_types_preparation",
    "restaurant_sides", "restaurant_mouvements_stock",
    "restaurant_variantes_plat", "restaurant_tables",
    # Epicerie
    "epicerie_produits", "epicerie_stock", "epicerie_stock_movements",
    "epicerie_ventes", "epicerie_vente_lignes", "epicerie_supply_orders",
    # Finance v2
    "finance_invoices", "finance_payments",
]


def upgrade() -> None:
    for table in TENANT_TABLES:
        # Activer RLS sur la table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE : appliquer meme au owner de la table (pas seulement aux autres roles)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # Policy : filtrer par tenant_id = session variable
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::int)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::int)
        """)


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
