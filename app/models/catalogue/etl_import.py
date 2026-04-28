"""Modèle EtlImport — Log technique des imports ETL alimentaires (M03).

Table sans tenant_id : log opérationnel partagé entre tous les imports,
quel que soit le tenant qui a déclenché l'import.

Références :
    §6.3    : schéma SQL validé
    ADR-08  : parsers ETL fournisseurs
    ADR-15  : etl_import_id dans etl_conflicts (FK nullable, pas CASCADE)
    ADR-25  : enrichissement facture fournisseur (metadata + workflow preview)
"""
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Statuts valides — alignés sur EtlStatutImport (app/constants/approvisionnement.py)
_STATUTS_VALIDES = (
    'PENDING', 'RUNNING', 'PREVIEW', 'VALIDATED', 'REJECTED',
    'SUCCES', 'PARTIEL', 'ECHEC', 'REVERTED',
)


class EtlImport(Base, TimestampMixin):
    """Log d'un import ETL : une ligne par fichier fournisseur traité.

    Cycle de vie classique (catalogue) : PENDING → RUNNING → (SUCCES | PARTIEL | ECHEC).
    Cycle de vie facture (preview)      : PENDING → RUNNING → PREVIEW → (VALIDATED | REJECTED).
    Revert (annulation post-validation) : VALIDATED → REVERTED.

    Quand statut=PREVIEW, les champs facture (numero_facture, date_facture, montants)
    sont renseignés et modifiables par l'opérateur avant validation.

    Pas de SoftDeleteMixin : log append-only, on ne supprime pas un import.
    Les conflits liés survivent à l'éventuelle suppression du log (FK SET NULL).
    """

    __tablename__ = "etl_imports"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    fournisseur_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="FK nullable vers fournisseurs_alim.id. NULL si fournisseur inconnu."
    )
    fichier_source: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Nom ou chemin du fichier importé. Ex: 'metro_2026-03-10.csv'"
    )
    fichier_path: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Chemin relatif du PDF persisté. Ex: 'etl/42.pdf'"
    )
    nb_lignes_total: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Nombre total de lignes dans le fichier source."
    )
    nb_lignes_ok: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Lignes intégrées sans conflit."
    )
    nb_lignes_conflit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Lignes ayant généré un EtlConflict."
    )
    nb_lignes_erreur: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Lignes rejetées (format invalide, champ obligatoire manquant)."
    )
    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING",
        comment="Cycle de vie : PENDING → RUNNING → PREVIEW → VALIDATED/REJECTED "
                "ou PENDING → RUNNING → SUCCES/PARTIEL/ECHEC"
    )
    erreur_detail: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Détail de l'erreur technique (traceback, message) si statut=ECHEC."
    )

    # ── Métadonnées facture fournisseur (ADR-25) ────────────────────────────────
    # Renseignés par le parser via FactureMetadata, modifiables en PREVIEW.

    numero_facture: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Numéro de facture du fournisseur (ex: 'F-2026-1234')."
    )
    date_facture: Mapped[Optional[object]] = mapped_column(
        Date, nullable=True,
        comment="Date d'émission de la facture fournisseur."
    )
    montant_ht_total: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Montant HT total en centimes (parser déclaré ou réconcilié)."
    )
    montant_tva_total: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Montant TVA total en centimes."
    )
    montant_ttc_total: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="Montant TTC total en centimes."
    )
    vendor_code: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Code fournisseur (ex: 'METRO', 'TAIYAT'). Lien applicatif vers finance_vendors.code."
    )
    client_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="Nom client extrait par le parser (TAIYAT : INCONTOURNABLE|NOUTAM)."
    )
    target_tenant_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment=(
            "Tenant de destination pour la validation (routing multi-tenant). "
            "NULL = fallback sur tenant de l'opérateur."
        )
    )
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Score qualité parsing 0-100 (cohérence montants, OCR, couverture EAN)."
    )
    ecart_reconciliation: Mapped[Optional[object]] = mapped_column(
        Numeric(10, 2), nullable=True,
        comment="Écart en euros entre total déclaré et total calculé (signe = sens)."
    )

    # ── Lignes parsées (persist entre PREVIEW et VALIDATED) ────────────────────
    lignes_data: Mapped[Optional[object]] = mapped_column(
        JSON, nullable=True,
        comment="Lignes parsées sérialisées (list[dict]) — persiste entre PREVIEW et VALIDATED."
    )

    # ── Progression validation ──────────────────────────────────────────────────
    validation_step: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Étape courante de validation (catalogue, stock, invoice, prix). NULL si pas en cours."
    )

    # ── Revert (annulation post-validation) ──────────────────────────────────────

    prix_snapshot: Mapped[Optional[object]] = mapped_column(
        JSON, nullable=True,
        comment="Snapshot {catalogue_produit_id: prix_unitaire_cts} capturé avant validation. "
                "Permet la restauration des prix catalogue en cas de revert."
    )
    reverted_at: Mapped[Optional[object]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Date/heure du revert. NULL si non reverté."
    )
    reverted_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="ID du compte qui a déclenché le revert."
    )

    # created_at / updated_at hérités de TimestampMixin

    __table_args__ = (
        CheckConstraint(
            f"statut IN {_STATUTS_VALIDES}",
            name="ck_etl_imports_statut",
        ),
        # Montants négatifs autorisés — avoirs/notes de crédit METRO
        # (contraintes positives supprimées — les avoirs sont des opérations légitimes)
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)",
            name="ck_etl_imports_quality_score_range",
        ),
        # Index pour monitoring opérationnel : retrouver les imports en cours
        Index("idx_etl_imports_statut", "statut"),
        # Index pour filtrage par fournisseur (tableau de bord ETL)
        Index("idx_etl_imports_fournisseur", "fournisseur_id"),
        # Index pour retrouver les previews d'un fournisseur
        Index("idx_etl_imports_vendor_code", "vendor_code"),
        # Index pour routing multi-tenant (TAIYAT)
        Index("idx_etl_imports_target_tenant", "target_tenant_id"),
    )

    def __repr__(self) -> str:
        facture_info = f" facture={self.numero_facture!r}" if self.numero_facture else ""
        return (
            f"<EtlImport id={self.id} fournisseur_id={self.fournisseur_id} "
            f"statut={self.statut!r} lignes={self.nb_lignes_total}{facture_info}>"
        )
