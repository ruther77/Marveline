"""Restaurant V2 — 12 tables du domaine restaurant (tenant_id=3).

Crée toutes les tables du domaine restaurant dans l'ordre de dépendance FK :
  - T01 : restaurant_categories_ingredient
  - T02 : restaurant_tables
  - T03 : restaurant_ingredients             (FK → T01)
  - T04 : restaurant_types_preparation
  - T05 : restaurant_recettes_type_preparation (FK → T04, T03)
  - T06 : restaurant_instances_preparation   (FK → T04, accounts)
  - T07 : restaurant_mouvements_stock        (FK → T03, accounts)
  - T08 : restaurant_variantes_plat          (FK → T04, T03)
  - T09 : restaurant_sides                   (FK → T03)
  - T10 : restaurant_commandes               (FK → T02, accounts)
  - T11 : restaurant_lignes_commande         (FK → T10, T08, T06, T09)
  - T12 : restaurant_alertes_stock           (FK → accounts)

Stratégie expand/contract :
  - Toutes les tables sont nouvelles (pas de DROP, pas de modification existante).
  - Rollback : downgrade() supprime les 12 tables dans l'ordre inverse des FK.

Références :
    V2_API_RESTAURANT.md (source de vérité endpoints)
    FC_RESTAURANT_COMMANDES.md (statuts, atomicité, fractionnement)
    FC_RESTAURANT_CUISINE.md (marmites, recettes, portions)
    FC_RESTAURANT_INGREDIENTS.md (stock, mouvements, alertes)
    ADR-09 (2 niveaux de stock), ADR-14 (lecture directe DB), ADR-06-BIS (TVA)

Revision ID: r0s1t2u3v4w5
Revises: v1w2x3y4z5a6
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "r0s1t2u3v4w5"
down_revision = "v1w2x3y4z5a6"
branch_labels = None
depends_on = None

STOCK_PRECISION = 10
STOCK_SCALE = 3


def upgrade() -> None:
    # ── T01 : restaurant_categories_ingredient ────────────────────────────────
    op.create_table(
        "restaurant_categories_ingredient",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("nom", sa.String(100), nullable=False,
                  comment="Nom affiché. Ex: 'Protéines', 'Légumes'"),
        sa.Column("is_proteine", sa.Boolean(), nullable=False, server_default="false",
                  comment="True si protéine : incluse dans le calcul des ruptures dashboard"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_categories_ingredient_tenant",
                    "restaurant_categories_ingredient", ["tenant_id"])
    op.create_index("uq_categories_ingredient_tenant_nom",
                    "restaurant_categories_ingredient", ["tenant_id", "nom"],
                    unique=True)

    # ── T02 : restaurant_tables ───────────────────────────────────────────────
    op.create_table(
        "restaurant_tables",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("numero", sa.String(20), nullable=False,
                  comment="Numéro ou nom affiché. Ex: '5', 'Terrasse 2'"),
        sa.Column("capacite", sa.Integer(), nullable=False,
                  comment="Nombre maximum de couverts"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true",
                  comment="False → table retirée du plan de salle"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("capacite >= 1", name="check_table_resto_capacite_positive"),
    )
    op.create_index("idx_restaurant_tables_tenant",
                    "restaurant_tables", ["tenant_id"])
    op.create_index("uq_restaurant_tables_tenant_numero",
                    "restaurant_tables", ["tenant_id", "numero"],
                    unique=True)

    # ── T03 : restaurant_ingredients ─────────────────────────────────────────
    op.create_table(
        "restaurant_ingredients",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("categorie_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_categories_ingredient.id",
                                ondelete="SET NULL", name="fk_ingredient_categorie"),
                  nullable=True,
                  comment="Catégorie de l'ingrédient"),
        sa.Column("nom", sa.String(200), nullable=False,
                  comment="Nom. Ex: 'Poulet', 'Tomates concassées'"),
        sa.Column("unite_stock", sa.String(10), nullable=False, server_default="kg",
                  comment="Unité de mesure. Ex: 'kg', 'L', 'pièce'"),
        sa.Column("stock_actuel",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False, server_default="0",
                  comment="Stock actuel (ADR-14 : lecture directe DB)"),
        sa.Column("stock_alerte",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False, server_default="0",
                  comment="Seuil bas — badge alerte si stock_actuel <= stock_alerte"),
        sa.Column("cout_unitaire_cts", sa.BigInteger(), nullable=True,
                  comment="Coût d'achat en centimes. Ex: 89000 = 890,00 XPF/kg"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("stock_actuel >= 0", name="check_ingredient_stock_positif"),
        sa.CheckConstraint("stock_alerte >= 0", name="check_ingredient_alerte_positif"),
    )
    op.create_index("idx_ingredients_resto_tenant",
                    "restaurant_ingredients", ["tenant_id"])
    op.create_index("idx_ingredients_resto_categorie",
                    "restaurant_ingredients", ["categorie_id"])
    op.create_index("idx_ingredients_resto_tenant_active",
                    "restaurant_ingredients", ["tenant_id", "is_active"])

    # ── T04 : restaurant_types_preparation ───────────────────────────────────
    op.create_table(
        "restaurant_types_preparation",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("nom", sa.String(200), nullable=False,
                  comment="Nom de la recette. Ex: 'Sauce rougail', 'Carry poulet'"),
        sa.Column("portions_par_batch", sa.Integer(), nullable=False,
                  comment="Nombre de portions standard par batch de cuisson"),
        sa.Column("temps_cuisson_min", sa.Integer(), nullable=False, server_default="0",
                  comment="Temps de cuisson indicatif en minutes"),
        sa.Column("seuil_alerte_portions", sa.Integer(), nullable=False, server_default="5",
                  comment="Portions restantes en dessous de ce seuil → badge 'faible'"),
        sa.Column("notes", sa.Text(), nullable=True,
                  comment="Notes de recette libres"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("portions_par_batch >= 1",
                           name="check_type_prep_batch_positif"),
        sa.CheckConstraint("temps_cuisson_min >= 0",
                           name="check_type_prep_cuisson_positif"),
        sa.CheckConstraint("seuil_alerte_portions >= 0",
                           name="check_type_prep_seuil_positif"),
    )
    op.create_index("idx_types_prep_tenant",
                    "restaurant_types_preparation", ["tenant_id"])
    op.create_index("idx_types_prep_tenant_active",
                    "restaurant_types_preparation", ["tenant_id", "is_active"])

    # ── T05 : restaurant_recettes_type_preparation ───────────────────────────
    op.create_table(
        "restaurant_recettes_type_preparation",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("type_preparation_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_types_preparation.id",
                                ondelete="RESTRICT", name="fk_recette_type_prep"),
                  nullable=False),
        sa.Column("ingredient_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_ingredients.id",
                                ondelete="RESTRICT", name="fk_recette_ingredient"),
                  nullable=False),
        sa.Column("quantite_par_batch",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False,
                  comment="Quantité de l'ingrédient pour un batch complet"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantite_par_batch > 0",
                           name="check_recette_quantite_positive"),
    )
    op.create_index("idx_recettes_type_prep_tenant",
                    "restaurant_recettes_type_preparation", ["tenant_id"])
    op.create_index("idx_recettes_type_prep_type",
                    "restaurant_recettes_type_preparation", ["type_preparation_id"])
    op.create_index("idx_recettes_type_prep_ingredient",
                    "restaurant_recettes_type_preparation", ["ingredient_id"])
    op.create_index("uq_recettes_type_prep_pair",
                    "restaurant_recettes_type_preparation",
                    ["type_preparation_id", "ingredient_id"],
                    unique=True)

    # ── T06 : restaurant_instances_preparation ───────────────────────────────
    op.create_table(
        "restaurant_instances_preparation",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("type_preparation_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_types_preparation.id",
                                ondelete="RESTRICT", name="fk_instance_type_prep"),
                  nullable=False),
        sa.Column("portions_initiales", sa.Integer(), nullable=False,
                  comment="Portions au lancement"),
        sa.Column("portions_restantes", sa.Integer(), nullable=False,
                  comment="Portions disponibles — mis à jour atomiquement (ADR-14)"),
        sa.Column("date_cuisine", sa.Date(), nullable=False,
                  comment="Date de cuisson"),
        sa.Column("heure_lancement", sa.DateTime(timezone=True), nullable=True,
                  comment="Timestamp précis du lancement (optionnel)"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(),
                  sa.ForeignKey("accounts.id",
                                ondelete="SET NULL", name="fk_instance_prep_created_by"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("portions_initiales >= 1",
                           name="check_instance_prep_portions_initiales_positive"),
        sa.CheckConstraint("portions_restantes >= 0",
                           name="check_instance_prep_portions_restantes_positive"),
        sa.CheckConstraint("portions_restantes <= portions_initiales",
                           name="check_instance_prep_portions_coherentes"),
    )
    op.create_index("idx_instances_prep_tenant",
                    "restaurant_instances_preparation", ["tenant_id"])
    op.create_index("idx_instances_prep_type",
                    "restaurant_instances_preparation", ["type_preparation_id"])
    op.create_index("idx_instances_prep_date",
                    "restaurant_instances_preparation", ["date_cuisine"])
    op.create_index("idx_instances_prep_created_by",
                    "restaurant_instances_preparation", ["created_by_id"])
    op.create_index("idx_instances_prep_tenant_date",
                    "restaurant_instances_preparation", ["tenant_id", "date_cuisine"])

    # ── T07 : restaurant_mouvements_stock ─────────────────────────────────────
    op.create_table(
        "restaurant_mouvements_stock",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("ingredient_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_ingredients.id",
                                ondelete="RESTRICT", name="fk_mvt_stock_ingredient"),
                  nullable=False),
        sa.Column("type_mouvement", sa.String(30), nullable=False,
                  comment="Type: entree | consommation | transfert_entrant | inventaire | perte"),
        sa.Column("quantite",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False,
                  comment="Quantité signée : + entrée, − consommation/perte"),
        sa.Column("stock_apres",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=False,
                  comment="Stock après ce mouvement — enregistré atomiquement"),
        sa.Column("date_mouvement", sa.DateTime(timezone=True), nullable=False,
                  comment="Timestamp du mouvement réel"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(),
                  sa.ForeignKey("accounts.id",
                                ondelete="SET NULL", name="fk_mvt_stock_created_by"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "type_mouvement IN ('entree','consommation','transfert_entrant','inventaire','perte')",
            name="check_mouvement_stock_type_valide"
        ),
        sa.CheckConstraint("stock_apres >= 0",
                           name="check_mouvement_stock_apres_positif"),
    )
    op.create_index("idx_mvt_stock_resto_tenant",
                    "restaurant_mouvements_stock", ["tenant_id"])
    op.create_index("idx_mvt_stock_resto_ingredient",
                    "restaurant_mouvements_stock", ["ingredient_id"])
    op.create_index("idx_mvt_stock_resto_date",
                    "restaurant_mouvements_stock", ["date_mouvement"])
    op.create_index("idx_mvt_stock_resto_created_by",
                    "restaurant_mouvements_stock", ["created_by_id"])

    # ── T08 : restaurant_variantes_plat ───────────────────────────────────────
    op.create_table(
        "restaurant_variantes_plat",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("nom", sa.String(200), nullable=False,
                  comment="Nom affiché sur le menu"),
        sa.Column("type", sa.String(20), nullable=False,
                  comment="Type : plat | boisson | formule"),
        sa.Column("prix_vente_cts", sa.BigInteger(), nullable=False,
                  comment="Prix en centimes"),
        sa.Column("taux_tva", sa.Integer(), nullable=False, server_default="550",
                  comment="Taux TVA en centièmes de % (ADR-06-BIS). Ex: 550 = 5,5%"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type_preparation_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_types_preparation.id",
                                ondelete="SET NULL", name="fk_variante_type_prep"),
                  nullable=True),
        sa.Column("ingredient_proteine_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_ingredients.id",
                                ondelete="SET NULL", name="fk_variante_proteine"),
                  nullable=True),
        sa.Column("quantite_proteine",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('plat','boisson','formule')",
                           name="check_variante_plat_type_valide"),
        sa.CheckConstraint("prix_vente_cts >= 0",
                           name="check_variante_plat_prix_positif"),
        sa.CheckConstraint("taux_tva >= 0",
                           name="check_variante_plat_tva_positive"),
        sa.CheckConstraint(
            "quantite_proteine IS NULL OR quantite_proteine > 0",
            name="check_variante_plat_qtite_proteine_positive"
        ),
    )
    op.create_index("idx_variantes_plat_tenant",
                    "restaurant_variantes_plat", ["tenant_id"])
    op.create_index("idx_variantes_plat_type_prep",
                    "restaurant_variantes_plat", ["type_preparation_id"])
    op.create_index("idx_variantes_plat_proteine",
                    "restaurant_variantes_plat", ["ingredient_proteine_id"])
    op.create_index("idx_variantes_plat_tenant_active",
                    "restaurant_variantes_plat", ["tenant_id", "is_active"])

    # ── T09 : restaurant_sides ────────────────────────────────────────────────
    op.create_table(
        "restaurant_sides",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("nom", sa.String(200), nullable=False,
                  comment="Nom affiché. Ex: 'Riz blanc', 'Rougail tomates'"),
        sa.Column("ingredient_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_ingredients.id",
                                ondelete="SET NULL", name="fk_side_ingredient"),
                  nullable=True),
        sa.Column("quantite_par_portion",
                  sa.Numeric(STOCK_PRECISION, STOCK_SCALE),
                  nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "quantite_par_portion IS NULL OR quantite_par_portion > 0",
            name="check_side_qtite_positive"
        ),
        sa.CheckConstraint(
            "(ingredient_id IS NULL) = (quantite_par_portion IS NULL)",
            name="check_side_ingredient_qtite_couplees"
        ),
    )
    op.create_index("idx_sides_resto_tenant",
                    "restaurant_sides", ["tenant_id"])
    op.create_index("idx_sides_resto_ingredient",
                    "restaurant_sides", ["ingredient_id"])
    op.create_index("idx_sides_resto_tenant_active",
                    "restaurant_sides", ["tenant_id", "is_active"])

    # ── T10 : restaurant_commandes ────────────────────────────────────────────
    op.create_table(
        "restaurant_commandes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("table_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_tables.id",
                                ondelete="SET NULL", name="fk_commande_table"),
                  nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="OUVERTE",
                  comment="Statut : OUVERTE | SERVIE | PAYEE | ANNULEE"),
        sa.Column("nb_couverts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sous_total_cts", sa.BigInteger(), nullable=True),
        sa.Column("tva_cts", sa.BigInteger(), nullable=True),
        sa.Column("total_cts", sa.BigInteger(), nullable=True),
        sa.Column("pourboire_cts", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("mode_paiement", sa.String(20), nullable=True),
        sa.Column("fractionnement", postgresql.JSON(astext_type=sa.Text()), nullable=True,
                  comment="JSON : liste fractions [{parts, montant_cts}]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("date_fermeture", sa.DateTime(timezone=True), nullable=True,
                  comment="Date/heure de fermeture (PAYEE ou ANNULEE)"),
        sa.Column("created_by_id", sa.BigInteger(),
                  sa.ForeignKey("accounts.id",
                                ondelete="SET NULL", name="fk_commande_created_by"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "statut IN ('OUVERTE','SERVIE','PAYEE','ANNULEE')",
            name="check_commande_resto_statut_valide"
        ),
        sa.CheckConstraint("nb_couverts >= 1",
                           name="check_commande_resto_couverts_positif"),
        sa.CheckConstraint("pourboire_cts >= 0",
                           name="check_commande_resto_pourboire_positif"),
    )
    op.create_index("idx_commandes_resto_tenant",
                    "restaurant_commandes", ["tenant_id"])
    op.create_index("idx_commandes_resto_table",
                    "restaurant_commandes", ["table_id"])
    op.create_index("idx_commandes_resto_statut",
                    "restaurant_commandes", ["statut"])
    op.create_index("idx_commandes_resto_created_by",
                    "restaurant_commandes", ["created_by_id"])
    op.create_index("idx_commandes_resto_tenant_statut",
                    "restaurant_commandes", ["tenant_id", "statut"])

    # ── T11 : restaurant_lignes_commande ──────────────────────────────────────
    op.create_table(
        "restaurant_lignes_commande",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("commande_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_commandes.id",
                                ondelete="RESTRICT", name="fk_ligne_commande"),
                  nullable=False),
        sa.Column("variante_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_variantes_plat.id",
                                ondelete="RESTRICT", name="fk_ligne_variante"),
                  nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prix_unitaire_cts", sa.BigInteger(), nullable=False,
                  comment="Snapshot prix au moment de la commande"),
        sa.Column("statut_plat", sa.String(20), nullable=False, server_default="ENVOYEE",
                  comment="Statut cuisine : ENVOYEE | LANCEE | PRETE | SERVIE"),
        sa.Column("instance_preparation_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_instances_preparation.id",
                                ondelete="SET NULL", name="fk_ligne_instance_prep"),
                  nullable=True),
        sa.Column("side_id", sa.BigInteger(),
                  sa.ForeignKey("restaurant_sides.id",
                                ondelete="SET NULL", name="fk_ligne_side"),
                  nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "statut_plat IN ('ENVOYEE','LANCEE','PRETE','SERVIE')",
            name="check_ligne_commande_resto_statut_valide"
        ),
        sa.CheckConstraint("quantite >= 1",
                           name="check_ligne_commande_resto_quantite_positive"),
        sa.CheckConstraint("prix_unitaire_cts >= 0",
                           name="check_ligne_commande_resto_prix_positif"),
    )
    op.create_index("idx_lignes_commande_resto_tenant",
                    "restaurant_lignes_commande", ["tenant_id"])
    op.create_index("idx_lignes_commande_resto_commande",
                    "restaurant_lignes_commande", ["commande_id"])
    op.create_index("idx_lignes_commande_resto_variante",
                    "restaurant_lignes_commande", ["variante_id"])
    op.create_index("idx_lignes_commande_resto_instance",
                    "restaurant_lignes_commande", ["instance_preparation_id"])
    op.create_index("idx_lignes_commande_resto_side",
                    "restaurant_lignes_commande", ["side_id"])
    op.create_index("idx_lignes_commande_resto_statut",
                    "restaurant_lignes_commande", ["statut_plat"])

    # ── T12 : restaurant_alertes_stock ────────────────────────────────────────
    op.create_table(
        "restaurant_alertes_stock",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False,
                  comment="tenant_id=3 pour restaurant"),
        sa.Column("entite_type", sa.String(30), nullable=False,
                  comment="Type d'entité : ingredient | instance_preparation"),
        sa.Column("entite_id", sa.BigInteger(), nullable=False,
                  comment="ID de l'entité en alerte"),
        sa.Column("seuil_type", sa.String(20), nullable=False,
                  comment="Type de seuil : bas | zero"),
        sa.Column("resolu_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolu_by_id", sa.BigInteger(),
                  sa.ForeignKey("accounts.id",
                                ondelete="SET NULL", name="fk_alerte_resolu_by"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "entite_type IN ('ingredient','instance_preparation')",
            name="check_alerte_stock_resto_entite_type_valide"
        ),
        sa.CheckConstraint(
            "seuil_type IN ('bas','zero')",
            name="check_alerte_stock_resto_seuil_type_valide"
        ),
    )
    op.create_index("idx_alertes_stock_resto_tenant",
                    "restaurant_alertes_stock", ["tenant_id"])
    op.create_index("idx_alertes_stock_resto_entite",
                    "restaurant_alertes_stock", ["entite_type", "entite_id"])
    op.create_index("idx_alertes_stock_resto_resolu",
                    "restaurant_alertes_stock", ["resolu_at"])
    op.create_index("idx_alertes_stock_resto_resolu_by",
                    "restaurant_alertes_stock", ["resolu_by_id"])
    op.create_index("idx_alertes_stock_resto_tenant_active",
                    "restaurant_alertes_stock", ["tenant_id", "resolu_at"])


def downgrade() -> None:
    # Ordre inverse des FK : T12 → T11 → T10 → T09 → T08 → T07 → T06 → T05 → T04 → T03 → T02 → T01
    op.drop_table("restaurant_alertes_stock")
    op.drop_table("restaurant_lignes_commande")
    op.drop_table("restaurant_commandes")
    op.drop_table("restaurant_sides")
    op.drop_table("restaurant_variantes_plat")
    op.drop_table("restaurant_mouvements_stock")
    op.drop_table("restaurant_instances_preparation")
    op.drop_table("restaurant_recettes_type_preparation")
    op.drop_table("restaurant_types_preparation")
    op.drop_table("restaurant_ingredients")
    op.drop_table("restaurant_tables")
    op.drop_table("restaurant_categories_ingredient")
