"""V2 Alimentaire — Socle partagé Phase A (M00→M04).

Crée les 5 tables du domaine catalogue alimentaire sans tenant_id :
  - M00 : categories_produit   (référentiel catégories)
  - M01 : catalogue_produits   (catalogue ETL partagé)
  - M02 : fournisseurs_alim    (référentiel fournisseurs)
  - M03 : etl_imports          (log imports ETL)
  - M04 : etl_conflicts        (log déduplication Jaro-Winkler)

Stratégie expand/contract :
  - Toutes les tables sont nouvelles (pas de DROP, pas de modification existante).
  - Rollback : downgrade() supprime les 5 tables dans l'ordre inverse des FK.

Références : V2 §6.1→§6.4, ADR-01, ADR-02, ADR-07, ADR-15.

Revision ID: v1w2x3y4z5a6
Revises: f3a4b5c6d7e8
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "v1w2x3y4z5a6"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── M00 : categories_produit ──────────────────────────────────────────────
    op.create_table(
        "categories_produit",
        sa.Column("code", sa.String(20), primary_key=True,
                  comment="Clé courte ASCII unique. Ex: 'epic_pate', 'bois_biere'"),
        sa.Column("libelle", sa.String(100), nullable=False,
                  comment="Nom d'affichage. Ex: 'Pâtes et riz'"),
        sa.Column("tva_defaut", sa.Numeric(5, 4), nullable=False, server_default="0.085",
                  comment="Taux TVA par défaut pour cette catégorie (ADR-06-BIS). Ex: 0.085 = 8,5%"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_categories_libelle", "categories_produit", ["libelle"])

    # Seed des catégories de base (épicerie + boissons + frais)
    op.execute("""
        INSERT INTO categories_produit (code, libelle, tva_defaut) VALUES
          ('epic_pate',   'Pâtes et riz',          0.085),
          ('epic_conserv','Conserves et condiments',0.085),
          ('bois_biere',  'Bières et alcools',      0.085),
          ('bois_soft',   'Boissons non alcoolisées',0.085),
          ('frais_lait',  'Produits laitiers',      0.085),
          ('frais_viande','Viandes et charcuteries',0.085),
          ('epicerie',    'Épicerie générale',      0.085)
        ON CONFLICT (code) DO NOTHING
    """)

    # ── M01 : catalogue_produits ──────────────────────────────────────────────
    op.create_table(
        "catalogue_produits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ean", sa.String(20), nullable=True,
                  comment="Code EAN-8 ou EAN-13. NULL pour produits sans code-barres"),
        sa.Column("designation", sa.String(300), nullable=False,
                  comment="Désignation telle que reçue du fournisseur"),
        sa.Column("designation_norm", sa.String(300), nullable=True,
                  comment="Version normalisée pour déduplication Jaro-Winkler (ADR-07)"),
        sa.Column("marque", sa.String(100), nullable=True),
        sa.Column("unite_base", sa.String(20), nullable=False,
                  comment="Unité de stockage. Ex: 'piece', 'kg', 'L'"),
        sa.Column("conditionnement", sa.String(100), nullable=True),
        sa.Column("source_fournisseur", sa.String(50), nullable=True,
                  comment="Code fournisseur source. Ex: 'METRO', 'TAIYAT'"),
        sa.Column("categorie_code", sa.String(20), nullable=True,
                  comment="FK applicative vers categories_produit.code"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "uq_catalogue_ean", "catalogue_produits", ["ean"],
        unique=True,
        postgresql_where=sa.text("ean IS NOT NULL"),
    )
    op.create_index("idx_catalogue_categorie", "catalogue_produits", ["categorie_code"])
    op.create_index("idx_catalogue_source", "catalogue_produits", ["source_fournisseur"])

    # ── M02 : fournisseurs_alim ───────────────────────────────────────────────
    op.create_table(
        "fournisseurs_alim",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("nom", sa.String(200), nullable=False,
                  comment="Raison sociale complète du fournisseur"),
        sa.Column("code_fournisseur", sa.String(50), nullable=True,
                  comment="Code court unique. Ex: 'METRO', 'TAIYAT'"),
        sa.Column("type_facturation", sa.String(20), nullable=True,
                  comment="Format de facture fournisseur : 'pdf', 'email', 'xlsx'"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("uq_fournisseur_nom", "fournisseurs_alim", ["nom"], unique=True)
    op.create_index(
        "uq_fournisseur_code", "fournisseurs_alim", ["code_fournisseur"],
        unique=True,
        postgresql_where=sa.text("code_fournisseur IS NOT NULL"),
    )

    # ── M03 : etl_imports ────────────────────────────────────────────────────
    op.create_table(
        "etl_imports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fournisseur_id", sa.BigInteger(), nullable=True,
                  comment="FK nullable vers fournisseurs_alim.id"),
        sa.Column("fichier_source", sa.Text(), nullable=True),
        sa.Column("nb_lignes_total", sa.Integer(), nullable=True),
        sa.Column("nb_lignes_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nb_lignes_conflit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nb_lignes_erreur", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("statut", sa.String(20), nullable=False, server_default="PENDING",
                  comment="PENDING | RUNNING | SUCCES | PARTIEL | ECHEC"),
        sa.Column("erreur_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "statut IN ('PENDING','RUNNING','SUCCES','PARTIEL','ECHEC')",
            name="ck_etl_imports_statut",
        ),
        sa.ForeignKeyConstraint(
            ["fournisseur_id"], ["fournisseurs_alim.id"],
            name="fk_etl_imports_fournisseur",
            ondelete="SET NULL",
        ),
    )
    op.create_index("idx_etl_imports_statut", "etl_imports", ["statut"])
    op.create_index("idx_etl_imports_fournisseur", "etl_imports", ["fournisseur_id"])

    # ── M04 : etl_conflicts ───────────────────────────────────────────────────
    op.create_table(
        "etl_conflicts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("etl_import_id", sa.BigInteger(), nullable=True,
                  comment="FK nullable vers etl_imports.id (ADR-15 : SET NULL, pas CASCADE)"),
        sa.Column("catalogue_produit_id", sa.BigInteger(), nullable=True,
                  comment="FK nullable vers catalogue_produits.id"),
        sa.Column("designation_entrante", sa.Text(), nullable=False),
        sa.Column("designation_existante", sa.Text(), nullable=True),
        sa.Column("score_similarite", sa.Numeric(4, 3), nullable=True,
                  comment="Score Jaro-Winkler. NULL pour EAN_COLLISION."),
        sa.Column("type_conflit", sa.String(30), nullable=True,
                  comment="EAN_COLLISION | DESIGNATION_PROCHE | CATEGORIE_INCONNUE"),
        sa.Column("resolution", sa.String(20), nullable=False, server_default="PENDING",
                  comment="PENDING | MERGED | KEPT_SEPARATE"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "resolution IN ('PENDING','MERGED','KEPT_SEPARATE')",
            name="ck_etl_conflicts_resolution",
        ),
        sa.ForeignKeyConstraint(
            ["etl_import_id"], ["etl_imports.id"],
            name="fk_etl_conflicts_import",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["catalogue_produit_id"], ["catalogue_produits.id"],
            name="fk_etl_conflicts_produit",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "idx_etl_conflicts_import_pending", "etl_conflicts",
        ["etl_import_id", "resolution"],
        postgresql_where=sa.text("resolution = 'PENDING'"),
    )
    op.create_index("idx_etl_conflicts_resolution", "etl_conflicts", ["resolution"])
    op.create_index("idx_etl_conflicts_produit", "etl_conflicts", ["catalogue_produit_id"])


def downgrade() -> None:
    # Suppression dans l'ordre inverse des FK
    op.drop_table("etl_conflicts")
    op.drop_table("etl_imports")
    op.drop_table("fournisseurs_alim")
    op.drop_table("catalogue_produits")
    op.drop_table("categories_produit")
