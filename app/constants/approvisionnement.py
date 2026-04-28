"""Constantes domaine approvisionnement alimentaire — V2 Architecture.

Couvre : fournisseurs connus, cycle de vie ETL, déduplication, unités d'achat.
"""
from enum import Enum


class SourceFournisseur(str, Enum):
    """Codes canoniques des fournisseurs alimentaires (ADR-02).

    Utilisé dans :
        - catalogue_produits.source_fournisseur (string libre, pas FK)
        - ETL parsers (scripts/etl/parsers/)
        - Filtres API catalogue
    """

    METRO    = "METRO"
    TAIYAT   = "TAIYAT"
    EUROCIEL = "EUROCIEL"
    ETHAN    = "ETHAN"
    GNANAM   = "GNANAM"


class TypeImportFournisseur(str, Enum):
    """Identifiant du parser ETL pour un fournisseur.

    Métadonnée code Python — ne va pas en DB.
    Utilisé dans :
        - scripts/etl/parsers/ (sélection du parser)
        - app/tasks/etl_tasks.py (dispatch Celery)
    """

    CSV_METRO  = "csv_metro"
    CSV_TAIYAT = "csv_taiyat"
    MANUEL     = "manuel"


class EtlStatutImport(str, Enum):
    """Cycle de vie complet d'un import ETL (V2 §6.3 + états opérationnels).

    Transitions : PENDING → RUNNING → (SUCCES | PARTIEL | ECHEC)

    PENDING et RUNNING : états opérationnels ajoutés pour le suivi Celery.
    SUCCES / PARTIEL / ECHEC : états terminaux de la spec V2.

    Utilisé dans :
        - models.EtlImport.statut
        - app/tasks/etl_tasks.py
    """

    PENDING   = "PENDING"    # Tâche créée, en attente d'un worker Celery
    RUNNING   = "RUNNING"    # Worker en cours de traitement
    PREVIEW   = "PREVIEW"    # Parsing terminé, en attente validation opérateur
    VALIDATED = "VALIDATED"  # Opérateur a validé → FinanceInvoice créée
    REJECTED  = "REJECTED"   # Opérateur a rejeté la facture parsée
    SUCCES    = "SUCCES"     # Import catalogue complet, aucun conflit bloquant
    PARTIEL   = "PARTIEL"    # Import terminé, des conflits restent en attente
    ECHEC     = "ECHEC"      # Échec technique ou validation structurelle


class EtlTypeConflit(str, Enum):
    """Classification des conflits de déduplication (ADR-07).

    Absent de V2 spec mais conservé (Phase A) : requis pour l'interface
    de résolution opérateur et le reporting ETL.

    Utilisé dans :
        - models.EtlConflict.type_conflit
        - services.catalogue.deduplication_service
    """

    EAN_COLLISION      = "EAN_COLLISION"       # Même EAN, fournisseurs distincts
    DESIGNATION_PROCHE = "DESIGNATION_PROCHE"  # Score Jaro-Winkler dans la plage d'alerte
    CATEGORIE_INCONNUE = "CATEGORIE_INCONNUE"  # categorie_code absent du référentiel


class EtlResolutionConflit(str, Enum):
    """Résolutions possibles pour un conflit de déduplication (V2 §6.4).

    Utilisé dans :
        - models.EtlConflict.resolution
        - API résolution manuelle opérateur
    """

    PENDING       = "PENDING"       # En attente de décision opérateur
    MERGED        = "MERGED"        # Fusionné dans l'entrée catalogue existante
    KEPT_SEPARATE = "KEPT_SEPARATE" # Conservé comme entrée distincte


class UniteAchat(str, Enum):
    """Unités d'achat dans les lignes de commande fournisseur.

    Utilisé dans :
        - catalogue_produits.unite_base
        - lignes_commande_fournisseur.unite
    """

    KG     = "KG"
    LITRE  = "L"
    PIECE  = "PIECE"
    CARTON = "CARTON"
    BOITE  = "BOITE"
    SACHET = "SACHET"


# ── Seuils de déduplication Jaro-Winkler (ADR-07 §2b) ────────────────────────
# score ≥ ETL_SEUIL_MATCH     → même produit (pas de conflit, logger uniquement)
# score ∈ [ETL_SEUIL_CONFLIT_ALERTE, ETL_SEUIL_MATCH) → créer EtlConflict
# score < ETL_SEUIL_CONFLIT_ALERTE → entrée distincte sans conflit
ETL_SEUIL_MATCH          = 0.85  # Correspondance automatique (V2 ADR-07)
ETL_SEUIL_CONFLIT_ALERTE = 0.75  # Seuil bas d'alerte déduplication
