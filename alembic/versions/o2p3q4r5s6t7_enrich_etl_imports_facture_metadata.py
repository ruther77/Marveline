"""Enrich etl_imports with facture metadata (ADR-25).

Expand-only migration: adds nullable columns for supplier invoice tracking
and extends the statut CHECK constraint with PREVIEW/VALIDATED/REJECTED.

Revision ID: o2p3q4r5s6t7
Revises: n2o3p4q5r6s7
Create Date: 2026-03-14

Rollback: safe — all new columns are nullable, CHECK is replaced atomically.
"""
from alembic import op
import sqlalchemy as sa


revision = "o2p3q4r5s6t7"
down_revision = "n2o3p4q5r6s7"
branch_labels = None
depends_on = None

_OLD_STATUTS = "statut IN ('PENDING','RUNNING','SUCCES','PARTIEL','ECHEC')"
_NEW_STATUTS = (
    "statut IN ('PENDING','RUNNING','PREVIEW','VALIDATED','REJECTED',"
    "'SUCCES','PARTIEL','ECHEC')"
)


def upgrade() -> None:
    # ── Nouvelles colonnes facture (toutes nullable = expand safe) ───────────
    op.add_column(
        "etl_imports",
        sa.Column(
            "numero_facture", sa.String(100), nullable=True,
            comment="Numéro de facture du fournisseur (ex: 'F-2026-1234').",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "date_facture", sa.Date(), nullable=True,
            comment="Date d'émission de la facture fournisseur.",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "montant_ht_total", sa.BigInteger(), nullable=True,
            comment="Montant HT total en centimes.",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "montant_tva_total", sa.BigInteger(), nullable=True,
            comment="Montant TVA total en centimes.",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "montant_ttc_total", sa.BigInteger(), nullable=True,
            comment="Montant TTC total en centimes.",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "vendor_code", sa.String(50), nullable=True,
            comment="Code fournisseur (ex: 'METRO', 'TAIYAT').",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "quality_score", sa.Integer(), nullable=True,
            comment="Score qualité parsing 0-100.",
        ),
    )
    op.add_column(
        "etl_imports",
        sa.Column(
            "ecart_reconciliation", sa.Numeric(10, 2), nullable=True,
            comment="Écart en euros entre total déclaré et total calculé.",
        ),
    )

    # ── CHECK constraints ────────────────────────────────────────────────────
    op.drop_constraint("ck_etl_imports_statut", "etl_imports", type_="check")
    op.create_check_constraint(
        "ck_etl_imports_statut", "etl_imports", _NEW_STATUTS,
    )
    op.create_check_constraint(
        "ck_etl_imports_montant_ht_positif", "etl_imports",
        "montant_ht_total IS NULL OR montant_ht_total >= 0",
    )
    op.create_check_constraint(
        "ck_etl_imports_montant_ttc_positif", "etl_imports",
        "montant_ttc_total IS NULL OR montant_ttc_total >= 0",
    )
    op.create_check_constraint(
        "ck_etl_imports_quality_score_range", "etl_imports",
        "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)",
    )

    # ── Index ────────────────────────────────────────────────────────────────
    op.create_index("idx_etl_imports_vendor_code", "etl_imports", ["vendor_code"])


def downgrade() -> None:
    op.drop_index("idx_etl_imports_vendor_code", table_name="etl_imports")

    op.drop_constraint("ck_etl_imports_quality_score_range", "etl_imports", type_="check")
    op.drop_constraint("ck_etl_imports_montant_ttc_positif", "etl_imports", type_="check")
    op.drop_constraint("ck_etl_imports_montant_ht_positif", "etl_imports", type_="check")
    op.drop_constraint("ck_etl_imports_statut", "etl_imports", type_="check")
    op.create_check_constraint(
        "ck_etl_imports_statut", "etl_imports", _OLD_STATUTS,
    )

    for col in (
        "ecart_reconciliation", "quality_score", "vendor_code",
        "montant_ttc_total", "montant_tva_total", "montant_ht_total",
        "date_facture", "numero_facture",
    ):
        op.drop_column("etl_imports", col)
