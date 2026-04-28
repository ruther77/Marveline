"""Routeur principal API v1."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, products, customers, reservations, invoices, audit, health, sessions, mfa, categories, bundles, users, api_keys, features, vpn, inventory_movements, dashboard, delivery_zones, product_variants, damage_types, relances, devis, ventes, evenements, operations, suppliers, stock_management, planning, pricing, notifications, search, admin_settings, collections, formulas, supplier_orders, orders, provisioning, oauth, auth_v2, deposits, containers, treasury, tenant_brand
from app.api.v1.endpoints.restaurant import (
    bar_router,
    commandes_router,
    cuisine_router,
    dashboard_router as restaurant_dashboard_router,
    historique_router,
    ingredient_sourcing_router,
    ingredients_router,
    transferts_router as restaurant_transferts_router,
)
from app.constants import PublicEndpoints

# Routeur principal v1
api_router = APIRouter()

# Inclusion des sous-routeurs
api_router.include_router(auth.router)  # Prefix déjà défini dans auth.router
api_router.include_router(health.router)  # Health checks (Kubernetes probes)
api_router.include_router(tenant_brand.router)  # Public brand identity (no auth)
api_router.include_router(products.router)
api_router.include_router(customers.router)
api_router.include_router(reservations.router)
api_router.include_router(invoices.router)
api_router.include_router(sessions.router)       # Session management self-service
api_router.include_router(sessions.admin_router)  # Admin session endpoints §6.10
api_router.include_router(mfa.router)  # MFA TOTP
api_router.include_router(categories.router)  # Categories produits
api_router.include_router(bundles.router)  # Bundles (packs de produits)
api_router.include_router(users.router)  # User profile management
api_router.include_router(api_keys.router)  # API Keys M2M
api_router.include_router(features.router)  # Feature Flags
api_router.include_router(vpn.router)  # VPN WireGuard proxy
api_router.include_router(inventory_movements.router)  # Mouvements de stock
api_router.include_router(dashboard.router)  # Dashboard KPIs
api_router.include_router(delivery_zones.router)  # Zones de livraison
api_router.include_router(product_variants.router)  # Variantes couleur produits
api_router.include_router(damage_types.router)  # Types de dommages
api_router.include_router(relances.router)  # Relances planifiées
api_router.include_router(devis.router)  # Module Devis
api_router.include_router(ventes.router)  # Ventes directes
api_router.include_router(evenements.router)  # Événements avancés
api_router.include_router(operations.router)  # Opérations terrain (départ/retour/QR)
api_router.include_router(suppliers.router)  # Fournisseurs
api_router.include_router(stock_management.router)  # Gestion physique stock
api_router.include_router(planning.router)  # Planning semaine/mois/ressources
api_router.include_router(pricing.router)  # Règles de pricing
api_router.include_router(notifications.router)  # Notifications utilisateur
api_router.include_router(search.router)  # Recherche globale
api_router.include_router(audit.router)  # Admin uniquement
api_router.include_router(admin_settings.router)  # Paramètres tenant
api_router.include_router(collections.router)  # Collections thématiques de produits
api_router.include_router(formulas.router)  # Formules Marveline prix/personne
api_router.include_router(supplier_orders.router)  # Commandes fournisseurs (cycle commande)
api_router.include_router(orders.router)  # Commandes unifiées (devis + réservations + ventes)
api_router.include_router(provisioning.router)  # Provisioning admin tenant §S-13.2
api_router.include_router(oauth.router)  # OAuth 2.0 (Google, GitHub, Facebook)
api_router.include_router(auth_v2.router)  # IAM v2 — accounts + memberships
api_router.include_router(deposits.router)  # Cautions — vue globale admin
api_router.include_router(treasury.router)  # Tresorerie unifiee deposits + payments
api_router.include_router(containers.router)  # Contenants logistiques
# ── Carrier quotes + webhook (Boxtal) ─────────────────────────────────────────
from app.api.v1.endpoints.carrier import router as carrier_router
from app.api.v1.endpoints.carrier_webhook import router as carrier_webhook_router
api_router.include_router(carrier_router)  # POST /carrier/quotes
api_router.include_router(carrier_webhook_router)  # POST /carrier/webhook/boxtal (public, signature HMAC)
# ── WebAuthn/FIDO2 (M-03) ────────────────────────────────────────────────────
from app.api.v1.endpoints.webauthn import router as webauthn_router
api_router.include_router(webauthn_router)  # WebAuthn FIDO2 registration + auth
# ── Restaurant V2 alimentaire ──────────────────────────────────────────────────
api_router.include_router(restaurant_dashboard_router)  # KPIs, marmites, ruptures, activité
api_router.include_router(cuisine_router)  # Instances préparation, types, tickets cuisine
api_router.include_router(commandes_router)  # Tables, commandes, lignes, paiement
api_router.include_router(ingredients_router)  # Ingrédients & mouvements de stock
api_router.include_router(ingredient_sourcing_router)  # Mappings ingrédient ↔ produits épicerie + résolveur
api_router.include_router(historique_router)  # Historique + export CSV
api_router.include_router(bar_router)          # Catalogue boissons, ticket bar, formules
api_router.include_router(restaurant_transferts_router)  # Demandes transferts → épicerie (BACK-TRANSFER-RESTO-01)
# ── Épicerie V2 alimentaire ────────────────────────────────────────────────────
from app.api.v1.endpoints.epicerie.dashboard import router as epicerie_dashboard_router
from app.api.v1.endpoints.epicerie.inventaire import router as epicerie_inventaire_router, produits_router as epicerie_produits_router
from app.api.v1.endpoints.epicerie.pos import router as epicerie_pos_router
from app.api.v1.endpoints.epicerie.fournisseurs import router as epicerie_fournisseurs_router
from app.api.v1.endpoints.epicerie.commandes import router as epicerie_commandes_router
from app.api.v1.endpoints.epicerie.reception import router as epicerie_reception_router
from app.api.v1.endpoints.epicerie.transferts import router as epicerie_transferts_router

api_router.include_router(epicerie_dashboard_router)   # KPIs épicerie
api_router.include_router(epicerie_inventaire_router)  # Stock, ajustements, comptage
api_router.include_router(epicerie_produits_router)    # Produits épicerie (liste, EAN)
api_router.include_router(epicerie_pos_router)         # Encaissement POS + historique ventes
api_router.include_router(epicerie_fournisseurs_router)  # Fournisseurs + stats + factures
api_router.include_router(epicerie_commandes_router)   # Commandes fournisseurs CRUD
api_router.include_router(epicerie_reception_router)   # Réception atomique commandes
api_router.include_router(epicerie_transferts_router)  # Transferts internes épicerie → restaurant
from app.api.v1.endpoints.epicerie.transfer_requests import router as epicerie_transfer_requests_router
api_router.include_router(epicerie_transfer_requests_router)  # Demandes entrantes (BACK-TRANSFER-RESTO-01)
from app.api.v1.endpoints.epicerie.marges import router as epicerie_marges_router
api_router.include_router(epicerie_marges_router)      # Marges par catégorie
# ── Admin — ETL & supervision ──────────────────────────────────────────────────
from app.api.v1.endpoints.admin.etl_conflicts import router as admin_etl_router
from app.api.v1.endpoints.admin.etl_imports import router as admin_etl_imports_router

api_router.include_router(admin_etl_router)  # Tableau de bord résolution conflits ETL
api_router.include_router(admin_etl_imports_router)  # Queue factures fournisseur (ADR-25)

# ── Impression tickets ESC/POS ─────────────────────────────────────────────────
from app.api.v1.endpoints.printer import router as printer_router
api_router.include_router(printer_router)  # POST /print/ticket

# ── Reçu numérique (public, QR code) ──────────────────────────────────────────
from app.api.v1.endpoints.receipt import router as receipt_router
api_router.include_router(receipt_router)  # GET /receipt/{token}

# ── Fidelite (Loyalty) ───────────────────────────────────────────────────────
from app.api.v1.endpoints.loyalty import router as loyalty_router, wallet_router as loyalty_wallet_router
api_router.include_router(loyalty_router)  # Programme fidelite L'Incontournable + Marveline
api_router.include_router(loyalty_wallet_router)  # Apple Wallet callbacks

# ── Offline sync (PWA BackgroundSync) ──────────────────────────────────────────
from app.api.v1.endpoints.offline_sync import router as offline_sync_router
api_router.include_router(offline_sync_router)  # POST /offline/sync


@api_router.get("/")
async def root():
    """Endpoint racine de l'API v1."""
    return {
        "message": "CaroCorp API v1",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": PublicEndpoints.DOCS,
            "redoc": PublicEndpoints.REDOC,
        }
    }
