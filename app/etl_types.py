"""Types partagés du pipeline ETL catalogue alimentaire (ADR-08 + ADR-25).

Module léger sans dépendance lourde (pas de SQLAlchemy, FastAPI, etc.)
pour que les parsers fournisseur puissent l'importer sans cascade.

Importé par :
  - scripts/etl/parsers/metro.py, taiyat.py (parsers)
  - scripts/etl/import_pipeline.py (orchestrateur CLI)
  - app/services/catalogue/etl_import_service.py (service métier)
  - app/tasks/etl_tasks.py (Celery task)
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class LigneParsee:
    """Ligne normalisée issue d'un parser fournisseur (ADR-08 + ADR-25).

    Champs requis : designation, unite_base, source_fournisseur.
    Tous les autres sont optionnels.
    designation_norm est calculé par classify_designation si absent.

    ADR-25 : champs financiers ajoutés pour traçabilité facture fournisseur.
    Les montants sont en centimes (BigInteger convention).
    """

    # ── Champs catalogue (existants) ─────────────────────────────────────────
    designation: str
    unite_base: str
    source_fournisseur: str
    ean: Optional[str] = None
    designation_norm: Optional[str] = None
    marque: Optional[str] = None
    conditionnement: Optional[str] = None
    categorie_code: Optional[str] = None

    # ── Champs financiers (ADR-25) ───────────────────────────────────────────
    quantite: Optional[float] = None
    prix_unitaire_cts: Optional[int] = None
    montant_ht_cts: Optional[int] = None
    montant_ttc_cts: Optional[int] = None
    taux_tva_centieme: Optional[int] = None  # 2000 = 20.00%, 550 = 5.50%

    # ── Champs enrichis parser v2 ─────────────────────────────────────────────
    article_fournisseur: Optional[str] = None    # N° article fournisseur (METRO: 6-7 chiffres)
    degre_alcool: Optional[float] = None         # "40D" → 40.0, "5.5D" → 5.5
    contenant: Optional[str] = None              # VP, BTE, PET, BID, FUT...
    volume_unitaire_ml: Optional[int] = None     # Volume unitaire en mL (750, 330...)
    colisage: Optional[int] = None               # Nb unités/plateau (6, 12, 18, 24)
    designation_raw: Optional[str] = None        # Désignation brute avant nettoyage

    # ── Coordonnées PDF et confiance (Phase 2) ───────────────────────────────
    page_number: Optional[int] = None            # Page PDF (0-indexed)
    y_position: Optional[float] = None           # Y en points PDF (origin top-left)
    confidence_score: Optional[int] = None       # Score confiance 0-100 par ligne
    similar_products: Optional[list] = None      # Top-N produits similaires [{id, designation, ean, score}]

    # ── Auto-fill traçable (phase S1-S5) ─────────────────────────────────────
    # Clé = nom du champ (ean, marque, categorie_code, conditionnement,
    # prix_unitaire_cts, taux_tva_centieme, volume_unitaire_ml).
    # Valeur = {"source": "norm_exact"|"article_four"|"correction_history"|"tfidf_auto",
    #           "score": 0..1, "candidate_id": int, "candidate_designation": str}
    # Permet au frontend d'afficher un badge "auto 92%" avec source et au user
    # de révoquer d'un clic (on vide le champ + on réouvre la suggestion).
    auto_applied_fields: Optional[dict] = None


@dataclass
class FactureMetadata:
    """Métadonnées facture extraites par parse_with_facture_metrics() (ADR-25).

    Portées au niveau EtlImport pour permettre le workflow preview/validation.
    Les montants sont en centimes (BigInteger convention).

    Routing multi-tenant (TAIYAT) :
      client_name = INCONTOURNABLE | NOUTAM | None
      target_tenant_id = tenant de destination (2=épicerie, 3=restaurant)
    """

    vendor_code: str
    numero_facture: Optional[str] = None
    date_facture: Optional[date] = None
    montant_ht_total: Optional[int] = None
    montant_tva_total: Optional[int] = None
    montant_ttc_total: Optional[int] = None
    quality_score: Optional[int] = None
    ecart_reconciliation: Optional[float] = None
    lignes_brutes: int = 0  # nombre total de lignes avant filtrage
    client_name: Optional[str] = None          # TAIYAT : INCONTOURNABLE | NOUTAM
    target_tenant_id: Optional[int] = None     # tenant cible pour validation
