"""V2 Épicerie + Finance — 13 tables + altération restaurant_mouvements_stock.

Crée toutes les tables du domaine Épicerie et Finance dans l'ordre FK :
  F01 : finance_entities          (référentiel global, sans tenant_id)
  F02 : finance_vendors           (référentiel global, sans tenant_id)
  F03 : finance_invoices          (tenant, supply_order/vente/transfer fks ajoutées après)
  E01 : epicerie_produits         (tenant_id=2, FK finance_vendors)
  E02 : epicerie_stock            (tenant, FK epicerie_produits)
  E03 : epicerie_stock_movements  (tenant, FK epicerie_produits, accounts)
  E04 : epicerie_ventes           (tenant, FK accounts, finance_invoices)
  E05 : epicerie_vente_lignes     (tenant, FK epicerie_ventes, epicerie_produits)
  E06 : epicerie_supply_orders    (tenant, FK finance_vendors, finance_invoices)
  E07 : epicerie_supply_order_lines (FK epicerie_supply_orders, epicerie_produits)
  T01 : internal_transfers        (FK finance_entities x2, accounts x2, finance_invoices)
  T02 : internal_transfer_lines   (FK internal_transfers, epicerie_produits,
                                   restaurant_ingredients, epicerie_stock_movements,
                                   restaurant_mouvements_stock)
  F04 : finance_payments          (tenant, FK finance_invoices)

  + FK retour sur finance_invoices (supply_order_id, vente_id, transfer_id)
  + Altération restaurant_mouvements_stock.ingredient_id : nullable + SET NULL

Stratégie expand/contract :
  - Toutes les tables sont nouvelles sauf restaurant_mouvements_stock (altération colonne).
  - L'altération ingredient_id est réversible (downgrade remet nullable=False + RESTRICT).
  - Rollback : downgrade() supprime dans l'ordre inverse des FK.

Références :
    V2_API_EPICERIE.md (source de vérité endpoints)
    ADR-02 (finance_vendors global), ADR-03 (internal_transfers via finance_entities)
    ADR-06-BIS (TVA variable par catégorie, défaut 20%)
    ADR-14 (stock lecture directe DB)

Revision ID: s1t2u3v4w5x6
Revises: r0s1t2u3v4w5
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "s1t2u3v4w5x6"
down_revision = "r0s1t2u3v4w5"
branch_labels = None
depends_on = None

STOCK_PRECISION = 10
STOCK_SCALE = 3


def upgrade() -> None:
    # ── F01 : finance_entities ────────────────────────────────────────────────
    op.create_table(
        "finance_entities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("nom", sa.String(100), nullable=False,
                  comment="Nom lisible de l'entité (ex: Épicerie, Restaurant)"),
        sa.Column("type", sa.String(20), nullable=False,
                  comment="Type : EPICERIE | RESTAURANT | EXTERNE"),
        sa.Column("code", sa.String(20), nullable=True,
                  comment="Code court unique"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('EPICERIE', 'RESTAURANT', 'EXTERNE')",
            name="check_finance_entity_type_valide",
        ),
        sa.UniqueConstraint("code", name="uq_finance_entity_code"),
    )
    op.create_index("idx_finance_entity_code", "finance_entities", ["code"])
    op.create_index("idx_finance_entity_type", "finance_entities", ["type"])

    # Données initiales : épicerie=1, restaurant=2
    op.execute(
        "INSERT INTO finance_entities (id, nom, type, code) VALUES "
        "(1, 'Épicerie', 'EPICERIE', 'EPICERIE'), "
        "(2, 'Restaurant', 'RESTAURANT', 'RESTO')"
    )
    op.execute("SELECT setval('finance_entities_id_seq', 2, true)")

    # ── F02 : finance_vendors ─────────────────────────────────────────────────
    op.create_table(
        "finance_vendors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False,
                  comment="Raison sociale"),
        sa.Column("code", sa.String(50), nullable=True,
                  comment="Code court unique"),
        sa.Column("adresse", sa.Text(), nullable=True),
        sa.Column("telephone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_finance_vendor_code"),
    )
    op.create_index("idx_finance_vendor_code", "finance_vendors", ["code"])
    op.create_index("idx_finance_vendor_name", "finance_vendors", ["name"])

    # ── F03 : finance_invoices (sans FK retour — ajoutées après les tables dépendantes) ──
    op.create_table(
        "finance_invoices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False,
                  comment="FOURNISSEUR | CLIENT | INTERNE"),
        sa.Column("numero", sa.String(50), nullable=False,
                  comment="FAC-YYYYMMDD-NNNN"),
        sa.Column("date_facture", sa.Date(), nullable=False),
        sa.Column("date_echeance", sa.Date(), nullable=True),
        sa.Column("montant_ht", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_tva", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_ttc", sa.BigInteger(), nullable=False, default=0),
        sa.Column("statut", sa.String(20), nullable=False, default="EN_ATTENTE",
                  comment="EN_ATTENTE | PAYEE | EN_RETARD | ANNULEE"),
        # Références contextuelles — FK définies après la création des tables cibles
        sa.Column("vendor_id", sa.BigInteger(),
                  sa.ForeignKey("finance_vendors.id", ondelete="SET NULL",
                                name="fk_finance_invoice_vendor"),
                  nullable=True),
        sa.Column("supply_order_id", sa.BigInteger(), nullable=True,
                  comment="FK epicerie_supply_orders — ajoutée après"),
        sa.Column("vente_id", sa.BigInteger(), nullable=True,
                  comment="FK epicerie_ventes — ajoutée après"),
        sa.Column("transfer_id", sa.BigInteger(), nullable=True,
                  comment="FK internal_transfers — ajoutée après"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('FOURNISSEUR', 'CLIENT', 'INTERNE')",
            name="check_finance_invoice_type_valide",
        ),
        sa.CheckConstraint(
            "statut IN ('EN_ATTENTE', 'PAYEE', 'EN_RETARD', 'ANNULEE')",
            name="check_finance_invoice_statut_valide",
        ),
        sa.CheckConstraint("montant_ht >= 0",
                           name="check_finance_invoice_montant_ht_positif"),
        sa.CheckConstraint("montant_ttc >= 0",
                           name="check_finance_invoice_montant_ttc_positif"),
    )
    op.create_index("idx_finance_invoice_tenant", "finance_invoices", ["tenant_id"])
    op.create_index("idx_finance_invoice_tenant_numero", "finance_invoices",
                    ["tenant_id", "numero"], unique=True)
    op.create_index("idx_finance_invoice_statut", "finance_invoices", ["statut"])
    op.create_index("idx_finance_invoice_vendor", "finance_invoices", ["vendor_id"])
    op.create_index("idx_finance_invoice_supply_order",
                    "finance_invoices", ["supply_order_id"])
    op.create_index("idx_finance_invoice_vente", "finance_invoices", ["vente_id"])
    op.create_index("idx_finance_invoice_transfer", "finance_invoices", ["transfer_id"])
    op.create_index("idx_finance_invoice_date", "finance_invoices", ["date_facture"])
    op.create_index("idx_finance_invoice_tenant_statut", "finance_invoices",
                    ["tenant_id", "statut"])

    # ── E01 : epicerie_produits ───────────────────────────────────────────────
    op.create_table(
        "epicerie_produits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("ean", sa.String(20), nullable=True,
                  comment="Code EAN-13/EAN-8 (null si absent)"),
        sa.Column("designation_clean", sa.String(255), nullable=False,
                  comment="Désignation normalisée"),
        sa.Column("nom_court", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("categorie", sa.String(100), nullable=True),
        sa.Column("unite_vente", sa.String(10), nullable=False, default="U"),
        sa.Column("prix_unitaire_cts", sa.BigInteger(), nullable=False, default=0,
                  comment="Prix unitaire TTC en centimes"),
        sa.Column("taux_tva", sa.BigInteger(), nullable=False, default=2000,
                  comment="Taux TVA centièmes de pourcent (2000=20%)"),
        sa.Column("vendor_id", sa.BigInteger(),
                  sa.ForeignKey("finance_vendors.id", ondelete="SET NULL",
                                name="fk_epicerie_produit_vendor"),
                  nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_epicerie_produit_tenant",
                    "epicerie_produits", ["tenant_id"])
    op.create_index("idx_epicerie_produit_ean",
                    "epicerie_produits", ["tenant_id", "ean"])
    op.create_index("idx_epicerie_produit_vendor",
                    "epicerie_produits", ["vendor_id"])
    op.create_index("idx_epicerie_produit_categorie",
                    "epicerie_produits", ["categorie"])
    op.create_index("idx_epicerie_produit_actif",
                    "epicerie_produits", ["tenant_id", "actif"])

    # ── E02 : epicerie_stock ──────────────────────────────────────────────────
    op.create_table(
        "epicerie_stock",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("produit_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_produits.id", ondelete="RESTRICT",
                                name="fk_epicerie_stock_produit"),
                  nullable=False),
        sa.Column("quantite", sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False, default=0,
                  comment="Quantité en stock (≥ 0)"),
        sa.Column("seuil_alerte", sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantite >= 0",
                           name="check_epicerie_stock_quantite_positive"),
        sa.CheckConstraint("seuil_alerte >= 0",
                           name="check_epicerie_stock_seuil_positif"),
    )
    op.create_index("idx_epicerie_stock_tenant", "epicerie_stock", ["tenant_id"])
    op.create_index("idx_epicerie_stock_produit", "epicerie_stock", ["produit_id"])
    op.create_index("idx_epicerie_stock_tenant_produit", "epicerie_stock",
                    ["tenant_id", "produit_id"], unique=True)

    # ── E03 : epicerie_stock_movements ────────────────────────────────────────
    op.create_table(
        "epicerie_stock_movements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("produit_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_produits.id", ondelete="RESTRICT",
                                name="fk_epicerie_mvt_produit"),
                  nullable=False),
        sa.Column("type", sa.String(30), nullable=False,
                  comment="ENTREE|SORTIE|VENTE|AJUSTEMENT|PERTE|TRANSFERT_RESTAURANT"),
        sa.Column("quantite", sa.Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
                  comment="Quantité signée (+ entrée, − sortie)"),
        sa.Column("stock_apres", sa.Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False,
                  comment="Stock après ce mouvement"),
        sa.Column("date_mouvement", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(),
                  sa.ForeignKey("accounts.id", ondelete="SET NULL",
                                name="fk_epicerie_mvt_created_by"),
                  nullable=True),
        # Références contextuelles (colonnes simples — FK ajoutées après)
        sa.Column("vente_id", sa.BigInteger(), nullable=True),
        sa.Column("supply_order_id", sa.BigInteger(), nullable=True),
        sa.Column("transfer_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "type IN ('ENTREE', 'SORTIE', 'VENTE', 'AJUSTEMENT', 'PERTE', 'TRANSFERT_RESTAURANT')",
            name="check_epicerie_movement_type_valide",
        ),
        sa.CheckConstraint("stock_apres >= 0",
                           name="check_epicerie_movement_stock_apres_positif"),
    )
    op.create_index("idx_epicerie_mvt_tenant",
                    "epicerie_stock_movements", ["tenant_id"])
    op.create_index("idx_epicerie_mvt_produit",
                    "epicerie_stock_movements", ["produit_id"])
    op.create_index("idx_epicerie_mvt_type",
                    "epicerie_stock_movements", ["type"])
    op.create_index("idx_epicerie_mvt_date",
                    "epicerie_stock_movements", ["date_mouvement"])
    op.create_index("idx_epicerie_mvt_vente",
                    "epicerie_stock_movements", ["vente_id"])
    op.create_index("idx_epicerie_mvt_supply_order",
                    "epicerie_stock_movements", ["supply_order_id"])
    op.create_index("idx_epicerie_mvt_transfer",
                    "epicerie_stock_movements", ["transfer_id"])
    op.create_index("idx_epicerie_mvt_created_by",
                    "epicerie_stock_movements", ["created_by_id"])

    # ── E04 : epicerie_ventes ─────────────────────────────────────────────────
    op.create_table(
        "epicerie_ventes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("numero_ticket", sa.String(20), nullable=False,
                  comment="VTE-YYYYMMDD-NNNN"),
        sa.Column("date_vente", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, default="EN_COURS"),
        sa.Column("mode_paiement", sa.String(20), nullable=True),
        sa.Column("total_ht", sa.BigInteger(), nullable=False, default=0),
        sa.Column("total_tva", sa.BigInteger(), nullable=False, default=0),
        sa.Column("total_ttc", sa.BigInteger(), nullable=False, default=0),
        sa.Column("remise_pct", sa.Numeric(5, 2), nullable=False, default=0),
        sa.Column("remise_montant", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_especes", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_cb", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_rendu", sa.BigInteger(), nullable=False, default=0),
        sa.Column("client_nom", sa.String(200), nullable=True),
        sa.Column("client_email", sa.String(200), nullable=True),
        sa.Column("vendeur_id", sa.BigInteger(),
                  sa.ForeignKey("accounts.id", ondelete="SET NULL",
                                name="fk_epicerie_vente_vendeur"),
                  nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("invoice_id", sa.BigInteger(),
                  sa.ForeignKey("finance_invoices.id", ondelete="SET NULL",
                                name="fk_epicerie_vente_invoice"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "statut IN ('EN_COURS', 'VALIDEE', 'ANNULEE', 'REMBOURSEE')",
            name="check_epicerie_vente_statut_valide",
        ),
        sa.CheckConstraint("total_ttc >= 0",
                           name="check_epicerie_vente_total_positif"),
        sa.CheckConstraint("remise_pct >= 0 AND remise_pct <= 100",
                           name="check_epicerie_vente_remise_valide"),
    )
    op.create_index("idx_epicerie_vente_tenant", "epicerie_ventes", ["tenant_id"])
    op.create_index("idx_epicerie_vente_tenant_numero", "epicerie_ventes",
                    ["tenant_id", "numero_ticket"], unique=True)
    op.create_index("idx_epicerie_vente_statut", "epicerie_ventes", ["statut"])
    op.create_index("idx_epicerie_vente_date", "epicerie_ventes", ["date_vente"])
    op.create_index("idx_epicerie_vente_vendeur", "epicerie_ventes", ["vendeur_id"])
    op.create_index("idx_epicerie_vente_invoice", "epicerie_ventes", ["invoice_id"])
    op.create_index("idx_epicerie_vente_tenant_date", "epicerie_ventes",
                    ["tenant_id", "date_vente"])

    # ── E05 : epicerie_vente_lignes ───────────────────────────────────────────
    op.create_table(
        "epicerie_vente_lignes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("vente_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_ventes.id", ondelete="RESTRICT",
                                name="fk_epicerie_vligne_vente"),
                  nullable=False),
        sa.Column("produit_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_produits.id", ondelete="RESTRICT",
                                name="fk_epicerie_vligne_produit"),
                  nullable=False),
        sa.Column("quantite", sa.Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False),
        sa.Column("prix_unitaire_ht", sa.BigInteger(), nullable=False),
        sa.Column("taux_tva", sa.BigInteger(), nullable=False, default=2000),
        sa.Column("montant_ht", sa.BigInteger(), nullable=False),
        sa.Column("montant_tva", sa.BigInteger(), nullable=False),
        sa.Column("montant_ttc", sa.BigInteger(), nullable=False),
        sa.Column("remise_pct", sa.Numeric(5, 2), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantite > 0",
                           name="check_epicerie_ligne_quantite_positive"),
        sa.CheckConstraint("montant_ttc >= 0",
                           name="check_epicerie_ligne_montant_positif"),
        sa.CheckConstraint("remise_pct >= 0 AND remise_pct <= 100",
                           name="check_epicerie_ligne_remise_valide"),
    )
    op.create_index("idx_epicerie_vligne_tenant",
                    "epicerie_vente_lignes", ["tenant_id"])
    op.create_index("idx_epicerie_vligne_vente",
                    "epicerie_vente_lignes", ["vente_id"])
    op.create_index("idx_epicerie_vligne_produit",
                    "epicerie_vente_lignes", ["produit_id"])

    # ── E06 : epicerie_supply_orders ──────────────────────────────────────────
    op.create_table(
        "epicerie_supply_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("vendor_id", sa.BigInteger(),
                  sa.ForeignKey("finance_vendors.id", ondelete="RESTRICT",
                                name="fk_supply_order_vendor"),
                  nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("date_commande", sa.Date(), nullable=False),
        sa.Column("date_livraison_prevue", sa.Date(), nullable=True),
        sa.Column("date_livraison_reelle", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, default="en_attente",
                  comment="en_attente|confirmee|expediee|livree|annulee"),
        sa.Column("montant_ht", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_tva", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_ttc", sa.BigInteger(), nullable=False, default=0),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("invoice_id", sa.BigInteger(),
                  sa.ForeignKey("finance_invoices.id", ondelete="SET NULL",
                                name="fk_supply_order_invoice"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "statut IN ('en_attente', 'confirmee', 'expediee', 'livree', 'annulee')",
            name="check_supply_order_statut_valide",
        ),
        sa.CheckConstraint("montant_ttc >= 0",
                           name="check_supply_order_montant_positif"),
    )
    op.create_index("idx_supply_order_tenant",
                    "epicerie_supply_orders", ["tenant_id"])
    op.create_index("idx_supply_order_vendor",
                    "epicerie_supply_orders", ["vendor_id"])
    op.create_index("idx_supply_order_statut",
                    "epicerie_supply_orders", ["statut"])
    op.create_index("idx_supply_order_date",
                    "epicerie_supply_orders", ["date_commande"])
    op.create_index("idx_supply_order_invoice",
                    "epicerie_supply_orders", ["invoice_id"])
    op.create_index("idx_supply_order_tenant_statut",
                    "epicerie_supply_orders", ["tenant_id", "statut"])

    # ── E07 : epicerie_supply_order_lines ─────────────────────────────────────
    op.create_table(
        "epicerie_supply_order_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_supply_orders.id", ondelete="RESTRICT",
                                name="fk_supply_line_order"),
                  nullable=False),
        sa.Column("produit_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_produits.id", ondelete="SET NULL",
                                name="fk_supply_line_produit"),
                  nullable=True),
        sa.Column("designation", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False),
        sa.Column("prix_unitaire", sa.BigInteger(), nullable=False, default=0,
                  comment="Prix unitaire HT en centimes"),
        sa.Column("taux_tva", sa.BigInteger(), nullable=False, default=2000),
        sa.Column("received_quantity", sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0",
                           name="check_supply_line_quantity_positive"),
        sa.CheckConstraint("prix_unitaire >= 0",
                           name="check_supply_line_prix_positif"),
    )
    op.create_index("idx_supply_line_order",
                    "epicerie_supply_order_lines", ["order_id"])
    op.create_index("idx_supply_line_produit",
                    "epicerie_supply_order_lines", ["produit_id"])

    # ── T01 : internal_transfers ──────────────────────────────────────────────
    op.create_table(
        "internal_transfers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_source_id", sa.BigInteger(),
                  sa.ForeignKey("finance_entities.id", ondelete="RESTRICT",
                                name="fk_internal_transfer_source"),
                  nullable=False),
        sa.Column("entity_dest_id", sa.BigInteger(),
                  sa.ForeignKey("finance_entities.id", ondelete="RESTRICT",
                                name="fk_internal_transfer_dest"),
                  nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="PENDING",
                  comment="PENDING | VALIDATED | CANCELLED"),
        sa.Column("montant_ht", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_ttc", sa.BigInteger(), nullable=False, default=0),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("invoice_id", sa.BigInteger(),
                  sa.ForeignKey("finance_invoices.id", ondelete="SET NULL",
                                name="fk_internal_transfer_invoice"),
                  nullable=True),
        sa.Column("created_by", sa.BigInteger(),
                  sa.ForeignKey("accounts.id", ondelete="SET NULL",
                                name="fk_internal_transfer_created_by"),
                  nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_by", sa.BigInteger(),
                  sa.ForeignKey("accounts.id", ondelete="SET NULL",
                                name="fk_internal_transfer_validated_by"),
                  nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raison_annulation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'VALIDATED', 'CANCELLED')",
            name="check_internal_transfer_status_valide",
        ),
        sa.CheckConstraint("entity_source_id != entity_dest_id",
                           name="check_internal_transfer_source_ne_dest"),
        sa.CheckConstraint("montant_ttc >= 0",
                           name="check_internal_transfer_montant_positif"),
    )
    op.create_index("idx_internal_transfer_source",
                    "internal_transfers", ["entity_source_id"])
    op.create_index("idx_internal_transfer_dest",
                    "internal_transfers", ["entity_dest_id"])
    op.create_index("idx_internal_transfer_status",
                    "internal_transfers", ["status"])
    op.create_index("idx_internal_transfer_invoice",
                    "internal_transfers", ["invoice_id"])
    op.create_index("idx_internal_transfer_created_by",
                    "internal_transfers", ["created_by"])

    # ── T02 : internal_transfer_lines ─────────────────────────────────────────
    op.create_table(
        "internal_transfer_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("transfer_id", sa.BigInteger(),
                  sa.ForeignKey("internal_transfers.id", ondelete="RESTRICT",
                                name="fk_transfer_line_transfer"),
                  nullable=False),
        sa.Column("produit_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_produits.id", ondelete="SET NULL",
                                name="fk_transfer_line_produit"),
                  nullable=True),
        sa.Column("ingredient_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_ingredients.id", ondelete="SET NULL",
                                name="fk_transfer_line_ingredient"),
                  nullable=True),
        sa.Column("quantite", sa.Numeric(STOCK_PRECISION, STOCK_SCALE), nullable=False),
        sa.Column("unite", sa.String(10), nullable=False, default="U"),
        sa.Column("prix_unitaire", sa.BigInteger(), nullable=False, default=0),
        sa.Column("montant_ht", sa.BigInteger(), nullable=False, default=0),
        sa.Column("tva_pct", sa.BigInteger(), nullable=False, default=2000),
        sa.Column("montant_ttc", sa.BigInteger(), nullable=False, default=0),
        sa.Column("mouvement_epicerie_id", sa.BigInteger(),
                  sa.ForeignKey("epicerie_stock_movements.id", ondelete="SET NULL",
                                name="fk_transfer_line_mvt_epicerie"),
                  nullable=True),
        sa.Column("mouvement_restaurant_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_mouvements_stock.id", ondelete="SET NULL",
                                name="fk_transfer_line_mvt_resto"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantite > 0",
                           name="check_transfer_line_quantite_positive"),
        sa.CheckConstraint("prix_unitaire >= 0",
                           name="check_transfer_line_prix_positif"),
    )
    op.create_index("idx_transfer_line_transfer",
                    "internal_transfer_lines", ["transfer_id"])
    op.create_index("idx_transfer_line_produit",
                    "internal_transfer_lines", ["produit_id"])
    op.create_index("idx_transfer_line_ingredient",
                    "internal_transfer_lines", ["ingredient_id"])
    op.create_index("idx_transfer_line_mvt_epicerie",
                    "internal_transfer_lines", ["mouvement_epicerie_id"])
    op.create_index("idx_transfer_line_mvt_resto",
                    "internal_transfer_lines", ["mouvement_restaurant_id"])

    # ── F04 : finance_payments ────────────────────────────────────────────────
    op.create_table(
        "finance_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(),
                  sa.ForeignKey("finance_invoices.id", ondelete="RESTRICT",
                                name="fk_finance_payment_invoice"),
                  nullable=False),
        sa.Column("montant_cts", sa.BigInteger(), nullable=False,
                  comment="Montant paiement en centimes"),
        sa.Column("mode_paiement", sa.String(20), nullable=False),
        sa.Column("date_paiement", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "mode_paiement IN ('ESPECES', 'CB', 'CHEQUE', 'VIREMENT', 'MIXTE')",
            name="check_finance_payment_mode_valide",
        ),
        sa.CheckConstraint("montant_cts > 0",
                           name="check_finance_payment_montant_positif"),
    )
    op.create_index("idx_finance_payment_tenant",
                    "finance_payments", ["tenant_id"])
    op.create_index("idx_finance_payment_invoice",
                    "finance_payments", ["invoice_id"])
    op.create_index("idx_finance_payment_date",
                    "finance_payments", ["date_paiement"])
    op.create_index("idx_finance_payment_tenant_invoice",
                    "finance_payments", ["tenant_id", "invoice_id"])

    # ── FK retour sur finance_invoices ────────────────────────────────────────
    op.create_foreign_key(
        "fk_finance_invoice_supply_order",
        "finance_invoices", "epicerie_supply_orders",
        ["supply_order_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_finance_invoice_vente",
        "finance_invoices", "epicerie_ventes",
        ["vente_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_finance_invoice_transfer",
        "finance_invoices", "internal_transfers",
        ["transfer_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── FK retour sur epicerie_stock_movements ────────────────────────────────
    op.create_foreign_key(
        "fk_epicerie_mvt_vente",
        "epicerie_stock_movements", "epicerie_ventes",
        ["vente_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_epicerie_mvt_supply_order",
        "epicerie_stock_movements", "epicerie_supply_orders",
        ["supply_order_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_epicerie_mvt_transfer",
        "epicerie_stock_movements", "internal_transfers",
        ["transfer_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── Altération restaurant_mouvements_stock.ingredient_id → nullable + SET NULL ──
    # La migration restaurant (r0s1t2u3v4w5) a créé cette colonne NOT NULL + RESTRICT.
    # Les transferts internes épicerie→restaurant créent des mouvements sans ingrédient.
    # Stratégie expand : rendre nullable + changer ondelete RESTRICT → SET NULL.
    op.drop_constraint("fk_mvt_stock_ingredient",
                       "restaurant_mouvements_stock", type_="foreignkey")
    op.alter_column("restaurant_mouvements_stock", "ingredient_id",
                    nullable=True, existing_type=sa.BigInteger())
    op.create_foreign_key(
        "fk_mvt_stock_ingredient",
        "restaurant_mouvements_stock", "restaurant_ingredients",
        ["ingredient_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # ── Restaurer restaurant_mouvements_stock.ingredient_id ───────────────────
    op.drop_constraint("fk_mvt_stock_ingredient",
                       "restaurant_mouvements_stock", type_="foreignkey")
    op.alter_column("restaurant_mouvements_stock", "ingredient_id",
                    nullable=False, existing_type=sa.BigInteger())
    op.create_foreign_key(
        "fk_mvt_stock_ingredient",
        "restaurant_mouvements_stock", "restaurant_ingredients",
        ["ingredient_id"], ["id"],
        ondelete="RESTRICT",
    )

    # ── Supprimer FK retour epicerie_stock_movements ──────────────────────────
    op.drop_constraint("fk_epicerie_mvt_transfer",
                       "epicerie_stock_movements", type_="foreignkey")
    op.drop_constraint("fk_epicerie_mvt_supply_order",
                       "epicerie_stock_movements", type_="foreignkey")
    op.drop_constraint("fk_epicerie_mvt_vente",
                       "epicerie_stock_movements", type_="foreignkey")

    # ── Supprimer FK retour finance_invoices ──────────────────────────────────
    op.drop_constraint("fk_finance_invoice_transfer",
                       "finance_invoices", type_="foreignkey")
    op.drop_constraint("fk_finance_invoice_vente",
                       "finance_invoices", type_="foreignkey")
    op.drop_constraint("fk_finance_invoice_supply_order",
                       "finance_invoices", type_="foreignkey")

    # ── Supprimer tables dans l'ordre inverse des FK ──────────────────────────
    op.drop_table("finance_payments")
    op.drop_table("internal_transfer_lines")
    op.drop_table("internal_transfers")
    op.drop_table("epicerie_supply_order_lines")
    op.drop_table("epicerie_supply_orders")
    op.drop_table("epicerie_vente_lignes")
    op.drop_table("epicerie_ventes")
    op.drop_table("epicerie_stock_movements")
    op.drop_table("epicerie_stock")
    op.drop_table("epicerie_produits")
    op.drop_table("finance_invoices")
    op.drop_table("finance_vendors")
    op.drop_table("finance_entities")
