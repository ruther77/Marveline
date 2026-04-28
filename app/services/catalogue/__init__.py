"""Services domaine catalogue alimentaire V2.

Modules :
    etl_deduplication   : Normalisation + scoring Soft TF-IDF (ADR-07)
    etl_import_service  : Orchestration pipeline ETL (ADR-08)
"""
from app.services.catalogue.etl_classification import classify_by_knn, classify_categorie_code
from app.services.catalogue.etl_deduplication import (
    DecisionDeduplication,
    ResultatDeduplication,
    classify_designation,
    compute_similarity,
    is_ean_valid,
    normalize_designation,
)
from app.services.catalogue.etl_import_service import run_import
from app.etl_types import FactureMetadata, LigneParsee

__all__ = [
    "classify_by_knn",
    "classify_categorie_code",
    "DecisionDeduplication",
    "ResultatDeduplication",
    "classify_designation",
    "compute_similarity",
    "is_ean_valid",
    "normalize_designation",
    "FactureMetadata",
    "LigneParsee",
    "run_import",
]
